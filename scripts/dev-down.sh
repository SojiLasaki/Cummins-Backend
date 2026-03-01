#!/usr/bin/env bash
set -euo pipefail

for name in felix_backend felix_frontend felix_mcp_supply felix_mcp_ticket felix_mcp_employee; do
  if tmux has-session -t "$name" 2>/dev/null; then
    tmux kill-session -t "$name"
    echo "stopped $name"
  fi
done
