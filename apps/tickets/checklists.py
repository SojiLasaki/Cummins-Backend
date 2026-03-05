import hashlib
import re
from typing import Any

from django.utils import timezone

from apps.ai.services.retrieval import search_knowledge_chunks
from apps.tickets.models import Ticket


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


def _ticket_query(ticket: Ticket) -> str:
    parts = [
        str(ticket.title or ""),
        str(ticket.description or ""),
        str(ticket.issue_description or ""),
        str(ticket.specialization or ""),
    ]
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
    return {
        "id": _step_id(category, title or instructions or "step"),
        "category": category,
        "title": title or instructions or "Checklist step",
        "instructions": instructions or title or "",
        "required": required,
        "source_refs": item.get("source_refs", []),
    }


def generate_ticket_checklist(ticket: Ticket, *, limit: int = 6) -> dict[str, Any]:
    query = _ticket_query(ticket)
    snippets = search_knowledge_chunks(query, limit=limit) if query else []

    template: list[dict[str, Any]] = []
    for base in BASELINE_STEPS:
        template.append(
            _normalize_template_item(
                {
                    "category": base["category"],
                    "title": base["title"],
                    "instructions": base["instructions"],
                    "required": base["required"],
                    "source_refs": [],
                }
            )
        )

    added_titles = {item["title"].lower() for item in template}
    snippet_refs: list[dict[str, Any]] = []
    for snippet in snippets:
        ref = {
            "chunk_id": snippet.get("chunk_id"),
            "title": snippet.get("document_title"),
            "source_uri": snippet.get("document_source_uri"),
            "score": snippet.get("score"),
        }
        snippet_refs.append(ref)
        for sentence in _extract_candidate_steps(str(snippet.get("content") or "")):
            normalized = sentence.lower()
            if normalized in added_titles:
                continue
            template.append(
                _normalize_template_item(
                    {
                        "category": "repair",
                        "title": sentence,
                        "instructions": sentence,
                        "required": False,
                        "source_refs": [ref],
                    }
                )
            )
            added_titles.add(normalized)
            if len(template) >= 12:
                break
        if len(template) >= 12:
            break

    return {
        "template": template,
        "progress": [],
        "meta": {
            "generated_at": timezone.now().isoformat(),
            "generator": "ticket_checklist_v1",
            "query": query,
            "source_refs": snippet_refs[:10],
        },
    }


def ensure_ticket_checklist(ticket: Ticket) -> Ticket:
    if isinstance(ticket.checklist_template, list) and ticket.checklist_template:
        return ticket

    generated = generate_ticket_checklist(ticket)
    ticket.checklist_template = generated["template"]
    ticket.checklist_progress = generated["progress"]
    ticket.checklist_meta = generated["meta"]
    ticket.save(update_fields=["checklist_template", "checklist_progress", "checklist_meta"])
    return ticket


def regenerate_ticket_checklist(ticket: Ticket) -> Ticket:
    previous_progress = ticket.checklist_progress if isinstance(ticket.checklist_progress, list) else []
    progress_by_id = {
        str(item.get("item_id") or ""): item
        for item in previous_progress
        if isinstance(item, dict) and str(item.get("item_id") or "").strip()
    }

    generated = generate_ticket_checklist(ticket)
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
