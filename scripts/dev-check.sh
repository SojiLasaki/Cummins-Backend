#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_DIR="$(cd "${ROOT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"
echo "[1/7] backend check"
uv run --no-sync python manage.py check

echo "[2/7] backend ai tests"
uv run --no-sync python manage.py test apps.ai

echo "[3/7] backend users tests"
uv run --no-sync python manage.py test apps.users

echo "[4/7] seed demo users"
uv run --no-sync python manage.py seed_demo_users

cd "${WORKSPACE_DIR}/breakthru-dashboard"
echo "[5/7] frontend build"
npm run build

cd "${ROOT_DIR}"
echo "[6/7] MCP endpoint probes"
for url in \
  "http://127.0.0.1:9101/mcp" \
  "http://127.0.0.1:9102/mcp" \
  "http://127.0.0.1:9103/mcp"; do
  code="$(curl -s -o /tmp/felix_mcp_probe.out -w '%{http_code}' \
    -X POST "$url" \
    -H 'Accept: application/json, text/event-stream' \
    -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":"health","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"dev-check","version":"0.1.0"}}}' || true)"
  echo "$code $url"
done

echo "[7/7] login API smoke"
cd "${ROOT_DIR}"
uv run --no-sync python manage.py shell -c "from rest_framework.test import APIClient; c=APIClient(); r=c.post('/api/auth/login', {'username':'admin','password':'admin'}, format='json', HTTP_HOST='localhost'); print('status', r.status_code); print('keys', list(r.data.keys()) if hasattr(r,'data') else None)"

echo "dev-check complete"
