# Cummins Backend

Django + DRF backend for Breakthru/Fix it Felix, including LangGraph orchestration, agent action approvals, and MCP connector integration.

## Quick Start

For automated setup of the complete stack (backend + frontend + MCP services), use the setup script from the parent directory:

```bash
# From parent directory containing both repos
./setup.sh

# Start all services
make start

# Open http://127.0.0.1:8080
```

See `breakthru-dashboard/README.md` for comprehensive documentation.

---

## Requirements

1. `git`
2. `python` 3.14.x (project currently runs on 3.14 in this repo)
3. `uv` (Python package/dependency runner)
4. `node` 20+ and `npm` 10+ (needed if you also run frontend locally)
5. `tmux` (optional, only for `scripts/dev-up.sh` workflow)
6. `curl` (used by health/probe scripts)

## Repository layout assumptions

These instructions assume both repos exist side-by-side:

- `Cummins-Backend`
- `breakthru-dashboard`

If you cloned them elsewhere, adjust paths/commands accordingly.

## Environment variables

The backend loads `.env` from either:

1. `Cummins-Backend/.env`
2. workspace root `.env` (parent folder containing both repos)

Minimum for AI chat (free online model, no local server):

```bash
OPENROUTER_API_KEY=<your_key_from_https://openrouter.ai/keys>
```

Optional: use OpenAI instead:

```bash
OPENAI_API_KEY=<your_openai_key>
```

Optional model/runtime overrides:

```bash
FELIX_DEFAULT_PROVIDER=openrouter
FELIX_OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
FELIX_LANGGRAPH_MODEL=gpt-4o-mini
FELIX_OPENAI_MODEL=gpt-4.1-mini
FELIX_GOOGLE_MODEL=gemini-3-flash-preview
FELIX_ANTHROPIC_MODEL=claude-3-5-sonnet-latest
FELIX_OLLAMA_MODEL=llama3.2
FELIX_VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct
FELIX_LLAMACPP_MODEL=local-model
OLLAMA_BASE_URL=http://localhost:11434/v1
VLLM_BASE_URL=http://localhost:8001/v1
LLAMACPP_BASE_URL=http://localhost:8088/v1
```

## One-time setup

```bash
cd Cummins-Backend
uv sync
uv run --no-sync python manage.py migrate
uv run --no-sync python manage.py seed_demo_users
```

If running full stack locally, also install frontend dependencies:

```bash
cd ../breakthru-dashboard
npm install
```

## Run the full local demo stack (recommended)

From `Cummins-Backend`:

```bash
./scripts/dev-up.sh
```

This starts:

1. Backend API on `127.0.0.1:8000`
2. Frontend on `127.0.0.1:8080`
3. MCP demo connectors:
   - Supply Chain: `127.0.0.1:9101/mcp`
   - Ticketing: `127.0.0.1:9102/mcp`
   - Workforce: `127.0.0.1:9103/mcp`

Useful runtime commands:

```bash
./scripts/dev-status.sh
./scripts/dev-check.sh
./scripts/dev-down.sh
```

## Run backend only (manual mode)

```bash
cd Cummins-Backend
uv sync
uv run --no-sync python manage.py migrate
uv run --no-sync python manage.py runserver 127.0.0.1:8000
```

## Run MCP demo services manually (optional)

```bash
cd Cummins-Backend/mcp-demo
uv sync
uv run python supply_chain_server/server.py
uv run python ticketing_server/server.py
uv run python employee_server/server.py
```

## Login and auth

Supported login endpoints:

- `POST /api/auth/login/`
- `POST /api/auth/login`

Refresh endpoints:

- `POST /api/auth/refresh/`
- `POST /api/auth/refresh`

Seeded demo credentials (`username/password`):

- `admin/admin`
- `office/office`
- `engine/engine`
- `electrical/electrical`
- `customer/customer`
- `login_probe/login_probe`

## MCP connectors and Agent actions

Agent action queue endpoints:

- `GET /api/ai/agent_actions/`
- `POST /api/ai/agent_actions/{id}/approve/`
- `POST /api/ai/agent_actions/{id}/reject/`
- `POST /api/ai/agent_actions/{id}/execute/`

Seed demo connectors via API:

```bash
curl -X POST http://127.0.0.1:8000/api/ai/mcp_adapters/seed_demo/ \
  -H "Authorization: Bearer <access-token>"
```

## Validation and regression checks

```bash
cd Cummins-Backend
uv run --no-sync python manage.py check
uv run --no-sync python manage.py test apps.ai.tests apps.users.tests
./scripts/regression_auth.sh
./scripts/dev-check.sh
```

## Common issues

1. `401` from login/UI:
   - Run `uv run --no-sync python manage.py seed_demo_users` again.
2. Empty/failed Felix model response:
   - Confirm `OPENAI_API_KEY` is set in backend-loaded `.env`.
3. MCP connectors unavailable:
   - Ensure ports `9101/9102/9103` are running (`./scripts/dev-status.sh`).
4. Frontend cannot reach backend:
   - Confirm backend is listening on `127.0.0.1:8000`.
