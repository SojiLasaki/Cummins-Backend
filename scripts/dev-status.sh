#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "tmux sessions"
tmux ls | rg 'felix_(backend|frontend|mcp_supply|mcp_ticket|mcp_employee)' || echo "no demo sessions running"

echo
echo "HTTP probes"
for url in \
  "http://127.0.0.1:8000/api/auth/login/" \
  "http://127.0.0.1:8080/login"; do
  code="$(curl -s -o /tmp/felix_probe.out -w '%{http_code}' "$url" || true)"
  echo "$code $url"
done

echo
echo "MCP initialize probes"
for url in \
  "http://127.0.0.1:9101/mcp" \
  "http://127.0.0.1:9102/mcp" \
  "http://127.0.0.1:9103/mcp"; do
  code="$(curl -s -o /tmp/felix_mcp_probe.out -w '%{http_code}' \
    -X POST "$url" \
    -H 'Accept: application/json, text/event-stream' \
    -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":"status","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"dev-status","version":"0.1.0"}}}' || true)"
  echo "$code $url"
done
