from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastmcp import FastMCP

mcp = FastMCP("Workforce Connector")

EMPLOYEES: list[dict[str, Any]] = [
    {
        "emp_id": "EMP-1001",
        "name": "Jordan Smith",
        "specialization": "engine",
        "station_id": "INDY",
        "status": "available",
        "score": 92,
    },
    {
        "emp_id": "EMP-1002",
        "name": "Taylor Garcia",
        "specialization": "electrical",
        "station_id": "INDY",
        "status": "available",
        "score": 88,
    },
    {
        "emp_id": "EMP-1003",
        "name": "Morgan Lee",
        "specialization": "engine",
        "station_id": "CHI",
        "status": "busy",
        "score": 84,
    },
    {
        "emp_id": "EMP-1004",
        "name": "Riley Johnson",
        "specialization": "engine",
        "station_id": "INDY",
        "status": "available",
        "score": 81,
    },
]

RESERVATIONS: list[dict[str, Any]] = []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sweep_expired_reservations() -> None:
    now = datetime.now(timezone.utc)
    for row in RESERVATIONS:
        if row["status"] != "active":
            continue
        if datetime.fromisoformat(row["expires_at"]) <= now:
            row["status"] = "expired"
            for employee in EMPLOYEES:
                if employee["emp_id"] == row["emp_id"]:
                    employee["status"] = "available"


@mcp.tool()
def search_employees(
    station_id: str = "",
    specialization: str = "",
    status: str = "",
) -> dict[str, Any]:
    """Search roster by location, specialization, and status."""
    _sweep_expired_reservations()
    rows = EMPLOYEES
    if station_id:
        rows = [row for row in rows if row["station_id"].lower() == station_id.lower()]
    if specialization:
        rows = [row for row in rows if row["specialization"].lower() == specialization.lower()]
    if status:
        rows = [row for row in rows if row["status"].lower() == status.lower()]
    rows = sorted(rows, key=lambda row: row["score"], reverse=True)
    return {
        "generated_at": _now_iso(),
        "count": len(rows),
        "results": rows,
    }


@mcp.tool()
def get_employee(emp_id: str) -> dict[str, Any]:
    """Get details of one employee."""
    _sweep_expired_reservations()
    for row in EMPLOYEES:
        if row["emp_id"] == emp_id:
            return row
    return {"error": "employee_not_found", "emp_id": emp_id}


@mcp.tool()
def reserve_employee(emp_id: str, ticket_ref: str, hold_minutes: int = 30) -> dict[str, Any]:
    """Reserve an employee for a ticket for a limited time window."""
    _sweep_expired_reservations()
    for row in EMPLOYEES:
        if row["emp_id"] != emp_id:
            continue
        if row["status"] != "available":
            return {"error": "employee_not_available", "emp_id": emp_id, "status": row["status"]}
        row["status"] = "reserved"
        reservation = {
            "reservation_id": f"RSV-{len(RESERVATIONS) + 1:05d}",
            "emp_id": emp_id,
            "ticket_ref": ticket_ref,
            "status": "active",
            "created_at": _now_iso(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=max(5, hold_minutes))).isoformat(),
        }
        RESERVATIONS.append(reservation)
        return reservation
    return {"error": "employee_not_found", "emp_id": emp_id}


@mcp.tool()
def release_employee(emp_id: str, ticket_ref: str) -> dict[str, Any]:
    """Release a reservation and mark employee available."""
    _sweep_expired_reservations()
    for reservation in RESERVATIONS:
        if reservation["emp_id"] == emp_id and reservation["ticket_ref"] == ticket_ref and reservation["status"] == "active":
            reservation["status"] = "released"
            for employee in EMPLOYEES:
                if employee["emp_id"] == emp_id:
                    employee["status"] = "available"
            return reservation
    return {"error": "reservation_not_found", "emp_id": emp_id, "ticket_ref": ticket_ref}


@mcp.resource("employee://roster")
def employee_roster() -> dict[str, Any]:
    _sweep_expired_reservations()
    return {
        "generated_at": _now_iso(),
        "results": EMPLOYEES,
    }


@mcp.resource("employee://availability/{station_id}")
def employee_availability(station_id: str) -> dict[str, Any]:
    _sweep_expired_reservations()
    return search_employees(station_id=station_id)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=9103, path="/mcp")
