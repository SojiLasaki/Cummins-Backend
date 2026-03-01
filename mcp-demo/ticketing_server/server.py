from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("Ticket Operations Connector")

TICKETS: list[dict[str, Any]] = []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@mcp.tool()
def create_ticket(
    title: str,
    description: str,
    specialization: str = "engine",
    priority: int = 2,
    station_id: str = "",
    customer_id: str = "",
) -> dict[str, Any]:
    """Create external ticket in simulated ticketing system."""
    ticket_ref = f"EXT-TK-{len(TICKETS) + 1:05d}"
    ticket = {
        "ticket_ref": ticket_ref,
        "title": title,
        "description": description,
        "specialization": specialization,
        "priority": max(1, min(4, int(priority))),
        "status": "open",
        "station_id": station_id,
        "customer_id": customer_id,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "notes": [],
    }
    TICKETS.append(ticket)
    return ticket


@mcp.tool()
def update_ticket(ticket_ref: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Patch ticket fields in simulated ticketing store."""
    for ticket in TICKETS:
        if ticket["ticket_ref"] != ticket_ref:
            continue
        for key, value in (patch or {}).items():
            if key in {"ticket_ref", "created_at"}:
                continue
            ticket[key] = value
        ticket["updated_at"] = _now_iso()
        return ticket
    return {"error": "ticket_not_found", "ticket_ref": ticket_ref}


@mcp.tool()
def get_ticket(ticket_ref: str) -> dict[str, Any]:
    """Fetch single ticket by external reference."""
    for ticket in TICKETS:
        if ticket["ticket_ref"] == ticket_ref:
            return ticket
    return {"error": "ticket_not_found", "ticket_ref": ticket_ref}


@mcp.tool()
def list_open_tickets(station_id: str = "", specialization: str = "") -> dict[str, Any]:
    """List open tickets for location/specialization filters."""
    rows = [row for row in TICKETS if row.get("status") in {"open", "assigned", "in_progress", "awaiting_parts"}]
    if station_id:
        rows = [row for row in rows if str(row.get("station_id") or "") == station_id]
    if specialization:
        rows = [row for row in rows if str(row.get("specialization") or "") == specialization]
    return {
        "generated_at": _now_iso(),
        "count": len(rows),
        "results": rows,
    }


@mcp.resource("ticket://open")
def ticket_open_resource() -> dict[str, Any]:
    return list_open_tickets()


@mcp.resource("ticket://{ticket_ref}")
def ticket_resource(ticket_ref: str) -> dict[str, Any]:
    return get_ticket(ticket_ref)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=9102, path="/mcp")
