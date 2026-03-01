import json
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.ai.models import AgentActionProposal, AgentExecutionTrace, McpAdapter
from apps.ai.services.mcp_client import McpClient, list_enabled_mcp_clients
from apps.inventory.models import Part
from apps.technicians.models import TechnicianProfile
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
    return any(token in normalized for token in checks)


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

    if not _looks_like_ticket_request(query):
        return PlanningResult(proposals=proposals, mcp_reads=mcp_reads)

    specialization = _derive_specialization(query)
    priority = _derive_priority(query)
    workflow_id = str(uuid.uuid4())
    normalized_policy_mode = _normalize_policy_mode(policy_mode or context_payload.get("policy_mode"))
    normalized_intent = str(intent or context_payload.get("intent") or "qa").strip().lower() or "qa"
    if context_refs and "context_refs" not in context_payload:
        context_payload["context_refs"] = context_refs

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

    ticket_title = f"{specialization.title()} service request"
    ticket_description = query.strip()[:1000]
    create_ticket_payload = {
        "workflow_id": workflow_id,
        "title": ticket_title,
        "description": ticket_description,
        "specialization": specialization,
        "priority": priority,
        "station_hint": str(context_payload.get("station_id") or context_payload.get("location") or ""),
        "mcp_adapter_id": ticketing_client.adapter.id if ticketing_client else None,
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

    part_name = _extract_part_name(query)
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


def _ensure_ticket_id() -> str:
    prefix = timezone.now().strftime("%m%d")
    return f"TK-{prefix}-{timezone.now().strftime('%H%M%S')}"


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
            specialization = str(payload.get("specialization") or "engine")
            priority = int(payload.get("priority") or 2)
            severity = min(max(priority, 1), 4)

            ticket = Ticket.objects.create(
                ticket_id=_ensure_ticket_id(),
                title=title,
                description=description,
                specialization=specialization,
                priority=priority,
                severity=severity,
                status="pending",
                created_by=getattr(actor, "username", "agent"),
                estimated_resolution_time_minutes=90,
            )

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
