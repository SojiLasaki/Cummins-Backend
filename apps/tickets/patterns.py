from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from django.utils import timezone

from apps.tickets.models import Ticket, TicketResolutionPattern


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _tokenize(value: Any) -> set[str]:
    return set(TOKEN_PATTERN.findall(_normalize_text(value)))


def _normalize_part_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _normalize_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _diagnostic_payload_parts(diagnostic_payload: dict[str, Any]) -> list[str]:
    for key in ("part_names", "parts", "parts_affected"):
        raw = diagnostic_payload.get(key)
        if isinstance(raw, list):
            values: list[str] = []
            for item in raw:
                if isinstance(item, str):
                    values.append(item)
                elif isinstance(item, dict):
                    values.append(str(item.get("name") or item.get("part_name") or ""))
            return _normalize_part_list(values)
    return []


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def build_ticket_signature(ticket: Ticket, diagnostic_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = diagnostic_payload if isinstance(diagnostic_payload, dict) else {}
    component_name = _normalize_text(payload.get("component_name") or payload.get("component") or "")
    fault_code = _normalize_text(payload.get("fault_code") or "")
    issue_text = _normalize_text(
        payload.get("issue")
        or payload.get("description")
        or ticket.issue_description
        or ticket.description
        or ticket.title
        or ""
    )

    specialization = _normalize_text(payload.get("specialization") or ticket.specialization or "engine")
    if specialization not in {"engine", "electrical"}:
        specialization = "engine"

    parts_signature = _diagnostic_payload_parts(payload)
    if not parts_signature and getattr(ticket, "pk", None):
        try:
            parts_signature = _normalize_part_list(list(ticket.parts.values_list("name", flat=True)))
        except Exception:
            parts_signature = []

    signature = {
        "specialization": specialization,
        "component_name": component_name,
        "fault_code": fault_code,
        "issue_text": issue_text,
        "issue_tokens": sorted(_tokenize(issue_text)),
        "parts_signature": parts_signature,
    }
    return signature


def signature_hash(signature: dict[str, Any]) -> str:
    payload = json.dumps(signature, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def pattern_match_score(signature: dict[str, Any], pattern: TicketResolutionPattern) -> float:
    score = 0.0
    pattern_specialization = _normalize_text(pattern.specialization)
    if pattern_specialization == _normalize_text(signature.get("specialization")):
        score += 0.35

    component = _normalize_text(signature.get("component_name"))
    pattern_component = _normalize_text(pattern.component_name)
    if component and pattern_component:
        if component == pattern_component:
            score += 0.2
        elif _jaccard(_tokenize(component), _tokenize(pattern_component)) >= 0.5:
            score += 0.1

    fault_code = _normalize_text(signature.get("fault_code"))
    pattern_fault = _normalize_text(pattern.fault_code)
    if fault_code and pattern_fault and fault_code == pattern_fault:
        score += 0.2

    score += 0.15 * _jaccard(
        set(_normalize_part_list(signature.get("parts_signature", []))),
        set(_normalize_part_list(pattern.parts_signature)),
    )
    score += 0.1 * _jaccard(
        set(signature.get("issue_tokens") or []),
        set(pattern.issue_tokens or []),
    )
    return min(score, 1.0)


def find_best_patterns(
    signature: dict[str, Any],
    *,
    top_k: int = 3,
    min_score: float = 0.35,
) -> list[dict[str, Any]]:
    specialization = _normalize_text(signature.get("specialization") or "engine")
    rows = TicketResolutionPattern.objects.filter(specialization=specialization).order_by("-success_count", "-updated_at")
    scored: list[dict[str, Any]] = []
    for row in rows[:80]:
        score = pattern_match_score(signature, row)
        if score < min_score:
            continue
        scored.append({"pattern": row, "score": round(score, 4)})
    scored.sort(key=lambda item: (item["score"], item["pattern"].success_count, item["pattern"].updated_at), reverse=True)
    return scored[: max(1, top_k)]


def _coerce_checklist_template(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    template: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        step_id = str(row.get("id") or "").strip()
        title = str(row.get("title") or "").strip()
        if not step_id or not title:
            continue
        template.append(
            {
                "id": step_id,
                "category": str(row.get("category") or "repair").strip().lower() or "repair",
                "title": title,
                "instructions": str(row.get("instructions") or "").strip(),
                "required": bool(row.get("required", True)),
            }
        )
    return template


def upsert_pattern_from_completed_ticket(ticket: Ticket) -> TicketResolutionPattern | None:
    if str(ticket.status or "").strip().lower() != "completed":
        return None

    template = _coerce_checklist_template(ticket.checklist_template)
    if not template:
        return None

    progress = ticket.checklist_progress if isinstance(ticket.checklist_progress, list) else []
    progress_by_item = {
        str(item.get("item_id") or "").strip(): bool(item.get("done", False))
        for item in progress
        if isinstance(item, dict) and str(item.get("item_id") or "").strip()
    }
    successful_steps: list[dict[str, Any]] = []
    for step in template:
        step_id = str(step.get("id") or "")
        done = progress_by_item.get(step_id, False)
        if done or bool(step.get("required", True)):
            enriched = dict(step)
            enriched["done"] = done
            successful_steps.append(enriched)
    if len(successful_steps) < 2:
        successful_steps = template[: min(len(template), 6)]

    diagnostic_payload = {}
    latest_report = ticket.diagnostic_reports.order_by("-created_at").first()
    if latest_report:
        diagnostic_payload = {
            "specialization": latest_report.specialization,
            "component_name": getattr(latest_report.component, "name", "") if latest_report.component_id else "",
            "fault_code": latest_report.fault_code,
            "issue": latest_report.title or latest_report.description or "",
            "description": latest_report.description or "",
            "part_names": list(latest_report.parts.values_list("name", flat=True)),
        }

    signature = build_ticket_signature(ticket, diagnostic_payload=diagnostic_payload)
    hashed = signature_hash(signature)

    evidence = {
        "source_ticket_ids": [str(ticket.id)],
        "source_ticket_refs": [str(ticket.ticket_id or "")],
        "last_ticket_title": str(ticket.title or ""),
        "last_ticket_completed_at": timezone.now().isoformat(),
    }

    pattern, created = TicketResolutionPattern.objects.get_or_create(
        signature_hash=hashed,
        defaults={
            "specialization": signature["specialization"],
            "component_name": signature["component_name"],
            "fault_code": signature["fault_code"],
            "issue_text": signature["issue_text"],
            "issue_tokens": signature["issue_tokens"],
            "parts_signature": signature["parts_signature"],
            "checklist_template": successful_steps,
            "evidence": evidence,
            "success_count": 1,
            "last_used_at": timezone.now(),
        },
    )
    if created:
        return pattern

    merged_ticket_ids = set(str(item) for item in (pattern.evidence.get("source_ticket_ids", []) if isinstance(pattern.evidence, dict) else []))
    merged_ticket_refs = set(str(item) for item in (pattern.evidence.get("source_ticket_refs", []) if isinstance(pattern.evidence, dict) else []))
    merged_ticket_ids.add(str(ticket.id))
    if ticket.ticket_id:
        merged_ticket_refs.add(str(ticket.ticket_id))

    pattern.specialization = signature["specialization"]
    pattern.component_name = signature["component_name"]
    pattern.fault_code = signature["fault_code"]
    pattern.issue_text = signature["issue_text"]
    pattern.issue_tokens = signature["issue_tokens"]
    pattern.parts_signature = signature["parts_signature"]
    pattern.checklist_template = successful_steps
    pattern.success_count = int(pattern.success_count or 0) + 1
    pattern.last_used_at = timezone.now()
    pattern.evidence = {
        "source_ticket_ids": sorted(merged_ticket_ids),
        "source_ticket_refs": sorted(merged_ticket_refs),
        "last_ticket_title": str(ticket.title or ""),
        "last_ticket_completed_at": timezone.now().isoformat(),
    }
    pattern.save(
        update_fields=[
            "specialization",
            "component_name",
            "fault_code",
            "issue_text",
            "issue_tokens",
            "parts_signature",
            "checklist_template",
            "success_count",
            "last_used_at",
            "evidence",
            "updated_at",
        ]
    )
    return pattern
