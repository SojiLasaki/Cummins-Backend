import hashlib
import re
from typing import Any

from django.utils import timezone

from apps.ai.services.retrieval import search_knowledge_chunks
from apps.tickets.models import Ticket
from apps.tickets.patterns import build_ticket_signature, find_best_patterns


BASELINE_STEPS: list[dict[str, str | bool]] = [
    {
        "category": "safety",
        "title": "Review safety precautions and gather PPE",
        "instructions": "Confirm lockout and PPE before diagnosis.",
        "required": True,
    },
    {
        "category": "diagnosis",
        "title": "Verify customer-reported symptom onsite",
        "instructions": "Reproduce the issue and capture current observations.",
        "required": True,
    },
    {
        "category": "diagnosis",
        "title": "Run diagnostic scan and collect active/latent fault codes",
        "instructions": "Record all codes and live readings before disassembly.",
        "required": True,
    },
    {
        "category": "repair",
        "title": "Perform targeted component inspection and corrective action",
        "instructions": "Inspect affected components and execute approved repair steps.",
        "required": True,
    },
    {
        "category": "verification",
        "title": "Validate repair under operating conditions",
        "instructions": "Run equipment at operating load and verify no recurring faults.",
        "required": True,
    },
    {
        "category": "verification",
        "title": "Capture notes, parts usage, and completion evidence",
        "instructions": "Attach service notes, timings, and photos before closing ticket.",
        "required": True,
    },
]

ACTION_VERBS = (
    "check",
    "inspect",
    "verify",
    "test",
    "measure",
    "scan",
    "replace",
    "tighten",
    "calibrate",
    "clean",
    "confirm",
)


def _step_id(category: str, title: str) -> str:
    raw = f"{category}|{title}".strip().lower().encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def build_ticket_diagnostic_payload(ticket: Ticket) -> dict[str, Any]:
    if not getattr(ticket, "pk", None):
        return {}
    report = ticket.diagnostic_reports.order_by("-created_at").first()
    if not report:
        return {}
    return {
        "diagnostic_report_id": str(report.id),
        "specialization": str(report.specialization or ""),
        "component_name": str(getattr(report.component, "name", "") or ""),
        "fault_code": str(report.fault_code or ""),
        "issue": str(report.title or ""),
        "description": str(report.description or report.ai_summary or ""),
        "part_names": list(report.parts.values_list("name", flat=True)),
    }


def _ticket_query(ticket: Ticket, diagnostic_payload: dict[str, Any] | None = None) -> str:
    payload = diagnostic_payload if isinstance(diagnostic_payload, dict) else {}
    parts = [
        str(ticket.title or ""),
        str(ticket.description or ""),
        str(ticket.issue_description or ""),
        str(ticket.specialization or ""),
        str(payload.get("component_name") or ""),
        str(payload.get("fault_code") or ""),
        str(payload.get("issue") or ""),
        str(payload.get("description") or ""),
    ]
    part_names = payload.get("part_names")
    if isinstance(part_names, list):
        parts.extend(str(item or "") for item in part_names)
    return " ".join(part.strip() for part in parts if part and part.strip()).strip()


def _extract_candidate_steps(snippet_text: str) -> list[str]:
    candidates: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", str(snippet_text or "")):
        cleaned = re.sub(r"\s+", " ", sentence).strip(" -:\t\r\n")
        if len(cleaned) < 18 or len(cleaned) > 170:
            continue
        lower = cleaned.lower()
        if any(verb in lower for verb in ACTION_VERBS):
            candidates.append(cleaned.rstrip("."))
    return candidates


def _normalize_template_item(item: dict[str, Any]) -> dict[str, Any]:
    category = str(item.get("category") or "diagnosis").strip().lower() or "diagnosis"
    if category not in {"diagnosis", "repair", "verification", "safety"}:
        category = "diagnosis"
    title = re.sub(r"\s+", " ", str(item.get("title") or "").strip())
    instructions = re.sub(r"\s+", " ", str(item.get("instructions") or "").strip())
    required = bool(item.get("required", True))
    refs = item.get("source_refs")
    return {
        "id": _step_id(category, title or instructions or "step"),
        "category": category,
        "title": title or instructions or "Checklist step",
        "instructions": instructions or title or "",
        "required": required,
        "source_refs": refs if isinstance(refs, list) else [],
    }


def _append_step(
    template: list[dict[str, Any]],
    added_titles: set[str],
    step: dict[str, Any],
    *,
    hard_limit: int = 12,
) -> bool:
    normalized = str(step.get("title") or "").strip().lower()
    if not normalized or normalized in added_titles:
        return False
    if len(template) >= hard_limit:
        return False
    template.append(step)
    added_titles.add(normalized)
    return True


def generate_ticket_checklist(
    ticket: Ticket,
    *,
    limit: int = 6,
    diagnostic_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_diagnostic_payload = (
        diagnostic_payload if isinstance(diagnostic_payload, dict) and diagnostic_payload else build_ticket_diagnostic_payload(ticket)
    )
    query = _ticket_query(ticket, resolved_diagnostic_payload)
    snippets = search_knowledge_chunks(query, limit=limit) if query else []
    signature = build_ticket_signature(ticket, diagnostic_payload=resolved_diagnostic_payload)
    pattern_matches = find_best_patterns(signature, top_k=3, min_score=0.35)

    template: list[dict[str, Any]] = []
    for base in BASELINE_STEPS:
        template.append(
            _normalize_template_item(
                {
                    "category": base["category"],
                    "title": base["title"],
                    "instructions": base["instructions"],
                    "required": base["required"],
                    "source_refs": [{"type": "baseline"}],
                }
            )
        )

    added_titles = {item["title"].lower() for item in template}
    learned_refs: list[dict[str, Any]] = []
    learned_step_count = 0
    for match in pattern_matches:
        pattern = match["pattern"]
        score = float(match.get("score") or 0.0)
        ref = {
            "type": "pattern",
            "pattern_id": str(pattern.id),
            "score": score,
            "success_count": int(pattern.success_count or 0),
            "source_ticket_refs": pattern.evidence.get("source_ticket_refs", []) if isinstance(pattern.evidence, dict) else [],
        }
        learned_refs.append(ref)
        for raw_step in pattern.checklist_template if isinstance(pattern.checklist_template, list) else []:
            if not isinstance(raw_step, dict):
                continue
            normalized_step = _normalize_template_item(
                {
                    "category": raw_step.get("category") or "repair",
                    "title": raw_step.get("title") or "",
                    "instructions": raw_step.get("instructions") or raw_step.get("title") or "",
                    "required": bool(raw_step.get("required", False)),
                    "source_refs": [ref],
                }
            )
            if _append_step(template, added_titles, normalized_step):
                learned_step_count += 1
            if len(template) >= 12:
                break
        if len(template) >= 12:
            break

    snippet_refs: list[dict[str, Any]] = []
    knowledge_step_count = 0
    for snippet in snippets:
        ref = {
            "type": "knowledge",
            "chunk_id": snippet.get("chunk_id"),
            "title": snippet.get("document_title"),
            "source_uri": snippet.get("document_source_uri"),
            "score": snippet.get("score"),
        }
        snippet_refs.append(ref)
        for sentence in _extract_candidate_steps(str(snippet.get("content") or "")):
            normalized_step = _normalize_template_item(
                {
                    "category": "repair",
                    "title": sentence,
                    "instructions": sentence,
                    "required": False,
                    "source_refs": [ref],
                }
            )
            if _append_step(template, added_titles, normalized_step):
                knowledge_step_count += 1
            if len(template) >= 12:
                break
        if len(template) >= 12:
            break

    return {
        "template": template,
        "progress": [],
        "meta": {
            "generated_at": timezone.now().isoformat(),
            "generator": "ticket_checklist_v2",
            "query": query,
            "source_refs": snippet_refs[:10],
            "learned_patterns": learned_refs,
            "diagnostic_context": resolved_diagnostic_payload,
            "provenance": {
                "baseline_steps": len(BASELINE_STEPS),
                "learned_steps": learned_step_count,
                "knowledge_steps": knowledge_step_count,
                "total_steps": len(template),
            },
        },
    }


def ensure_ticket_checklist(ticket: Ticket, *, diagnostic_payload: dict[str, Any] | None = None) -> Ticket:
    if isinstance(ticket.checklist_template, list) and ticket.checklist_template:
        return ticket

    generated = generate_ticket_checklist(ticket, diagnostic_payload=diagnostic_payload)
    ticket.checklist_template = generated["template"]
    ticket.checklist_progress = generated["progress"]
    ticket.checklist_meta = generated["meta"]
    ticket.save(update_fields=["checklist_template", "checklist_progress", "checklist_meta"])
    return ticket


def regenerate_ticket_checklist(ticket: Ticket, *, diagnostic_payload: dict[str, Any] | None = None) -> Ticket:
    previous_progress = ticket.checklist_progress if isinstance(ticket.checklist_progress, list) else []
    progress_by_id = {
        str(item.get("item_id") or ""): item
        for item in previous_progress
        if isinstance(item, dict) and str(item.get("item_id") or "").strip()
    }

    generated = generate_ticket_checklist(ticket, diagnostic_payload=diagnostic_payload)
    preserved_progress: list[dict[str, Any]] = []
    for step in generated["template"]:
        step_id = str(step.get("id") or "").strip()
        if not step_id:
            continue
        prior = progress_by_id.get(step_id)
        if not prior:
            continue
        preserved_progress.append(
            {
                "item_id": step_id,
                "done": bool(prior.get("done", False)),
                "note": str(prior.get("note") or ""),
                "flagged": bool(prior.get("flagged", False)),
                "time_minutes": int(prior.get("time_minutes") or 0),
                "photos": prior.get("photos") if isinstance(prior.get("photos"), list) else [],
                "updated_at": timezone.now().isoformat(),
            }
        )

    ticket.checklist_template = generated["template"]
    ticket.checklist_progress = preserved_progress
    ticket.checklist_meta = generated["meta"]
    ticket.save(update_fields=["checklist_template", "checklist_progress", "checklist_meta"])
    return ticket
