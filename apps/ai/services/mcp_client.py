import json
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from apps.ai.models import McpAdapter


@dataclass
class McpCallResult:
    ok: bool
    data: dict[str, Any] | None = None
    error: str = ""
    status_code: int = 0
    duration_ms: int = 0


class McpClient:
    """Tiny JSON-RPC MCP client for streamable HTTP endpoints."""

    def __init__(self, adapter: McpAdapter, timeout_seconds: int = 8):
        self.adapter = adapter
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream, */*",
            "User-Agent": "FixItFelix-MCP-Client/1.0",
        }
        config = self.adapter.auth_config if isinstance(self.adapter.auth_config, dict) else {}

        if self.adapter.auth_type == McpAdapter.AUTH_BEARER:
            token = str(config.get("token") or config.get("bearer_token") or "").strip()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif self.adapter.auth_type == McpAdapter.AUTH_OAUTH2:
            token = str(config.get("access_token") or "").strip()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif self.adapter.auth_type == McpAdapter.AUTH_API_KEY:
            header_name = str(config.get("header_name") or "X-API-Key").strip()
            header_value = str(config.get("value") or config.get("api_key") or "").strip()
            if header_name and header_value:
                headers[header_name] = header_value

        return headers

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> McpCallResult:
        started = time.time()
        rpc_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "method": method,
            "params": params or {},
        }
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            self.adapter.base_url,
            headers=self._headers(),
            data=body,
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
                status_code = int(response.getcode() or 0)
        except HTTPError as exc:
            return McpCallResult(
                ok=False,
                error=str(exc.reason or "HTTPError"),
                status_code=int(exc.code or 0),
                duration_ms=int((time.time() - started) * 1000),
            )
        except (URLError, TimeoutError, ValueError) as exc:
            return McpCallResult(
                ok=False,
                error=str(exc),
                status_code=0,
                duration_ms=int((time.time() - started) * 1000),
            )

        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return McpCallResult(
                ok=False,
                error="Invalid JSON response",
                status_code=status_code,
                duration_ms=int((time.time() - started) * 1000),
            )

        if isinstance(parsed, dict) and parsed.get("error"):
            err = parsed.get("error")
            return McpCallResult(
                ok=False,
                error=str(err),
                status_code=status_code,
                data=parsed,
                duration_ms=int((time.time() - started) * 1000),
            )

        return McpCallResult(
            ok=200 <= status_code < 400,
            data=parsed if isinstance(parsed, dict) else {"result": parsed},
            error="",
            status_code=status_code,
            duration_ms=int((time.time() - started) * 1000),
        )

    def initialize(self) -> McpCallResult:
        return self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "fix-it-felix", "version": "0.1.0"},
            },
        )

    def list_tools(self) -> McpCallResult:
        return self._rpc("tools/list", {})

    def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> McpCallResult:
        return self._rpc(
            "tools/call",
            {
                "name": str(tool_name),
                "arguments": arguments or {},
            },
        )


def list_enabled_mcp_clients(selected_adapter_ids: list[str] | None = None) -> list[McpClient]:
    queryset = McpAdapter.objects.filter(is_enabled=True)
    if selected_adapter_ids:
        numeric_ids: list[int] = []
        for raw in selected_adapter_ids:
            try:
                numeric_ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        if numeric_ids:
            queryset = queryset.filter(id__in=numeric_ids)

    return [McpClient(adapter) for adapter in queryset.order_by("name")]
