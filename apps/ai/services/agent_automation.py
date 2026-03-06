import json
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.db import models
from django.utils import timezone

from apps.ai.models import AgentActionProposal, AgentExecutionTrace, McpAdapter
from apps.ai.services.mcp_client import McpClient, list_enabled_mcp_clients
from apps.diagnostics.models import DiagnosticReport
from apps.inventory.models import Part
from apps.technicians.models import TechnicianProfile
from apps.tickets.checklists import ensure_ticket_checklist, generate_ticket_checklist
from apps.tickets.id_generation import generate_ticket_id
from apps.tickets.models import Ticket


PART_KEYWORDS = {
    "injector": "Fuel Injector",
    "filter": "Oil Filter",
    "sensor": "Sensor",
    "alternator": "Alternator",
    "hose": "Hose",
}
ALLOWED_POLICY_MODES = {"manual", "semi_auto", "auto"}


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _looks_like_ticket_request(text: str) -> bool:
    checks = ["ticket", "issue", "fault", "breakdown", "create", "assign", "repair"]
    normalized = _normalized(text)
    # Exclude update requests from ticket creation
    update_checks = ["update", "change", "modify", "edit", "set status", "mark as", "close"]
    if any(token in normalized for token in update_checks):
        return False
    return any(token in normalized for token in checks)


def _looks_like_update_request(text: str) -> bool:
    """Detect if user wants to update an existing ticket."""
    update_checks = [
        "update", "change", "modify", "edit", "set status", "mark as",
        "close ticket", "resolve", "complete", "reassign", "change priority",
        "update description", "add notes", "change status"
    ]
    normalized = _normalized(text)
    return any(token in normalized for token in update_checks)


def _looks_like_inventory_query(text: str) -> bool:
    """Detect if user is asking about inventory/parts status."""
    inventory_checks = [
        "inventory", "stock", "parts available", "low stock", "reorder",
        "what parts", "show parts", "list parts", "check stock", "stock level",
        "how many", "in stock", "out of stock", "parts status", "inventory status",
        "need to order", "running low", "parts list"
    ]
    normalized = _normalized(text)
    return any(token in normalized for token in inventory_checks)


def _looks_like_order_request(text: str) -> bool:
    """Detect if user wants to order parts directly."""
    order_checks = [
        "order part", "order parts", "purchase", "buy", "restock",
        "place order", "create order", "need to order", "order more",
        "replenish", "get more"
    ]
    normalized = _normalized(text)
    # Must have order-related keyword AND part-related keyword
    has_order = any(token in normalized for token in order_checks)
    has_part = any(token in normalized for token in ["part", "parts", "injector", "filter", "sensor", "hose", "alternator", "pump", "valve"])
    return has_order or (has_part and "order" in normalized)


def _get_inventory_summary(query: str) -> str:
    """Generate inventory summary based on user query."""
    normalized = _normalized(query)

    # Check for low stock query
    if any(kw in normalized for kw in ["low stock", "reorder", "running low", "need to order"]):
        low_stock_parts = Part.objects.filter(
            quantity_available__lte=models.F("reorder_threshold")
        ).order_by("quantity_available")[:10]

        if not low_stock_parts:
            return "✅ **Inventory Status**: All parts are above reorder threshold. No immediate restocking needed."

        lines = ["⚠️ **Low Stock Alert** - Parts below reorder threshold:\n"]
        for part in low_stock_parts:
            status_icon = "🔴" if part.quantity_available == 0 else "🟡"
            lines.append(
                f"{status_icon} **{part.name}** ({part.part_number}): "
                f"{part.quantity_available} in stock (reorder at {part.reorder_threshold})"
            )
        lines.append("\n_Reply with 'Order [part name]' to create a purchase order._")
        return "\n".join(lines)

    # Check for specific part query
    for keyword, part_name in PART_KEYWORDS.items():
        if keyword in normalized:
            parts = Part.objects.filter(name__icontains=keyword)[:5]
            if parts:
                lines = [f"📦 **{part_name} Inventory**:\n"]
                for part in parts:
                    status = "✅" if part.quantity_available > part.reorder_threshold else "⚠️"
                    lines.append(f"{status} {part.name}: {part.quantity_available} available")
                return "\n".join(lines)

    # General inventory summary
    total_parts = Part.objects.count()
    low_stock_count = Part.objects.filter(
        quantity_available__lte=models.F("reorder_threshold")
    ).count()
    out_of_stock = Part.objects.filter(quantity_available=0).count()

    summary = f"""📊 **Inventory Summary**

• **Total Parts**: {total_parts}
• **Low Stock**: {low_stock_count} parts need reordering
• **Out of Stock**: {out_of_stock} parts

_Ask "show low stock parts" for details or "order [part name]" to restock._"""
    return summary


def _extract_part_from_query(query: str) -> Part | None:
    """Extract part reference from query text."""
    normalized = _normalized(query)

    # Check for part number pattern (e.g., PRT-001, 12345)
    part_num_match = re.search(r"\b(PRT[-]?\d+|\d{4,})\b", query, re.IGNORECASE)
    if part_num_match:
        part = Part.objects.filter(part_number__icontains=part_num_match.group(1)).first()
        if part:
            return part

    # Check for part name keywords
    for keyword, _ in PART_KEYWORDS.items():
        if keyword in normalized:
            part = Part.objects.filter(name__icontains=keyword).first()
            if part:
                return part

    # Try to find any mentioned part
    words = normalized.split()
    for word in words:
        if len(word) > 3:
            part = Part.objects.filter(
                models.Q(name__icontains=word) | models.Q(part_number__icontains=word)
            ).first()
            if part:
                return part

    return None


def _extract_quantity_from_query(query: str, default: int = 1) -> int:
    """Extract quantity from query text."""
    # Match patterns like "order 5", "buy 10", "5 units"
    qty_match = re.search(r"\b(\d+)\s*(?:unit|piece|part|pcs)?s?\b", query, re.IGNORECASE)
    if qty_match:
        qty = int(qty_match.group(1))
        return min(max(qty, 1), 100)  # Cap at 100
    return default


def _plan_order_from_query(
    query: str,
    context_payload: dict[str, Any],
    user,
    policy_mode: str,
) -> PlanningResult | None:
    """Create an order proposal from a direct order request."""
    part = _extract_part_from_query(query)

    if not part:
        return PlanningResult(
            proposals=[],
            mcp_reads=[],
            follow_up_question=(
                "I can help you order parts. Please specify which part you need. "
                "For example: 'Order 5 fuel injectors' or 'Restock part PRT-001'"
            ),
            missing_fields=["part_reference"],
        )

    quantity = _extract_quantity_from_query(query, default=max(1, part.reorder_threshold or 1))
    workflow_id = str(uuid.uuid4())
    normalized_policy_mode = _normalize_policy_mode(policy_mode)

    order_payload = {
        "workflow_id": workflow_id,
        "part_id": str(part.id),
        "part_number": part.part_number,
        "part_name": part.name,
        "quantity": quantity,
        "current_stock": part.quantity_available,
        "reorder_threshold": part.reorder_threshold,
        "unit_cost": float(part.cost_price) if part.cost_price else None,
        "estimated_total": float(part.cost_price * quantity) if part.cost_price else None,
        "supplier": part.supplier or "Default Supplier",
        "reason": f"User requested order: {query[:200]}",
    }

    proposal = AgentActionProposal.objects.create(
        action_type=AgentActionProposal.ACTION_ORDER_PART,
        status=AgentActionProposal.STATUS_PENDING,
        payload=order_payload,
        source_query=query,
        source_context=context_payload,
        created_by=user if getattr(user, "is_authenticated", False) else None,
        metadata=_proposal_metadata(
            action_type=AgentActionProposal.ACTION_ORDER_PART,
            workflow_id=workflow_id,
            query=query,
            context_payload=context_payload,
            policy_mode=normalized_policy_mode,
            intent="parts_ops",
            reason=f"User requested to order {quantity}x {part.name}",
            priority=2,
        ),
    )

    return PlanningResult(proposals=[proposal], mcp_reads=[])


def _extract_ticket_reference(text: str, context_payload: dict[str, Any]) -> str | None:
    """Extract ticket ID reference from text or context."""
    # Check context first for explicit ticket_id
    if isinstance(context_payload, dict):
        ticket_id = str(context_payload.get("ticket_id") or context_payload.get("ticket_ref") or "").strip()
        if ticket_id:
            return ticket_id

    normalized = text.strip()

    # Match full TK-XXXXXXXXXX-XXXX pattern (e.g., TK-0306173432-8812)
    tk_full_match = re.search(r"TK-\d+-\d+", normalized, re.IGNORECASE)
    if tk_full_match:
        return tk_full_match.group(0).upper()

    # Match shorter TK-xxx pattern (e.g., TK-001)
    tk_match = re.search(r"TK-\d+", normalized, re.IGNORECASE)
    if tk_match:
        return tk_match.group(0).upper()

    # Match "ticket #123" or "ticket 123" patterns
    ticket_num_match = re.search(r"ticket\s*#?(\d+)", normalized, re.IGNORECASE)
    if ticket_num_match:
        return f"TK-{ticket_num_match.group(1)}"

    # Check context_block for "Last referenced ticket: TK-xxx"
    if isinstance(context_payload, dict):
        context_block = str(context_payload.get("context_block") or "").strip()
        if context_block:
            last_ref_match = re.search(r"Last referenced ticket:\s*(TK-[\d-]+)", context_block, re.IGNORECASE)
            if last_ref_match:
                return last_ref_match.group(1).upper()

    return None


def _extract_update_fields(text: str, ticket: "Ticket") -> dict[str, Any]:
    """Extract fields to update from the user's request."""
    normalized = _normalized(text)
    updates: dict[str, Any] = {}

    # Status updates
    status_mappings = {
        ("close", "closed", "complete", "completed", "resolve", "resolved", "done", "finish", "finished"): "completed",
        ("in progress", "start", "working", "started", "begin"): "in_progress",
        ("pending", "wait", "waiting", "on hold"): "pending",
        ("assign", "assigned"): "assigned",
        ("cancel", "cancelled", "canceled"): "cancelled",
        ("awaiting parts", "waiting for parts", "needs parts"): "awaiting_parts",
    }
    for keywords, status_value in status_mappings.items():
        if any(kw in normalized for kw in keywords):
            updates["status"] = status_value
            break

    # Priority updates
    priority_mappings = {
        ("critical", "urgent", "asap", "emergency", "p1", "priority 1"): 4,
        ("high priority", "high", "important", "p2", "priority 2"): 3,
        ("medium priority", "medium", "normal", "p3", "priority 3"): 2,
        ("low priority", "low", "minor", "p4", "priority 4"): 1,
    }
    for keywords, priority_value in priority_mappings.items():
        if any(kw in normalized for kw in keywords):
            updates["priority"] = priority_value
            updates["severity"] = priority_value
            break

    # Description updates - look for quoted text or "description:" prefix
    desc_match = re.search(r'(?:description|notes?|details?)[\s:]+["\']?([^"\']+)["\']?', normalized, re.IGNORECASE)
    if desc_match:
        new_desc = desc_match.group(1).strip()
        if new_desc and len(new_desc) > 5:
            updates["description"] = new_desc

    return updates


def _derive_specialization(text: str) -> str:
    normalized = _normalized(text)
    if any(token in normalized for token in ["electrical", "wiring", "alternator", "battery"]):
        return "electrical"
    return "engine"


def _derive_priority(text: str) -> int:
    normalized = _normalized(text)
    if any(token in normalized for token in ["urgent", "critical", "immediate", "asap"]):
        return 4
    if any(token in normalized for token in ["high", "major"]):
        return 3
    if any(token in normalized for token in ["low", "minor"]):
        return 1
    return 2


def _extract_part_name(text: str) -> str:
    normalized = _normalized(text)
    for token, part_name in PART_KEYWORDS.items():
        if token in normalized:
            return part_name
    return "Fuel Injector"


def _normalize_policy_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_POLICY_MODES else "manual"


def _action_risk_level(action_type: str, priority: int) -> str:
    if action_type == AgentActionProposal.ACTION_ORDER_PART:
        return "high"
    if action_type == AgentActionProposal.ACTION_ASSIGN_EMPLOYEE:
        return "medium"
    if action_type == AgentActionProposal.ACTION_CREATE_TICKET:
        return "medium" if priority >= 3 else "low"
    if action_type == AgentActionProposal.ACTION_UPDATE_TICKET:
        # Status changes to completed/cancelled are higher risk
        return "low"
    return "medium"


def _requires_approval(
    *,
    policy_mode: str,
    action_type: str,
    risk_level: str,
    context_payload: dict[str, Any],
) -> bool:
    policy_rules = context_payload.get("policy_rules") if isinstance(context_payload, dict) else None
    if isinstance(policy_rules, dict):
        by_action = policy_rules.get("actions")
        if isinstance(by_action, dict):
            override = by_action.get(action_type)
            if isinstance(override, bool):
                return override
        by_risk = policy_rules.get("risk")
        if isinstance(by_risk, dict):
            override = by_risk.get(risk_level)
            if isinstance(override, bool):
                return override

    if policy_mode == "manual":
        return True
    if policy_mode == "semi_auto":
        return risk_level != "low"
    if policy_mode == "auto":
        return risk_level == "high"
    return True


def _proposal_metadata(
    *,
    action_type: str,
    workflow_id: str,
    query: str,
    context_payload: dict[str, Any],
    policy_mode: str,
    intent: str,
    reason: str,
    priority: int = 2,
) -> dict[str, Any]:
    risk_level = _action_risk_level(action_type, priority)
    requires_approval = _requires_approval(
        policy_mode=policy_mode,
        action_type=action_type,
        risk_level=risk_level,
        context_payload=context_payload,
    )
    return {
        "reason": reason,
        "agent_name": "langgraph_react_runtime",
        "policy_mode": policy_mode,
        "intent": intent,
        "risk_level": risk_level,
        "requires_approval": requires_approval,
        "context_refs": context_payload.get("context_refs", []),
        "idempotency_key": f"{workflow_id}:{action_type}:{_normalized(query)[:120]}",
    }


def _coerce_tool_result(result: dict[str, Any] | None) -> Any:
    if not isinstance(result, dict):
        return None
    payload = result.get("result")
    if isinstance(payload, dict):
        if "structuredContent" in payload:
            return payload.get("structuredContent")
        content = payload.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = str(item.get("text") or "").strip()
                    if not text:
                        continue
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
        return payload
    return payload


def _pick_connector(clients: list[McpClient], keywords: tuple[str, ...]) -> McpClient | None:
    for client in clients:
        haystack = f"{client.adapter.name} {client.adapter.base_url}"
        if any(keyword in _normalized(haystack) for keyword in keywords):
            return client
    return None


@dataclass
class PlanningResult:
    proposals: list[AgentActionProposal]
    mcp_reads: list[dict[str, Any]]
    follow_up_question: str = ""
    missing_fields: list[str] = None

    def __post_init__(self):
        if self.missing_fields is None:
            self.missing_fields = []


def _extract_missing_ticket_fields(query: str, context_payload: dict[str, Any]) -> list[str]:
    normalized = _normalized(query)
    missing: list[str] = []

    has_symptom = len(normalized.split()) >= 6 and any(
        token in normalized
        for token in (
            "fault",
            "code",
            "issue",
            "warning",
            "overheat",
            "leak",
            "noise",
            "pressure",
            "temperature",
            "smoke",
            "stall",
            "vibration",
            "misfire",
            "injector",
        )
    )
    if not has_symptom:
        missing.append("symptom_details")

    has_asset = bool(
        re.search(r"\b(unit|truck|asset|vehicle|engine)\b", normalized)
        or re.search(r"#?\d{3,}", normalized)
        or str(context_payload.get("station_id") or context_payload.get("asset_id") or "").strip()
    )
    if not has_asset:
        missing.append("asset_identifier")

    return missing


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    values: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            values.append(item.strip())
        elif isinstance(item, dict):
            text = str(item.get("name") or item.get("part_name") or "").strip()
            if text:
                values.append(text)
    return values


def _load_diagnostic_context(context_payload: dict[str, Any]) -> dict[str, Any]:
    report_id = str(
        context_payload.get("diagnostic_report_id")
        or context_payload.get("diagnostic_id")
        or ""
    ).strip()
    if report_id:
        report = DiagnosticReport.objects.filter(id=report_id).select_related("component").prefetch_related("parts").first()
        if report:
            return {
                "diagnostic_report_id": str(report.id),
                "specialization": str(report.specialization or ""),
                "component_name": str(getattr(report.component, "name", "") or ""),
                "fault_code": str(report.fault_code or ""),
                "issue": str(report.title or ""),
                "description": str(report.description or report.ai_summary or ""),
                "part_names": list(report.parts.values_list("name", flat=True)),
                "severity": int(report.severity or 2),
            }

    part_names = _coerce_string_list(
        context_payload.get("part_names")
        or context_payload.get("parts_affected")
        or context_payload.get("parts")
    )
    component_name = str(context_payload.get("component_name") or context_payload.get("component") or "").strip()
    issue = str(context_payload.get("issue") or "").strip()
    description = str(context_payload.get("description") or "").strip()
    fault_code = str(context_payload.get("fault_code") or "").strip()
    specialization = str(context_payload.get("specialization") or "").strip().lower()
    severity_raw = context_payload.get("severity")
    try:
        severity = int(float(severity_raw))
    except (TypeError, ValueError):
        severity = 0

    if not any([part_names, component_name, issue, description, fault_code]):
        return {}
    return {
        "diagnostic_report_id": "",
        "specialization": specialization,
        "component_name": component_name,
        "fault_code": fault_code,
        "issue": issue,
        "description": description,
        "part_names": part_names,
        "severity": severity,
    }


def _build_ticket_title_and_description(query: str, specialization: str, diagnostic_payload: dict[str, Any]) -> tuple[str, str]:
    payload = diagnostic_payload if isinstance(diagnostic_payload, dict) else {}
    component_name = str(payload.get("component_name") or "").strip()
    issue = str(payload.get("issue") or "").strip()
    fault_code = str(payload.get("fault_code") or "").strip()
    description = str(payload.get("description") or "").strip()
    part_names = _coerce_string_list(payload.get("part_names"))

    if component_name or issue or fault_code:
        summary_parts = [part for part in [component_name, issue or fault_code] if part]
        title = " - ".join(summary_parts)[:200] or f"{specialization.title()} service request"
    else:
        title = f"{specialization.title()} service request"

    details = [query.strip()]
    if description:
        details.append(description)
    if part_names:
        details.append(f"Affected parts: {', '.join(part_names[:6])}")
    ticket_description = "\n\n".join(part for part in details if part).strip()[:1000]
    return title, ticket_description


def _build_checklist_preview(query: str, specialization: str, diagnostic_payload: dict[str, Any] | None = None) -> list[str]:
    try:
        pseudo_ticket = Ticket(
            title=f"{specialization.title()} service request",
            description=query,
            issue_description=query,
            specialization=specialization,
        )
        generated = generate_ticket_checklist(pseudo_ticket, limit=4, diagnostic_payload=diagnostic_payload)
        preview = []
        for item in generated.get("template", [])[:5]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            if title:
                preview.append(title)
        return preview
    except Exception:
        return []


def plan_agent_actions(
    *,
    query: str,
    context_payload: dict[str, Any],
    selected_mcp_adapter_ids: list[str],
    user,
    policy_mode: str = "manual",
    intent: str = "qa",
    context_refs: list[str] | None = None,
) -> PlanningResult:
    proposals: list[AgentActionProposal] = []
    mcp_reads: list[dict[str, Any]] = []

    # Handle update ticket requests first
    if _looks_like_update_request(query):
        ticket_ref = _extract_ticket_reference(query, context_payload)
        if not ticket_ref:
            return PlanningResult(
                proposals=[],
                mcp_reads=[],
                follow_up_question="I can help update a ticket, but I need to know which ticket. Please provide the ticket ID (e.g., TK-001).",
                missing_fields=["ticket_reference"],
            )

        # Look up the ticket
        ticket = Ticket.objects.filter(ticket_id=ticket_ref).first()
        if not ticket:
            # Try by UUID
            try:
                ticket = Ticket.objects.filter(id=ticket_ref).first()
            except Exception:
                ticket = None

        if not ticket:
            return PlanningResult(
                proposals=[],
                mcp_reads=[],
                follow_up_question=f"I couldn't find ticket {ticket_ref}. Please verify the ticket ID and try again.",
                missing_fields=["valid_ticket_reference"],
            )

        # Extract what to update
        updates = _extract_update_fields(query, ticket)
        if not updates:
            return PlanningResult(
                proposals=[],
                mcp_reads=[],
                follow_up_question=f"I found ticket {ticket.ticket_id}, but I'm not sure what to update. Please specify what you'd like to change (e.g., status, priority, description).",
                missing_fields=["update_fields"],
            )

        workflow_id = str(uuid.uuid4())
        normalized_policy_mode = _normalize_policy_mode(policy_mode or context_payload.get("policy_mode"))
        normalized_intent = str(intent or context_payload.get("intent") or "update").strip().lower() or "update"

        update_payload = {
            "workflow_id": workflow_id,
            "ticket_id": str(ticket.id),
            "ticket_ref": ticket.ticket_id,
            "reason": f"User requested update: {query[:200]}",
            "updates": updates,
            "current_values": {
                "status": ticket.status,
                "priority": ticket.priority,
                "severity": ticket.severity,
                "description": ticket.description[:200] if ticket.description else "",
            },
        }

        proposals.append(
            AgentActionProposal.objects.create(
                action_type=AgentActionProposal.ACTION_UPDATE_TICKET,
                status=AgentActionProposal.STATUS_PENDING,
                payload=update_payload,
                source_query=query,
                source_context=context_payload,
                created_by=user if getattr(user, "is_authenticated", False) else None,
                metadata=_proposal_metadata(
                    action_type=AgentActionProposal.ACTION_UPDATE_TICKET,
                    workflow_id=workflow_id,
                    query=query,
                    context_payload=context_payload,
                    policy_mode=normalized_policy_mode,
                    intent=normalized_intent,
                    reason=f"User requested to update ticket {ticket.ticket_id}.",
                    priority=ticket.priority or 2,
                ),
            )
        )

        return PlanningResult(proposals=proposals, mcp_reads=mcp_reads)

    # Handle inventory queries
    if _looks_like_inventory_query(query):
        inventory_data = _get_inventory_summary(query)
        # Return inventory info as a follow-up (no proposal needed for read-only queries)
        return PlanningResult(
            proposals=[],
            mcp_reads=[],
            follow_up_question=inventory_data,
            missing_fields=[],
        )

    # Handle direct order requests
    if _looks_like_order_request(query):
        order_result = _plan_order_from_query(query, context_payload, user, policy_mode)
        if order_result:
            return order_result

    if not _looks_like_ticket_request(query):
        return PlanningResult(proposals=proposals, mcp_reads=mcp_reads, follow_up_question="", missing_fields=[])

    diagnostic_payload = _load_diagnostic_context(context_payload)
    specialization = str(diagnostic_payload.get("specialization") or _derive_specialization(query)).strip().lower() or "engine"
    if specialization not in {"engine", "electrical"}:
        specialization = _derive_specialization(query)
    priority = int(diagnostic_payload.get("severity") or 0) or _derive_priority(query)
    priority = min(max(priority, 1), 4)
    workflow_id = str(uuid.uuid4())
    normalized_policy_mode = _normalize_policy_mode(policy_mode or context_payload.get("policy_mode"))
    normalized_intent = str(intent or context_payload.get("intent") or "qa").strip().lower() or "qa"
    if context_refs and "context_refs" not in context_payload:
        context_payload["context_refs"] = context_refs
    missing_fields = [] if diagnostic_payload.get("diagnostic_report_id") else _extract_missing_ticket_fields(query, context_payload)
    if missing_fields:
        questions = []
        if "symptom_details" in missing_fields:
            questions.append("the specific symptom or fault code")
        if "asset_identifier" in missing_fields:
            questions.append("the unit/asset identifier or location")
        joined = " and ".join(questions)
        follow_up = (
            f"I can prepare the ticket, but I need {joined} first. "
            "Reply with those details and I will draft it for confirmation."
        )
        return PlanningResult(
            proposals=proposals,
            mcp_reads=mcp_reads,
            follow_up_question=follow_up,
            missing_fields=missing_fields,
        )

    clients = list_enabled_mcp_clients(selected_mcp_adapter_ids)
    supply_client = _pick_connector(clients, ("supply", "parts", "inventory"))
    employee_client = _pick_connector(clients, ("employee", "workforce", "technician"))
    ticketing_client = _pick_connector(clients, ("ticket", "dispatch", "workorder"))

    read_context: dict[str, Any] = {}
    if supply_client:
        read_result = supply_client.call_tool("search_parts", {"query": query, "limit": 5})
        mcp_reads.append(
            {
                "adapter": supply_client.adapter.name,
                "tool": "search_parts",
                "ok": read_result.ok,
                "status_code": read_result.status_code,
                "duration_ms": read_result.duration_ms,
                "error": read_result.error,
            }
        )
        read_context["parts"] = _coerce_tool_result(read_result.data)

    if employee_client:
        read_result = employee_client.call_tool(
            "search_employees",
            {
                "specialization": specialization,
                "status": "available",
            },
        )
        mcp_reads.append(
            {
                "adapter": employee_client.adapter.name,
                "tool": "search_employees",
                "ok": read_result.ok,
                "status_code": read_result.status_code,
                "duration_ms": read_result.duration_ms,
                "error": read_result.error,
            }
        )
        read_context["employees"] = _coerce_tool_result(read_result.data)

    ticket_title, ticket_description = _build_ticket_title_and_description(query, specialization, diagnostic_payload)
    create_ticket_payload = {
        "workflow_id": workflow_id,
        "title": ticket_title,
        "description": ticket_description,
        "issue_description": str(diagnostic_payload.get("issue") or query).strip()[:1000],
        "specialization": specialization,
        "priority": priority,
        "severity": min(max(priority, 1), 4),
        "station_hint": str(context_payload.get("station_id") or context_payload.get("location") or ""),
        "mcp_adapter_id": ticketing_client.adapter.id if ticketing_client else None,
        "diagnostic_report_id": str(diagnostic_payload.get("diagnostic_report_id") or ""),
        "diagnostic_payload": diagnostic_payload,
        "missing_fields": [],
        "checklist_preview": _build_checklist_preview(query, specialization, diagnostic_payload),
        "context": read_context,
    }
    proposals.append(
        AgentActionProposal.objects.create(
            action_type=AgentActionProposal.ACTION_CREATE_TICKET,
            status=AgentActionProposal.STATUS_PENDING,
            payload=create_ticket_payload,
            source_query=query,
            source_context=context_payload,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            metadata=_proposal_metadata(
                action_type=AgentActionProposal.ACTION_CREATE_TICKET,
                workflow_id=workflow_id,
                query=query,
                context_payload=context_payload,
                policy_mode=normalized_policy_mode,
                intent=normalized_intent,
                reason="Detected ticket-worthy issue from user request.",
                priority=priority,
            ),
        )
    )

    assignment_payload = {
        "workflow_id": workflow_id,
        "specialization": specialization,
        "station_hint": str(context_payload.get("station_id") or context_payload.get("location") or ""),
        "ticket_workflow_ref": "pending_create_ticket",
        "mcp_adapter_id": employee_client.adapter.id if employee_client else None,
        "context": read_context,
    }
    proposals.append(
        AgentActionProposal.objects.create(
            action_type=AgentActionProposal.ACTION_ASSIGN_EMPLOYEE,
            status=AgentActionProposal.STATUS_PENDING,
            payload=assignment_payload,
            source_query=query,
            source_context=context_payload,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            metadata=_proposal_metadata(
                action_type=AgentActionProposal.ACTION_ASSIGN_EMPLOYEE,
                workflow_id=workflow_id,
                query=query,
                context_payload=context_payload,
                policy_mode=normalized_policy_mode,
                intent=normalized_intent,
                reason="Assignment required for faster dispatch.",
                priority=priority,
            ),
        )
    )

    diagnostic_parts = _coerce_string_list(diagnostic_payload.get("part_names"))
    part_name = diagnostic_parts[0] if diagnostic_parts else _extract_part_name(query)
    try:
        local_part = Part.objects.filter(name__icontains=part_name).order_by("name").first()
    except Exception:
        local_part = None

    needs_external_order = local_part is None or int(local_part.quantity_available or 0) <= int(local_part.reorder_threshold or 0)
    if needs_external_order:
        order_payload = {
            "workflow_id": workflow_id,
            "part_name": local_part.name if local_part else part_name,
            "part_id": str(local_part.id) if local_part else "",
            "quantity": max(1, int((local_part.reorder_threshold if local_part else 2) or 2)),
            "ship_to_station_id": str(context_payload.get("station_id") or ""),
            "ticket_workflow_ref": "pending_create_ticket",
            "mcp_adapter_id": supply_client.adapter.id if supply_client else None,
            "context": read_context,
        }
        proposals.append(
            AgentActionProposal.objects.create(
                action_type=AgentActionProposal.ACTION_ORDER_PART,
                status=AgentActionProposal.STATUS_PENDING,
                payload=order_payload,
                source_query=query,
                source_context=context_payload,
                created_by=user if getattr(user, "is_authenticated", False) else None,
                metadata=_proposal_metadata(
                    action_type=AgentActionProposal.ACTION_ORDER_PART,
                    workflow_id=workflow_id,
                    query=query,
                    context_payload=context_payload,
                    policy_mode=normalized_policy_mode,
                    intent=normalized_intent,
                    reason="Local inventory appears insufficient for requested repair.",
                    priority=priority,
                ),
            )
        )

    return PlanningResult(proposals=proposals, mcp_reads=mcp_reads)


def _log_trace(
    *,
    proposal: AgentActionProposal,
    stage: str,
    adapter: McpAdapter | None,
    tool_name: str,
    ok: bool,
    status_code: int,
    duration_ms: int,
    request_payload: dict[str, Any] | None,
    response_payload: dict[str, Any] | None,
    error: str,
):
    AgentExecutionTrace.objects.create(
        proposal=proposal,
        stage=stage,
        adapter=adapter,
        tool_name=tool_name,
        ok=ok,
        status_code=status_code,
        duration_ms=duration_ms,
        request_payload=request_payload or {},
        response_payload=response_payload or {},
        error=error,
    )


def _find_best_local_technician(specialization: str) -> TechnicianProfile | None:
    techs = TechnicianProfile.objects.filter(
        specialization=specialization,
        status="available",
    ).order_by("-performance_rating", "-total_years_experience", "profile__user__username")
    return techs.first()


def _resolve_workflow_ticket(proposal: AgentActionProposal) -> Ticket | None:
    payload = proposal.payload if isinstance(proposal.payload, dict) else {}
    direct_ticket_id = str(payload.get("ticket_id") or "").strip()
    if direct_ticket_id:
        by_ref = Ticket.objects.filter(ticket_id=direct_ticket_id).first()
        if by_ref:
            return by_ref
        try:
            return Ticket.objects.filter(id=direct_ticket_id).first()
        except Exception:
            return None

    workflow_id = str(payload.get("workflow_id") or "").strip()
    if not workflow_id:
        return None

    create_proposal = (
        AgentActionProposal.objects.filter(
            action_type=AgentActionProposal.ACTION_CREATE_TICKET,
            status=AgentActionProposal.STATUS_EXECUTED,
            payload__workflow_id=workflow_id,
        )
        .order_by("-executed_at")
        .first()
    )
    if not create_proposal or not isinstance(create_proposal.result, dict):
        return None

    created_ticket_uuid = str(create_proposal.result.get("local_ticket_uuid") or "").strip()
    created_ticket_ref = str(create_proposal.result.get("local_ticket_id") or "").strip()
    if created_ticket_uuid:
        ticket = Ticket.objects.filter(id=created_ticket_uuid).first()
        if ticket:
            return ticket
    if created_ticket_ref:
        return Ticket.objects.filter(ticket_id=created_ticket_ref).first()
    return None


def _ensure_workflow_ticket(proposal: AgentActionProposal, actor) -> Ticket | None:
    ticket = _resolve_workflow_ticket(proposal)
    if ticket:
        return ticket

    payload = proposal.payload if isinstance(proposal.payload, dict) else {}
    workflow_id = str(payload.get("workflow_id") or "").strip()
    if not workflow_id:
        return None

    create_proposal = (
        AgentActionProposal.objects.filter(
            action_type=AgentActionProposal.ACTION_CREATE_TICKET,
            payload__workflow_id=workflow_id,
        )
        .exclude(id=proposal.id)
        .order_by("created_at")
        .first()
    )
    if not create_proposal:
        return None

    if create_proposal.status != AgentActionProposal.STATUS_EXECUTED:
        if create_proposal.status == AgentActionProposal.STATUS_PENDING:
            create_proposal.status = AgentActionProposal.STATUS_APPROVED
            create_proposal.approved_by = actor if getattr(actor, "is_authenticated", False) else create_proposal.approved_by
            create_proposal.approved_at = timezone.now()
            create_proposal.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        execute_agent_action(
            create_proposal,
            actor=actor,
            execution_overrides={"trigger": "workflow_dependency"},
        )
    return _resolve_workflow_ticket(proposal)


def execute_agent_action(
    proposal: AgentActionProposal,
    *,
    actor,
    execution_overrides: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> AgentActionProposal:
    if proposal.status not in {
        AgentActionProposal.STATUS_PENDING,
        AgentActionProposal.STATUS_APPROVED,
        AgentActionProposal.STATUS_FAILED,
    }:
        return proposal

    metadata = proposal.metadata if isinstance(proposal.metadata, dict) else {}
    metadata_changed = False
    if isinstance(execution_overrides, dict) and execution_overrides:
        metadata["execution_overrides"] = execution_overrides
        metadata_changed = True
    if isinstance(idempotency_key, str) and idempotency_key.strip():
        metadata["idempotency_key"] = idempotency_key.strip()
        metadata_changed = True

    requires_approval = bool(metadata.get("requires_approval", True))
    if requires_approval and proposal.status != AgentActionProposal.STATUS_APPROVED:
        proposal.error = "Approval required before execution."
        if metadata_changed:
            proposal.metadata = metadata
            proposal.save(update_fields=["error", "metadata", "updated_at"])
        else:
            proposal.save(update_fields=["error", "updated_at"])
        return proposal

    idem_key = str(metadata.get("idempotency_key") or "").strip()
    if idem_key:
        existing = (
            AgentActionProposal.objects.filter(
                action_type=proposal.action_type,
                status=AgentActionProposal.STATUS_EXECUTED,
                metadata__idempotency_key=idem_key,
            )
            .exclude(id=proposal.id)
            .order_by("-executed_at")
            .first()
        )
        if existing:
            proposal.status = AgentActionProposal.STATUS_EXECUTED
            proposal.executed_at = timezone.now()
            proposal.approved_by = actor if getattr(actor, "is_authenticated", False) else proposal.approved_by
            if proposal.approved_at is None:
                proposal.approved_at = timezone.now()
            proposal.error = ""
            proposal.result = {
                "idempotent_reuse": True,
                "reused_proposal_id": existing.id,
                "reused_result": existing.result if isinstance(existing.result, dict) else {},
            }
            if metadata_changed:
                proposal.metadata = metadata
                proposal.save(
                    update_fields=[
                        "status",
                        "result",
                        "executed_at",
                        "approved_by",
                        "approved_at",
                        "error",
                        "metadata",
                        "updated_at",
                    ]
                )
            else:
                proposal.save(update_fields=["status", "result", "executed_at", "approved_by", "approved_at", "error", "updated_at"])
            return proposal

    payload = proposal.payload if isinstance(proposal.payload, dict) else {}
    adapter_id = payload.get("mcp_adapter_id")
    adapter = McpAdapter.objects.filter(id=adapter_id).first() if adapter_id else None

    try:
        if proposal.action_type == AgentActionProposal.ACTION_CREATE_TICKET:
            title = str(payload.get("title") or "Service ticket").strip()[:200]
            description = str(payload.get("description") or "")
            issue_description = str(payload.get("issue_description") or description)
            specialization = str(payload.get("specialization") or "engine").strip().lower() or "engine"
            if specialization not in {"engine", "electrical"}:
                specialization = "engine"
            priority = int(payload.get("priority") or 2)
            severity = min(max(priority, 1), 4)
            diagnostic_report_id = str(payload.get("diagnostic_report_id") or "").strip()
            diagnostic_payload = payload.get("diagnostic_payload") if isinstance(payload.get("diagnostic_payload"), dict) else {}

            ticket = Ticket.objects.create(
                ticket_id=generate_ticket_id(),
                title=title,
                description=description,
                issue_description=issue_description,
                specialization=specialization,
                priority=priority,
                severity=severity,
                status="pending",
                created_by=getattr(actor, "username", "agent"),
                estimated_resolution_time_minutes=90,
            )
            linked_diagnostic_id = ""
            if diagnostic_report_id:
                report = DiagnosticReport.objects.filter(id=diagnostic_report_id).first()
                if report:
                    report.ticket_id = ticket
                    report.save(update_fields=["ticket_id"])
                    linked_diagnostic_id = str(report.id)
                    report_parts = list(report.parts.all())
                    if report_parts:
                        ticket.parts.set(report_parts)
                    if not diagnostic_payload:
                        diagnostic_payload = {
                            "diagnostic_report_id": linked_diagnostic_id,
                            "specialization": str(report.specialization or ""),
                            "component_name": str(getattr(report.component, "name", "") if report.component_id else ""),
                            "fault_code": str(report.fault_code or ""),
                            "issue": str(report.title or ""),
                            "description": str(report.description or report.ai_summary or ""),
                            "part_names": list(report.parts.values_list("name", flat=True)),
                        }
            elif isinstance(diagnostic_payload, dict):
                part_names = _coerce_string_list(diagnostic_payload.get("part_names"))
                if part_names:
                    matched_parts = list(Part.objects.filter(name__in=part_names))
                    if matched_parts:
                        ticket.parts.set(matched_parts)

            ensure_ticket_checklist(ticket, diagnostic_payload=diagnostic_payload)

            external_result: dict[str, Any] = {}
            if adapter:
                client = McpClient(adapter)
                tool_args = {
                    "title": title,
                    "description": description,
                    "specialization": specialization,
                    "priority": priority,
                    "station_id": str(payload.get("station_hint") or ""),
                }
                rpc_result = client.call_tool("create_ticket", tool_args)
                _log_trace(
                    proposal=proposal,
                    stage="execution",
                    adapter=adapter,
                    tool_name="create_ticket",
                    ok=rpc_result.ok,
                    status_code=rpc_result.status_code,
                    duration_ms=rpc_result.duration_ms,
                    request_payload=tool_args,
                    response_payload=rpc_result.data,
                    error=rpc_result.error,
                )
                external_result = _coerce_tool_result(rpc_result.data) if rpc_result.ok else {"error": rpc_result.error}

            proposal.result = {
                "local_ticket_uuid": str(ticket.id),
                "local_ticket_id": ticket.ticket_id,
                "diagnostic_report_id": linked_diagnostic_id or diagnostic_report_id,
                "external": external_result,
            }

        elif proposal.action_type == AgentActionProposal.ACTION_ASSIGN_EMPLOYEE:
            ticket = _ensure_workflow_ticket(proposal, actor)
            if not ticket:
                raise ValueError("No executable ticket context found for assignment.")

            specialization = str(payload.get("specialization") or ticket.specialization or "engine")
            local_pick = _find_best_local_technician(specialization)

            external_result: dict[str, Any] = {}
            if adapter:
                client = McpClient(adapter)
                search_args = {
                    "specialization": specialization,
                    "status": "available",
                    "station_id": str(payload.get("station_hint") or ""),
                }
                search_result = client.call_tool("search_employees", search_args)
                _log_trace(
                    proposal=proposal,
                    stage="execution",
                    adapter=adapter,
                    tool_name="search_employees",
                    ok=search_result.ok,
                    status_code=search_result.status_code,
                    duration_ms=search_result.duration_ms,
                    request_payload=search_args,
                    response_payload=search_result.data,
                    error=search_result.error,
                )
                external_result = _coerce_tool_result(search_result.data) if search_result.ok else {"error": search_result.error}

            if local_pick:
                ticket.assigned_technician = local_pick
                ticket.auto_assigned = True
                ticket.status = "assigned"
                ticket.assigned_at = timezone.now()
                ticket.save(update_fields=["assigned_technician", "auto_assigned", "status", "assigned_at"])

            proposal.result = {
                "ticket_id": ticket.ticket_id,
                "local_employee": {
                    "id": str(local_pick.id),
                    "name": local_pick.profile.user.get_full_name() or local_pick.profile.user.username,
                }
                if local_pick
                else None,
                "external": external_result,
            }

        elif proposal.action_type == AgentActionProposal.ACTION_UPDATE_TICKET:
            # Update an existing ticket
            ticket_id = str(payload.get("ticket_id") or "").strip()
            ticket_ref = str(payload.get("ticket_ref") or "").strip()

            ticket = None
            if ticket_id:
                try:
                    ticket = Ticket.objects.filter(id=ticket_id).first()
                except Exception:
                    pass
            if not ticket and ticket_ref:
                ticket = Ticket.objects.filter(ticket_id=ticket_ref).first()

            if not ticket:
                raise ValueError(f"Ticket not found: {ticket_ref or ticket_id}")

            updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else {}

            # Apply updates
            updated_fields = []
            if "status" in updates:
                old_status = ticket.status
                ticket.status = str(updates["status"])
                updated_fields.append("status")
                # Update timestamps based on status change
                if ticket.status == "completed" and old_status != "completed":
                    ticket.resolved_at = timezone.now()
                    updated_fields.append("resolved_at")
                elif ticket.status == "closed" and old_status != "closed":
                    ticket.closed_at = timezone.now()
                    updated_fields.append("closed_at")

            if "priority" in updates:
                ticket.priority = int(updates["priority"])
                updated_fields.append("priority")

            if "severity" in updates:
                ticket.severity = int(updates["severity"])
                updated_fields.append("severity")

            if "description" in updates:
                ticket.description = str(updates["description"])
                updated_fields.append("description")

            if updated_fields:
                ticket.save(update_fields=updated_fields)

            proposal.result = {
                "local_ticket_uuid": str(ticket.id),
                "local_ticket_id": ticket.ticket_id,
                "updated_fields": updated_fields,
                "updates_applied": updates,
            }

        elif proposal.action_type == AgentActionProposal.ACTION_ORDER_PART:
            ticket = _ensure_workflow_ticket(proposal, actor)
            adapter_result: dict[str, Any] = {}
            if adapter:
                client = McpClient(adapter)
                order_args = {
                    "part_number": str(payload.get("part_name") or "generic-part"),
                    "quantity": int(payload.get("quantity") or 1),
                    "ship_to_station_id": str(payload.get("ship_to_station_id") or ""),
                    "requested_by": getattr(actor, "username", "agent"),
                    "reason": "Auto-proposed from Fix it Felix",
                }
                rpc_result = client.call_tool("create_external_order", order_args)
                _log_trace(
                    proposal=proposal,
                    stage="execution",
                    adapter=adapter,
                    tool_name="create_external_order",
                    ok=rpc_result.ok,
                    status_code=rpc_result.status_code,
                    duration_ms=rpc_result.duration_ms,
                    request_payload=order_args,
                    response_payload=rpc_result.data,
                    error=rpc_result.error,
                )
                adapter_result = _coerce_tool_result(rpc_result.data) if rpc_result.ok else {"error": rpc_result.error}

            if ticket:
                ticket.status = "awaiting_parts"
                ticket.save(update_fields=["status"])

            proposal.result = {
                "part": str(payload.get("part_name") or ""),
                "quantity": int(payload.get("quantity") or 1),
                "ticket_id": ticket.ticket_id if ticket else "",
                "external": adapter_result,
            }

        proposal.status = AgentActionProposal.STATUS_EXECUTED
        proposal.executed_at = timezone.now()
        proposal.approved_by = actor if getattr(actor, "is_authenticated", False) else proposal.approved_by
        if proposal.approved_at is None:
            proposal.approved_at = timezone.now()
        proposal.error = ""
        if metadata_changed:
            proposal.metadata = metadata
            proposal.save(
                update_fields=["status", "result", "executed_at", "approved_by", "approved_at", "error", "metadata", "updated_at"]
            )
        else:
            proposal.save(update_fields=["status", "result", "executed_at", "approved_by", "approved_at", "error", "updated_at"])
        return proposal

    except Exception as exc:
        proposal.status = AgentActionProposal.STATUS_FAILED
        proposal.error = str(exc)
        proposal.executed_at = timezone.now()
        proposal.save(update_fields=["status", "error", "executed_at", "updated_at"])
        return proposal


def approve_agent_action(
    proposal: AgentActionProposal,
    *,
    actor,
    execution_overrides: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> AgentActionProposal:
    proposal.status = AgentActionProposal.STATUS_APPROVED
    proposal.approved_by = actor if getattr(actor, "is_authenticated", False) else proposal.approved_by
    proposal.approved_at = timezone.now()
    proposal.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return execute_agent_action(
        proposal,
        actor=actor,
        execution_overrides=execution_overrides,
        idempotency_key=idempotency_key,
    )


def reject_agent_action(proposal: AgentActionProposal, *, actor, reason: str = "") -> AgentActionProposal:
    proposal.status = AgentActionProposal.STATUS_REJECTED
    proposal.approved_by = actor if getattr(actor, "is_authenticated", False) else proposal.approved_by
    proposal.approved_at = timezone.now()
    proposal.error = str(reason or "Rejected by reviewer.")[:500]
    proposal.save(update_fields=["status", "approved_by", "approved_at", "error", "updated_at"])
    return proposal
