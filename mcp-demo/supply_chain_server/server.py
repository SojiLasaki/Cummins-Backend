from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from itertools import count
from random import Random
from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("Supply Chain Connector")
_rng = Random(20260301)
_tick = count(1)


@dataclass
class PartRow:
    part_number: str
    name: str
    quantity_available: int
    reorder_threshold: int
    supplier: str
    eta_days: int


PARTS: list[PartRow] = [
    PartRow("FI-6.7-001", "Fuel Injector", 4, 6, "Cascadia Supply", 3),
    PartRow("OF-15-002", "Oil Filter", 20, 8, "Midwest Fleet Parts", 2),
    PartRow("AL-24-120", "Alternator", 1, 3, "Prime Electric", 5),
    PartRow("HS-COOL-77", "Coolant Hose", 7, 5, "ThermaFlow", 2),
    PartRow("SNS-TEMP-09", "Temperature Sensor", 12, 6, "SensorGrid", 4),
]

EXTERNAL_ORDERS: list[dict[str, Any]] = []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _simulate_inventory_tick() -> None:
    step = next(_tick)
    for idx, part in enumerate(PARTS):
        delta = ((step + idx) % 3) - 1  # -1,0,+1 deterministic
        if delta == 0:
            continue
        part.quantity_available = max(0, part.quantity_available + delta)
        if part.quantity_available <= part.reorder_threshold:
            part.eta_days = max(1, part.eta_days + 1)
        elif part.eta_days > 1:
            part.eta_days -= 1


@mcp.tool()
def search_parts(query: str, location: str = "INDY", limit: int = 5) -> dict[str, Any]:
    """Search parts by keyword with live simulated availability."""
    _simulate_inventory_tick()
    query_l = query.strip().lower()
    rows = [
        asdict(part)
        for part in PARTS
        if query_l in part.name.lower() or query_l in part.part_number.lower() or query_l in part.supplier.lower()
    ]
    if not rows:
        rows = [asdict(part) for part in PARTS]
    return {
        "location": location,
        "generated_at": _now_iso(),
        "results": rows[: max(1, min(limit, 25))],
    }


@mcp.tool()
def get_part_availability(part_number: str, location: str = "INDY") -> dict[str, Any]:
    """Get latest availability for a part."""
    _simulate_inventory_tick()
    for part in PARTS:
        if part.part_number.lower() == part_number.lower() or part.name.lower() == part_number.lower():
            return {
                "part": asdict(part),
                "location": location,
                "is_below_threshold": part.quantity_available <= part.reorder_threshold,
                "generated_at": _now_iso(),
            }
    return {
        "error": "part_not_found",
        "part_number": part_number,
        "location": location,
        "generated_at": _now_iso(),
    }


@mcp.tool()
def get_eta(part_number: str, location: str = "INDY") -> dict[str, Any]:
    """Get ETA for replenishment of a part."""
    availability = get_part_availability(part_number, location)
    if availability.get("error"):
        return availability
    part = availability["part"]
    return {
        "part_number": part["part_number"],
        "location": location,
        "eta_days": part["eta_days"],
        "supplier": part["supplier"],
        "generated_at": _now_iso(),
    }


@mcp.tool()
def create_external_order(
    part_number: str,
    quantity: int,
    ship_to_station_id: str,
    requested_by: str,
    reason: str = "",
) -> dict[str, Any]:
    """Create a simulated external supplier order."""
    order_ref = f"EXT-{len(EXTERNAL_ORDERS) + 1:04d}"
    eta = _rng.randint(2, 7)
    record = {
        "order_ref": order_ref,
        "part_number": part_number,
        "quantity": int(max(1, quantity)),
        "ship_to_station_id": ship_to_station_id,
        "requested_by": requested_by,
        "reason": reason,
        "status": "submitted",
        "eta_days": eta,
        "created_at": _now_iso(),
    }
    EXTERNAL_ORDERS.append(record)
    return record


@mcp.tool()
def list_supplier_events(limit: int = 20) -> dict[str, Any]:
    """Return recent external order events."""
    return {
        "generated_at": _now_iso(),
        "events": list(reversed(EXTERNAL_ORDERS))[: max(1, min(limit, 100))],
    }


@mcp.resource("supply://parts/catalog")
def supply_catalog() -> dict[str, Any]:
    return {
        "generated_at": _now_iso(),
        "parts": [asdict(part) for part in PARTS],
    }


@mcp.resource("supply://inventory/{location}")
def supply_inventory(location: str) -> dict[str, Any]:
    _simulate_inventory_tick()
    return {
        "location": location,
        "generated_at": _now_iso(),
        "inventory": [asdict(part) for part in PARTS],
    }


@mcp.resource("supply://orders/{order_ref}")
def supply_order(order_ref: str) -> dict[str, Any]:
    for row in EXTERNAL_ORDERS:
        if row["order_ref"] == order_ref:
            return row
    return {"error": "order_not_found", "order_ref": order_ref, "generated_at": _now_iso()}


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=9101, path="/mcp")
