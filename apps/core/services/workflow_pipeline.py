from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from apps.agents.assignment_engine import assign_best_technician
from apps.customers.models import CustomerProfile
from apps.diagnostics.agents.severity_agent import SeverityAgent
from apps.diagnostics.models import DiagnosticReport
from apps.inventory.models import Component, Part
from apps.orders.models import Order
from apps.tickets.models import Ticket


def _gen_external_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12].upper()}"


def _normalize_severity(value: Any) -> int:
    """
    Ticket/Diagnostic severity is stored as an int with choices:
    1=Low, 2=Medium, 3=High, 4=Severe.
    """
    if value is None:
        return 0
    if isinstance(value, int):
        return max(1, min(4, value))
    if isinstance(value, str):
        v = value.strip().lower()
        mapping = {"low": 1, "medium": 2, "high": 3, "severe": 4}
        if v in mapping:
            return mapping[v]
        try:
            return max(1, min(4, int(v)))
        except Exception:
            return 0
    return 0


def _severity_label_from_int(value: Optional[int]) -> str:
    mapping = {
        1: "Low",
        2: "Medium",
        3: "High",
        4: "Severe",
    }
    return mapping.get(int(value or 0), "UNKNOWN")


def _ticket_status_to_label(status: Optional[str]) -> str:
    # Map internal statuses to external spec-friendly labels
    if not status:
        return "Open"
    status = status.lower()
    if status == "pending":
        return "Open"
    # Capitalize words like "in_progress" -> "In Progress"
    return " ".join(part.capitalize() for part in status.split("_"))


def _spec_specialization(code: Optional[str]) -> str:
    if code == "electrical":
        return "Electrical Technician"
    if code == "engine":
        return "Engine Technician"
    return "UNKNOWN"


def _spec_expertise(code: Optional[str]) -> str:
    lookup = {
        "junior": "Junior",
        "mid": "Mid",
        "senior": "Senior",
    }
    if not code:
        return "UNKNOWN"
    return lookup.get(code.lower(), "UNKNOWN")


def _get_parts(*, part_ids: Any = None, part_names: Any = None) -> list[Part]:
    parts: list[Part] = []
    if part_ids:
        if isinstance(part_ids, (list, tuple)):
            parts = list(Part.objects.filter(id__in=part_ids))
        else:
            parts = list(Part.objects.filter(id=part_ids))
    elif part_names:
        if isinstance(part_names, (list, tuple)):
            parts = list(Part.objects.filter(name__in=part_names))
        else:
            parts = list(Part.objects.filter(name=part_names))
    return parts


def _get_customer(*, customer_id: Any = None, user: Any = None) -> Optional[CustomerProfile]:
    if customer_id:
        try:
            return CustomerProfile.objects.get(id=customer_id)
        except CustomerProfile.DoesNotExist:
            return None
    if user is not None:
        return getattr(user, "customer_profile", None)
    return None


def _get_component(*, component_id: Any = None, component_name: Any = None) -> Optional[Component]:
    if component_id:
        try:
            return Component.objects.get(id=component_id)
        except Component.DoesNotExist:
            return None
    if component_name:
        try:
            return Component.objects.get(name=component_name)
        except Component.DoesNotExist:
            return None
    return None


@dataclass(frozen=True)
class FailureDetectedResult:
    report: DiagnosticReport
    ticket: Ticket
    orders: list[Order]


class WorkflowPipeline:
    """
    Implements the workflow:
    Failure detected -> DiagnosticReport -> Ticket -> Technician assignment -> Part ordering (if low stock)
    """

    def __init__(self, *, severity_agent: Optional[SeverityAgent] = None):
        self.severity_agent = severity_agent or SeverityAgent()

    @transaction.atomic
    def failure_detected(self, payload: dict[str, Any], *, user: Any = None) -> FailureDetectedResult:
        title = (payload.get("title") or "").strip() or "Failure detected"
        description = (payload.get("description") or payload.get("issue_description") or "").strip()

        specialization = (payload.get("specialization") or "engine").strip().lower()
        if specialization not in {"engine", "electrical"}:
            specialization = "engine"

        # Severity: explicit payload > calculated
        severity = _normalize_severity(payload.get("severity"))
        if severity == 0:
            calculated = self.severity_agent.calculate({"title": title, "description": description})
            severity = _normalize_severity(calculated) or 2

        customer = _get_customer(customer_id=payload.get("customer_id"), user=user)
        component = _get_component(
            component_id=payload.get("component_id"),
            component_name=payload.get("component_name"),
        )
        parts = _get_parts(part_ids=payload.get("part_ids"), part_names=payload.get("part_names"))

        identified_at = payload.get("identified_at")
        if not identified_at:
            identified_at = timezone.now()

        report = DiagnosticReport.objects.create(
            diagnostics_id=_gen_external_id("DIA"),
            ticket_id=None,
            title=title,
            description=description,
            severity=severity,
            status="pending",
            specialization=specialization,
            expertise_requirement=(payload.get("expertise_requirement") or "junior").strip().lower(),
            customer=customer,
            fault_code=(payload.get("fault_code") or "").strip() or None,
            component=component,
            ai_summary=payload.get("ai_summary"),
            probable_cause=payload.get("probable_cause"),
            recommended_actions=payload.get("recommended_actions"),
            confidence_score=payload.get("confidence_score"),
            identified_at=identified_at,
            requires_follow_up=bool(payload.get("requires_follow_up", False)),
            repeat_issue=bool(payload.get("repeat_issue", False)),
            diagnostic_duration_minutes=payload.get("diagnostic_duration_minutes"),
            performed_by=payload.get("performed_by") or (getattr(user, "username", None) if user else None),
        )
        if parts:
            report.parts.set(parts)

        ticket = Ticket.objects.create(
            ticket_id=_gen_external_id("TKT"),
            customer=customer,
            assigned_technician=None,
            specialization=specialization,
            title=title,
            description=description,
            severity=severity,
            status="pending",
            customer_satisfaction_rating=None,
            estimated_resolution_time_minutes=payload.get("estimated_resolution_time_minutes"),
            actual_resolution_time_minutes=None,
            predicted_resolution_summary=payload.get("predicted_resolution_summary") or payload.get("ai_summary"),
            auto_assigned=False,
            created_by=payload.get("created_by") or (getattr(user, "username", None) if user else None),
            priority=_normalize_severity(payload.get("priority")) or severity,
            issue_description=payload.get("issue_description") or description,
        )
        if parts:
            ticket.parts.set(parts)

        # Decide assignment + ordering first, then persist the final ticket status once.
        technician = assign_best_technician(ticket)
        if technician:
            ticket.assigned_technician = technician
            ticket.auto_assigned = True
            ticket.assigned_at = timezone.now()

            report.assigned_technician = technician
            report.status = "in_progress"
            report.save(update_fields=["assigned_technician", "status"])

        report.ticket_id = ticket
        report.save(update_fields=["ticket_id"])

        orders: list[Order] = []
        for part in parts:
            if part.quantity_available <= part.reorder_threshold:
                # Prevent duplicate agent-created pending orders for same ticket+part.
                existing = Order.objects.filter(
                    ticket=ticket,
                    part=part,
                    status="pending",
                    requested_by_agent=True,
                ).exists()
                if existing:
                    continue
                qty = max(1, int(part.reorder_threshold or 1))
                orders.append(
                    Order.objects.create(
                        ticket=ticket,
                        customer=customer,
                        part=part,
                        quantity=qty,
                        status="pending",
                        requested_by_agent=True,
                        requested_by=user if user and getattr(user, "is_authenticated", False) else None,
                    )
                )

        # Final ticket status:
        # - If a technician is assigned, keep status as "assigned" even if parts are needed
        #   (avoid overwriting "assigned" with "awaiting_parts").
        # - If no technician assigned but parts are needed, use "awaiting_parts".
        # - Otherwise keep "pending".
        if technician:
            ticket.status = "assigned"
        elif orders:
            ticket.status = "awaiting_parts"
        else:
            ticket.status = "pending"

        update_fields = ["status"]
        if technician:
            update_fields += ["assigned_technician", "auto_assigned", "assigned_at"]
        ticket.save(update_fields=update_fields)

        return FailureDetectedResult(report=report, ticket=ticket, orders=orders)


def build_spec_outputs(payload: dict[str, Any], result: FailureDetectedResult) -> dict[str, Any]:
    """
    Build the four objects described in the orchestrator spec:
    1) Failure Detection Output
    2) Diagnostic Report
    3) Ticket
    4) Part Order Request (or Not Triggered)
    """
    # 1) Failure Detection Output
    component = result.report.component
    parts = list(result.report.parts.all())
    failure_detection_output = {
        "failure_code": payload.get("failure_code") or "UNKNOWN",
        "fault_code": payload.get("fault_code") or result.report.fault_code or "UNKNOWN",
        "component": getattr(component, "name", None) or "UNKNOWN",
        "parts": [getattr(p, "part_number", None) or getattr(p, "name", None) or "UNKNOWN" for p in parts] or [],
    }

    # 2) Diagnostic Report object per spec
    diagnostic = result.report
    customer = diagnostic.customer
    diagnostic_report = {
        "diagnostic_id": diagnostic.diagnostics_id or "UNKNOWN",
        "ticket_id": result.ticket.ticket_id or "UNKNOWN",
        "title": diagnostic.title or payload.get("title") or "UNKNOWN",
        "severity": _severity_label_from_int(diagnostic.severity),
        "status": "Submitted",  # by the time this returns, ticket is created
        "specialization": _spec_specialization(diagnostic.specialization),
        "expertise_requirement": _spec_expertise(diagnostic.expertise_requirement),
        "customer": getattr(customer, "id", None) or "UNKNOWN",
        "fault_code": diagnostic.fault_code or payload.get("fault_code") or "UNKNOWN",
        "component": getattr(component, "name", None) or "UNKNOWN",
        "parts": [getattr(p, "part_number", None) or getattr(p, "name", None) or "UNKNOWN" for p in parts] or [],
        "ai_summary": diagnostic.ai_summary
        or payload.get("ai_summary")
        or f"Automated diagnostic for fault_code={diagnostic.fault_code or 'UNKNOWN'} on component={getattr(component, 'name', 'UNKNOWN')}.",
        "probable_cause": diagnostic.probable_cause or "UNKNOWN",
        "description": diagnostic.description or payload.get("description") or "UNKNOWN",
        "recommended_actions": diagnostic.recommended_actions or "UNKNOWN",
        "confidence_score": float(diagnostic.confidence_score or 0.5),
        "identified_at": (diagnostic.identified_at.isoformat() if diagnostic.identified_at else "UNKNOWN"),
        "resolved_at": (diagnostic.resolved_at.isoformat() if diagnostic.resolved_at else "UNKNOWN"),
        "requires_follow_up": bool(diagnostic.requires_follow_up),
        "repeat_issue": bool(diagnostic.repeat_issue),
        "diagnostic_duration_minutes": diagnostic.diagnostic_duration_minutes
        if diagnostic.diagnostic_duration_minutes is not None
        else "UNKNOWN",
        "performed_by": diagnostic.performed_by or "UNKNOWN",
    }

    # 3) Ticket object per spec
    ticket = result.ticket
    assigned_technician = ticket.assigned_technician
    ticket_parts = list(ticket.parts.all())
    ticket_obj = {
        "ticket_id": ticket.ticket_id or "UNKNOWN",
        "customer": getattr(ticket.customer, "id", None) or "UNKNOWN",
        "assigned_technician": getattr(assigned_technician, "id", None) or "UNASSIGNED",
        "specialization": _spec_specialization(ticket.specialization),
        "title": ticket.title or "UNKNOWN",
        "description": ticket.description or "UNKNOWN",
        "severity": _severity_label_from_int(ticket.severity),
        "status": _ticket_status_to_label(ticket.status),
        "customer_satisfaction_rating": (
            ticket.customer_satisfaction_rating
            if ticket.customer_satisfaction_rating is not None
            else "UNKNOWN"
        ),
        "estimated_resolution_time": (
            ticket.estimated_resolution_time_minutes
            if ticket.estimated_resolution_time_minutes is not None
            else "UNKNOWN"
        ),
        "actual_resolution_time_minutes": (
            ticket.actual_resolution_time_minutes
            if ticket.actual_resolution_time_minutes is not None
            else "UNKNOWN"
        ),
        "predicted_resolution_summary": ticket.predicted_resolution_summary or diagnostic_report["ai_summary"],
        "created_by": ticket.created_by or "UNKNOWN",
        "priority": _severity_label_from_int(ticket.priority),
        "parts_needed": [
            getattr(p, "part_number", None) or getattr(p, "name", None) or "UNKNOWN" for p in ticket_parts
        ]
        or [],
        "issue_description_summary": ticket.issue_description or ticket.description or "UNKNOWN",
        "assigned_at": ticket.assigned_at.isoformat() if ticket.assigned_at else "UNKNOWN",
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else "UNKNOWN",
        "close_at": ticket.closed_at.isoformat() if ticket.closed_at else "UNKNOWN",
    }

    # 4) Part Order Request (or Not Triggered)
    if result.orders:
        # For simplicity, return a list of part order requests
        part_orders = []
        for order in result.orders:
            part = order.part
            part_orders.append(
                {
                    "part_number": getattr(part, "part_number", None) or "UNKNOWN",
                    "part_quantity": order.quantity,
                    "reorder_threshold": part.reorder_threshold,
                    "status": "Submitted for admin",
                }
            )
        part_order_request: Any = part_orders
    else:
        part_order_request = {
            "status": "Not Triggered",
            "reason": "Inventory above reorder_threshold or no parts provided.",
        }

    return {
        "failure_detection_output": failure_detection_output,
        "diagnostic_report": diagnostic_report,
        "ticket": ticket_obj,
        "part_order_request": part_order_request,
    }

