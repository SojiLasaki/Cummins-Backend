# Cummins Backend

## Local setup

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

## Auth endpoints

- `POST /api/auth/login/`
- `POST /api/auth/login` (no trailing slash supported)
- `POST /api/auth/refresh/`
- `POST /api/auth/refresh` (no trailing slash supported)

## Demo accounts for local testing

Seed deterministic local accounts:

```bash
uv run --no-sync python manage.py seed_demo_users
```

Credentials (username/password):

- `admin/admin`
- `office/office`
- `engine/engine`
- `electrical/electrical`
- `customer/customer`
- `login_probe/login_probe`

## Regression checks

Run full auth-focused regression checks:

```bash
./scripts/regression_auth.sh
```

## Agent automation queue

The AI service now creates approval-gated proposals for:

- ticket creation
- employee assignment
- external part ordering

Queue endpoints:

- `GET /api/ai/agent_actions/`
- `POST /api/ai/agent_actions/{id}/approve/`
- `POST /api/ai/agent_actions/{id}/reject/`
- `POST /api/ai/agent_actions/{id}/execute/`

## Demo connector seed

Create pre-wired local connectors (for `mcp-demo` services):

```bash
curl -X POST http://127.0.0.1:8000/api/ai/mcp_adapters/seed_demo/ \
  -H "Authorization: Bearer <access-token>"
```

## Full demo runtime

From `Cummins-Backend`:

```bash
./scripts/dev-up.sh
./scripts/dev-status.sh
./scripts/dev-check.sh
./scripts/dev-down.sh
```
