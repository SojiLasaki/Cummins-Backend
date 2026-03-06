# Breakthru + Fix-it Felix Demo Playbook

Date: March 6, 2026  
Scope: End-to-end demo of features delivered to date (chat, approvals, ticketing, checklist intelligence, model orchestration, MCP integrations)

## 1. Demo Goal

Show how Breakthru operations teams use Fix-it Felix and Agent Studio to:

1. Diagnose and triage issues quickly.
2. Generate and approve ticket actions from chat.
3. Execute dynamic repair checklists tied to ticket context.
4. Reuse learned checklist patterns from completed work.
5. Operate with pluggable models (including local Ollama) and MCP connectors.

## 2. Environment Snapshot

- Frontend: `http://127.0.0.1:8080`
- Backend API: `http://127.0.0.1:8000`
- Local Ollama API: `http://localhost:11434/v1` (port `11434`)
- Current default local model: `qwen2.5:3b`

Demo MCP connectors (local):

- Supply Chain: `127.0.0.1:9101/mcp`
- Ticketing: `127.0.0.1:9102/mcp`
- Workforce: `127.0.0.1:9103/mcp`

## 3. One-Command Startup

From backend repo:

```bash
cd Cummins-Backend
uv sync
uv run --no-sync python manage.py migrate
uv run --no-sync python manage.py seed_demo_users
./scripts/dev-up.sh
```

Health checks:

```bash
./scripts/dev-status.sh
./scripts/dev-check.sh
```

## 4. Demo Accounts

Seeded credentials use `username = password`:

- `admin/admin` (Agent Studio + operations admin)
- `office/office`
- `engine/engine` (technician path)
- `electrical/electrical`
- `customer/customer`

If login fails:

```bash
cd Cummins-Backend
uv run --no-sync python manage.py seed_demo_users
```

## 5. What To Demo (Feature Inventory)

### A. Technician AI Workflow (Fix-it Felix)

- Route: `/ask-ai`
- Chat with diagnostic context and parts/issue details.
- AI returns action proposal (example: `create_ticket`).
- Technician confirms action directly from chat.
- Redirect to created ticket details.

### B. Ticket + Checklist Intelligence

- Ticket detail shows repair/checklist flow.
- Checklist is generated from issue context.
- Provenance badges supported by implementation:
  - `Baseline`
  - `Knowledge`
  - `Learned from similar completed tickets`
- Completed checklist patterns are stored for future reuse on similar issues.

### C. Admin Agent Studio

- Route: `/ai-agents`
- Tabs:
  - `Overview`
  - `Actions` (approval queue, approve/reject/execute)
  - `Integrations & Settings` (connectors, prompt controls, runtime defaults)
- Connector auth modes include OAuth 2.0 fields in connector configuration flow.
- Prompt controls allow system/guardrail tuning.

### D. Multi-Model and Local Model Support

- Backend active model endpoint supports providers: backend orchestration + local/remote providers.
- Local model path validated with Ollama `qwen2.5:3b`.
- UI model default selection uses active backend endpoint first.

### E. MCP Adapter Integration

- Connectors are manageable from Agent Studio.
- Demo local connectors represent external systems:
  - supply chain
  - ticket operations
  - workforce/employee assignment

## 6. Recommended 12-Minute Live Demo Script

## 0:00 - 1:00 | Intro

- Explain goal: faster resolution with AI-assisted triage + controlled automation.
- Mention role split: Technician in Fix-it Felix, Admin in Agent Studio.

## 1:00 - 4:00 | Technician: Chat -> Ticket

1. Login as `engine/engine`.
2. Open `Fix-it Felix`.
3. Send prompt:

```text
Create a ticket for engine X15 fuel leak on truck 4821 at INDY station.
Issue: fuel leak near injector hose with white smoke.
Parts affected: fuel injector and hose.
Assign technician and prepare checklist.
```

4. Show AI response + pending proposal card.
5. Click `Confirm`.
6. Show redirect to `/tickets/<uuid>`.

## 4:00 - 6:00 | Ticket Checklist View

1. In ticket detail, open full repair details/checklist.
2. Explain checklist generation and provenance badges.
3. Mark progress on a few items (if available in ticket UI state).
4. Explain learning loop on completed tickets.

## 6:00 - 9:00 | Admin: Agent Studio Controls

1. Login as `admin/admin`.
2. Open `Agent Studio`.
3. `Overview`: show operational KPIs.
4. `Actions`: show pending action queue and approval control.
5. `Integrations & Settings`:
   - show connector management
   - show prompt/guardrail controls
   - mention OAuth-capable connector setup fields

## 9:00 - 11:00 | Model + MCP Story

1. Explain active model route (local Ollama default).
2. Mention model currently configured: `qwen2.5:3b` via `http://localhost:11434/v1`.
3. Explain MCP connectors as the bridge to external systems.

## 11:00 - 12:00 | Close

- Summarize business impact:
  - faster triage
  - structured execution
  - approval-safe automation
  - learning over time

## 7. Backup Prompts (If You Need Variety)

```text
Give me a step-by-step injector diagnostic checklist for rough idle and white smoke.
```

```text
Create a repair checklist for coolant leak and overheating under load.
```

```text
Summarize this ticket and suggest technician handoff notes.
```

## 8. Validation Artifacts (Already Verified)

- Backend tests: `apps.tickets.tests`, `apps.ai.tests` pass.
- Frontend production build succeeds.
- Playwright E2E flow validated:
  - technician login
  - chat request
  - approve action
  - ticket redirect
  - checklist panel visibility
  - admin Agent Studio tabs and controls

## 9. Fast Troubleshooting During Demo

### Login failing

```bash
cd Cummins-Backend
uv run --no-sync python manage.py seed_demo_users
```

### Backend unreachable from UI

- Confirm backend running on `127.0.0.1:8000`.
- Confirm frontend uses `VITE_API_URL=http://127.0.0.1:8000/api`.

### No AI response

- Confirm `.env` has model/API key configuration.
- For local mode, confirm Ollama is up and model exists:

```bash
/usr/local/bin/ollama list
/usr/local/bin/ollama ps
```

### Connectors not showing

- Use Agent Studio integrations tab.
- Ensure demo MCP services are started by `./scripts/dev-up.sh`.

## 10. Optional API Proof Snippets

```bash
# login
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"engine","password":"engine"}'
```

```bash
# active model endpoints
curl -H "Authorization: Bearer <token>" \
  http://127.0.0.1:8000/api/ai/model_endpoints/active/
```

```bash
# chat
curl -X POST http://127.0.0.1:8000/api/ai/chat/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <token>' \
  -d '{"message":"Create a ticket for X15 injector leak at INDY","provider":"ollama","model":"qwen2.5:3b"}'
```

