#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DASHBOARD_DIR="$(cd "${ROOT_DIR}/../breakthru-dashboard" && pwd)"

cd "${ROOT_DIR}"
echo "[1/6] Django system checks"
uv run --no-sync python manage.py check

echo "[2/6] Seed deterministic demo users"
uv run --no-sync python manage.py seed_demo_users

echo "[3/6] Auth regression tests"
uv run --no-sync python manage.py test apps.users

echo "[4/6] AI regression tests"
uv run --no-sync python manage.py test apps.ai

echo "[5/6] Login API smoke"
uv run --no-sync python manage.py shell -c "from rest_framework.test import APIClient; c=APIClient(); r=c.post('/api/auth/login', {'username':'admin','password':'admin'}, format='json', HTTP_HOST='localhost'); print('status', r.status_code); print('keys', list(r.data.keys()) if hasattr(r,'data') else None)"

echo "[6/6] Frontend build regression"
cd "${DASHBOARD_DIR}"
npm run build

echo "Regression suite complete."
