#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE_DIR="$(cd "${ROOT_DIR}/.." && pwd)"

start_session() {
  local name="$1"
  local cmd="$2"
  if tmux has-session -t "$name" 2>/dev/null; then
    echo "tmux session $name already running"
    return
  fi
  tmux new-session -d -s "$name" "$cmd"
  echo "started $name"
}

if (echo > /dev/tcp/127.0.0.1/8000) >/dev/null 2>&1; then
  echo "backend already listening on 127.0.0.1:8000 (skipping new session)"
else
  start_session "felix_backend" "cd ${ROOT_DIR} && uv run --no-sync python manage.py runserver 127.0.0.1:8000"
fi
start_session "felix_frontend" "cd ${WORKSPACE_DIR}/breakthru-dashboard && npm run dev -- --host 127.0.0.1 --port 8080"
start_session "felix_mcp_supply" "cd ${ROOT_DIR}/mcp-demo && uv run python supply_chain_server/server.py"
start_session "felix_mcp_ticket" "cd ${ROOT_DIR}/mcp-demo && uv run python ticketing_server/server.py"
start_session "felix_mcp_employee" "cd ${ROOT_DIR}/mcp-demo && uv run python employee_server/server.py"

sleep 2

echo
echo "Active sessions:"
tmux ls | rg 'felix_(backend|frontend|mcp_supply|mcp_ticket|mcp_employee)' || true

echo
echo "Next steps:"
echo "1) Open UI: http://localhost:8080"
echo "2) In Agent Studio -> Integration Connectors, click 'Seed Demo Connectors'"
echo "3) Select connectors in Fix it Felix chat and ask for ticket/assignment/parts automation"
