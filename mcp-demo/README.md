# MCP Demo Services

Local FastMCP servers used by Fix it Felix demo workflows.

## Services

- Supply Chain Connector: `http://127.0.0.1:9101/mcp`
- Ticket Operations Connector: `http://127.0.0.1:9102/mcp`
- Workforce Connector: `http://127.0.0.1:9103/mcp`

## Run one service

```bash
cd Cummins-Backend/mcp-demo
uv sync
uv run python supply_chain_server/server.py
```

(Replace with `ticketing_server/server.py` or `employee_server/server.py`)

## Run all services

Use repo script:

```bash
cd Cummins-Backend
./scripts/dev-up.sh
```
