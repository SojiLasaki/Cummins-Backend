# Diagnostic Ticketing + Dynamic Checklist Testing Guide

This guide verifies the end-to-end flow:
- diagnostic context reaches the ticketing agent,
- ticket creation runs through Fix it Felix approval,
- checklist is generated dynamically,
- completed tickets feed learned checklist recommendations.

## 1. Prerequisites

1. Backend repo: `Cummins-Backend`
2. Python commands use `uv`
3. `.env` includes `OPENAI_API_KEY`
4. Frontend running on `http://127.0.0.1:8080`
5. Backend running on `http://127.0.0.1:8000`

## 2. One-Time Setup

```bash
cd Cummins-Backend
uv sync
uv run python manage.py migrate
```

The migration step is mandatory for learned checklist patterns (`tickets_ticketresolutionpattern`).

## 3. Backend Automated Validation

Run the focused test suites:

```bash
cd Cummins-Backend
uv run --no-sync python manage.py test apps.tickets.tests apps.ai.tests
uv run --no-sync python -m compileall apps
```

Expected result:
- tests pass,
- no migration/table errors,
- compile succeeds.

## 4. API Smoke Validation

```bash
# Login
curl -s -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"engine","password":"engine"}'

# Chat proposal generation
curl -s -X POST http://127.0.0.1:8000/api/ai/chat/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <access_token>' \
  -d '{
    "query": "Create ticket for X15 fuel leak on truck 4821. Parts affected injector and hose.",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "intent": "ticket_ops",
    "policy_mode": "manual",
    "context": {
      "diagnostic_report_id": "<diagnostic_uuid>"
    }
  }'
```

Expected:
- response includes a pending `create_ticket` proposal,
- proposal payload includes `diagnostic_report_id` and `diagnostic_payload`.

## 5. UI E2E Validation (Manual)

1. Login as technician (`engine/engine`) at `/login`.
2. Go to `Fix it Felix` (`/ask-ai`).
3. Send a ticket-style prompt with issue, component, and parts.
4. Verify a `create_ticket` proposal card appears.
5. Click `Confirm`.
6. Verify redirect to `/tickets/<uuid>`.
7. Open `View Full Repair Details & Checklist`.
8. Verify:
   - `Repair Checklist` is visible,
   - provenance badges appear (`Baseline` always; `Knowledge` and `Learned...` when available).

## 6. Learning Loop Validation

1. Mark ticket steps complete and set ticket status to `completed`.
2. Create another similar ticket/issue.
3. Verify checklist includes reused learned steps and `Learned from similar completed tickets` badge when matched.

## 7. Troubleshooting

### Error: `no such table: tickets_ticketresolutionpattern`

Run:

```bash
cd Cummins-Backend
uv run --no-sync python manage.py migrate
```

### Proposal approve returns `failed`

Check latest proposal status:

```bash
cd Cummins-Backend
uv run --no-sync python manage.py shell -c "from apps.ai.models import AgentActionProposal as A; p=A.objects.order_by('-created_at').first(); print(p.id, p.status, p.error, p.result)"
```
