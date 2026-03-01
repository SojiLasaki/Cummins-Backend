import json
import os
import re
from html import unescape
from django.http import HttpResponse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from .models import (
    AgentActionProposal,
    AgentPromptConfig,
    AgentExecutionTrace,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeRelation,
    McpAdapter,
    ModelEndpoint,
)
from .serializers import (
    AgentActionProposalSerializer,
    AgentPromptConfigSerializer,
    AgentExecutionTraceSerializer,
    KnowledgeChunkSerializer,
    KnowledgeDocumentIngestSerializer,
    KnowledgeDocumentSerializer,
    KnowledgeEntitySerializer,
    KnowledgeRelationSerializer,
    McpAdapterSerializer,
    ModelEndpointSerializer,
)
from .services.langgraph_agent import run_langgraph_agent
from .services.agent_automation import (
    approve_agent_action,
    execute_agent_action,
    plan_agent_actions,
    reject_agent_action,
)
from .services.oauth_connector import (
    complete_oauth_flow,
    get_oauth_flow_status,
    start_oauth_flow,
)
from .services.retrieval import rebuild_document_chunks, search_knowledge_chunks


HTML_TAG_RE = re.compile(r"<[^>]+>")
NON_ALNUM_RE = re.compile(r"[^a-z0-9_+\-]+")
STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "about",
    "have",
    "has",
    "will",
    "your",
    "you",
    "are",
    "can",
    "all",
    "not",
    "use",
    "using",
    "was",
    "were",
    "they",
    "their",
    "them",
    "then",
    "when",
    "what",
}


def _fetch_url_text(url: str, timeout_seconds: int) -> tuple[str, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": "FixItFelixKnowledgeIngest/1.0",
            "Accept": "text/plain,text/html,application/json,*/*",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            raw = response.read().decode(charset, errors="replace")
            content_type = response.headers.get("Content-Type", "")
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return "", f"url_fetch_failed:{exc.__class__.__name__}"

    text = unescape(HTML_TAG_RE.sub(" ", raw)).strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return "", f"url_fetch_empty:{content_type or 'unknown'}"
    return text[:60000], None


def _extract_query_from_messages(messages):
    if not isinstance(messages, list):
        return ""

    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "").lower() != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            text = content.strip()
            if text:
                return text
            continue
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = str(part.get("text") or "").strip()
                    if text:
                        parts.append(text)
            if parts:
                return "\n".join(parts)
    return ""


def _coerce_context_text(context_value):
    if isinstance(context_value, str):
        return context_value
    if isinstance(context_value, (dict, list)):
        try:
            return json.dumps(context_value)
        except (TypeError, ValueError):
            return str(context_value)
    return str(context_value or "")


def _safe_int(value, default, minimum=1, maximum=100):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(minimum, min(parsed, maximum))


def _tokenize_for_entities(text: str):
    normalized = NON_ALNUM_RE.sub(" ", text.lower())
    for token in normalized.split():
        if len(token) < 4 or token in STOPWORDS:
            continue
        yield token


def _mcp_auth_headers(adapter: McpAdapter) -> dict[str, str]:
    headers = {
        "User-Agent": "FixItFelix-MCP-Validator/1.0",
        "Accept": "application/json, text/event-stream, */*",
    }
    config = adapter.auth_config if isinstance(adapter.auth_config, dict) else {}

    if adapter.auth_type == McpAdapter.AUTH_BEARER:
        token = str(config.get("token") or config.get("bearer_token") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif adapter.auth_type == McpAdapter.AUTH_OAUTH2:
        token = str(config.get("access_token") or config.get("token") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    elif adapter.auth_type == McpAdapter.AUTH_API_KEY:
        header_name = str(config.get("header_name") or "X-API-Key").strip()
        value = str(config.get("value") or config.get("api_key") or "").strip()
        if header_name and value:
            headers[header_name] = value

    return headers


def _build_default_model_endpoints():
    return [
        {
            "id": "builtin-langgraph",
            "name": "Backend AI Orchestrator",
            "provider": "langgraph",
            "model_identifier": os.getenv("FELIX_LANGGRAPH_MODEL", "gpt-4o-mini"),
            "label": "Backend AI Orchestrator · GPT-4o Mini",
            "active": True,
        },
        {
            "id": "builtin-google",
            "name": "Google Gemini",
            "provider": "google",
            "model_identifier": os.getenv("FELIX_GOOGLE_MODEL", "gemini-3-flash-preview"),
            "label": "Google · Gemini 3 Flash Preview",
            "active": False,
        },
        {
            "id": "builtin-openai",
            "name": "OpenAI GPT-4.1 Mini",
            "provider": "openai",
            "model_identifier": os.getenv("FELIX_OPENAI_MODEL", "gpt-4.1-mini"),
            "label": "OpenAI · GPT-4.1 Mini",
            "active": False,
        },
        {
            "id": "builtin-anthropic",
            "name": "Anthropic Claude",
            "provider": "anthropic",
            "model_identifier": os.getenv("FELIX_ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
            "label": "Anthropic · Claude 3.5 Sonnet",
            "active": False,
        },
        {
            "id": "builtin-ollama",
            "name": "Ollama Local",
            "provider": "ollama",
            "model_identifier": os.getenv("FELIX_OLLAMA_MODEL", "llama3.1:8b"),
            "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            "label": "Ollama (Local) · Llama 3.1 8B",
            "active": False,
        },
        {
            "id": "builtin-vllm",
            "name": "vLLM Local",
            "provider": "vllm",
            "model_identifier": os.getenv("FELIX_VLLM_MODEL", "Qwen/Qwen2.5-7B-Instruct"),
            "base_url": os.getenv("VLLM_BASE_URL", "http://localhost:8001/v1"),
            "label": "vLLM (Local) · Qwen2.5 7B",
            "active": False,
        },
        {
            "id": "builtin-llamacpp",
            "name": "llama.cpp Local",
            "provider": "llamacpp",
            "model_identifier": os.getenv("FELIX_LLAMACPP_MODEL", "local-model"),
            "base_url": os.getenv("LLAMACPP_BASE_URL", "http://localhost:8088/v1"),
            "label": "llama.cpp (Local) · OpenAI-compatible",
            "active": False,
        },
    ]


class KnowledgeDocumentViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeDocument.objects.all()
    serializer_class = KnowledgeDocumentSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user if self.request.user and self.request.user.is_authenticated else None
        serializer.save(created_by=user)

    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request):
        payload = KnowledgeDocumentIngestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        content = (data.get("content") or "").strip()
        url = (data.get("url") or "").strip()
        metadata = data.get("metadata") or {}
        timeout_seconds = data.get("timeout_seconds", 15)

        source_type = KnowledgeDocument.SOURCE_TEXT
        source_uri = ""
        if url:
            source_type = KnowledgeDocument.SOURCE_URL
            source_uri = url
            if not content:
                fetched_content, fetch_error = _fetch_url_text(url, timeout_seconds)
                content = fetched_content
                if fetch_error:
                    metadata = {**metadata, "url_fetch_error": fetch_error}
                if not content:
                    content = f"URL source registered for deferred retrieval: {url}"

        title = (data.get("title") or "").strip()
        if not title:
            title = url or f"Knowledge document {KnowledgeDocument.objects.count() + 1}"
        title = title[:255]

        user = request.user if request.user and request.user.is_authenticated else None
        document = KnowledgeDocument.objects.create(
            source_type=source_type,
            source_uri=source_uri,
            title=title,
            content=content,
            metadata=metadata,
            created_by=user,
        )

        chunk_stats = rebuild_document_chunks(
            document=document,
            chunk_size=data.get("chunk_size", 120),
            overlap=data.get("overlap", 20),
        )
        serialized = KnowledgeDocumentSerializer(document).data
        return Response(
            {
                "id": document.id,
                "document": serialized,
                "chunking": chunk_stats,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="rechunk")
    def rechunk(self, request, pk=None):
        document = self.get_object()
        chunk_size = _safe_int(request.data.get("chunk_size"), default=120, minimum=1, maximum=2000)
        overlap = _safe_int(request.data.get("overlap"), default=20, minimum=0, maximum=max(chunk_size - 1, 0))
        stats = rebuild_document_chunks(document=document, chunk_size=chunk_size, overlap=overlap)
        return Response(
            {
                "id": document.id,
                "chunking": stats,
            }
        )

    @action(detail=False, methods=["get", "post"], url_path="search")
    def search(self, request):
        query = (
            request.query_params.get("q")
            or request.query_params.get("query")
            or request.data.get("q")
            or request.data.get("query")
            or ""
        )
        query = str(query).strip()
        if not query:
            return Response({"error": "Search query is required."}, status=status.HTTP_400_BAD_REQUEST)

        limit = _safe_int(
            request.query_params.get("limit") or request.data.get("limit"),
            default=6,
            minimum=1,
            maximum=50,
        )
        results = search_knowledge_chunks(query, limit=limit, return_meta=True)
        return Response(results)


class KnowledgeChunkViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeChunk.objects.select_related("document").all()
    serializer_class = KnowledgeChunkSerializer
    permission_classes = [IsAuthenticated]


class KnowledgeEntityViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeEntity.objects.all()
    serializer_class = KnowledgeEntitySerializer
    permission_classes = [IsAuthenticated]


class KnowledgeRelationViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeRelation.objects.select_related("source_entity", "target_entity").all()
    serializer_class = KnowledgeRelationSerializer
    permission_classes = [IsAuthenticated]


class ModelEndpointViewSet(viewsets.ModelViewSet):
    queryset = ModelEndpoint.objects.all()
    serializer_class = ModelEndpointSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        serialized = ModelEndpointSerializer(self.queryset.filter(is_enabled=True), many=True).data

        combined = []
        seen = set()

        for row in serialized:
            provider = str(row.get("provider") or "").strip().lower()
            model_identifier = str(row.get("model_identifier") or "").strip()
            if not provider or not model_identifier:
                continue
            key = f"{provider}:{model_identifier.lower()}"
            if key in seen:
                continue
            seen.add(key)
            combined.append(
                {
                    **row,
                    "model": model_identifier,
                    "label": row.get("name") or f"{provider} · {model_identifier}",
                    "active": bool(row.get("is_default")),
                }
            )

        for builtin in _build_default_model_endpoints():
            provider = str(builtin.get("provider") or "").strip().lower()
            model_identifier = str(builtin.get("model_identifier") or "").strip()
            key = f"{provider}:{model_identifier.lower()}"
            if not provider or not model_identifier or key in seen:
                continue
            seen.add(key)
            combined.append(
                {
                    **builtin,
                    "model": model_identifier,
                    "is_enabled": True,
                    "is_default": bool(builtin.get("active")),
                }
            )

        if combined and not any(bool(item.get("active")) for item in combined):
            combined[0]["active"] = True
        return Response(combined)


class McpAdapterViewSet(viewsets.ModelViewSet):
    queryset = McpAdapter.objects.all()
    serializer_class = McpAdapterSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"], url_path="seed_demo")
    def seed_demo(self, request):
        demo_rows = [
            {
                "name": "Supply Chain Connector",
                "transport": McpAdapter.TRANSPORT_HTTP,
                "base_url": "http://127.0.0.1:9101/mcp",
                "auth_type": McpAdapter.AUTH_NONE,
                "metadata": {
                    "description": "External supply chain availability and order placement.",
                    "domain": "supply_chain",
                },
            },
            {
                "name": "Ticket Operations Connector",
                "transport": McpAdapter.TRANSPORT_HTTP,
                "base_url": "http://127.0.0.1:9102/mcp",
                "auth_type": McpAdapter.AUTH_NONE,
                "metadata": {
                    "description": "External ticket intake and synchronization.",
                    "domain": "ticketing",
                },
            },
            {
                "name": "Workforce Connector",
                "transport": McpAdapter.TRANSPORT_HTTP,
                "base_url": "http://127.0.0.1:9103/mcp",
                "auth_type": McpAdapter.AUTH_NONE,
                "metadata": {
                    "description": "Employee roster and availability orchestration.",
                    "domain": "employee_management",
                },
            },
        ]
        created = 0
        updated = 0
        for row in demo_rows:
            adapter, was_created = McpAdapter.objects.get_or_create(
                name=row["name"],
                defaults=row,
            )
            if was_created:
                created += 1
                continue
            changed = False
            for key in ("transport", "base_url", "auth_type", "metadata"):
                value = row[key]
                if getattr(adapter, key) != value:
                    setattr(adapter, key, value)
                    changed = True
            if not adapter.is_enabled:
                adapter.is_enabled = True
                changed = True
            if changed:
                adapter.save()
                updated += 1

        serialized = McpAdapterSerializer(McpAdapter.objects.filter(name__in=[x["name"] for x in demo_rows]), many=True).data
        return Response(
            {
                "ok": True,
                "created": created,
                "updated": updated,
                "adapters": serialized,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="test_connection")
    def test_connection(self, request, pk=None):
        adapter = self.get_object()
        if adapter.auth_type == McpAdapter.AUTH_OAUTH2:
            config = adapter.auth_config if isinstance(adapter.auth_config, dict) else {}
            if not str(config.get("access_token") or "").strip():
                return Response(
                    {
                        "ok": False,
                        "status_code": 401,
                        "error": "OAuth token is not configured.",
                        "hint": "Start OAuth in Agent Studio and then store the returned access token.",
                    }
                )

        headers = _mcp_auth_headers(adapter)
        headers["Content-Type"] = "application/json"
        initialize_payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "healthcheck",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "fix-it-felix", "version": "0.1.0"},
                },
            }
        ).encode("utf-8")
        req = Request(adapter.base_url, headers=headers, data=initialize_payload, method="POST")

        try:
            with urlopen(req, timeout=10) as response:
                status_code = int(response.getcode() or 0)
        except HTTPError as exc:
            status_code = int(exc.code or 0)
            hint = ""
            if status_code == 401 and "githubcopilot.com/mcp" in adapter.base_url.lower():
                hint = (
                    "GitHub MCP rejected the request. Configure bearer auth with a valid GitHub token "
                    "or OAuth-capable client flow."
                )
            return Response(
                {
                    "ok": False,
                    "status_code": status_code,
                    "error": str(exc.reason or "HTTPError"),
                    "hint": hint,
                }
            )
        except URLError as exc:
            return Response(
                {
                    "ok": False,
                    "status_code": 0,
                    "error": str(exc.reason or "ConnectionError"),
                    "hint": "Could not reach MCP endpoint. Check URL, server health, and network routing.",
                }
            )
        except TimeoutError:
            return Response(
                {
                    "ok": False,
                    "status_code": 0,
                    "error": "Timeout",
                    "hint": "MCP endpoint timed out. Verify server availability and latency.",
                }
            )

        return Response(
            {
                "ok": 200 <= status_code < 400,
                "status_code": status_code,
                "error": "" if 200 <= status_code < 400 else f"HTTP {status_code}",
                "hint": "",
            }
        )

    @action(detail=True, methods=["post"], url_path="start_oauth")
    def start_oauth(self, request, pk=None):
        adapter = self.get_object()
        if adapter.auth_type != McpAdapter.AUTH_OAUTH2:
            return Response(
                {"ok": False, "error": "Adapter auth_type must be oauth2.", "hint": ""},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = adapter.auth_config if isinstance(adapter.auth_config, dict) else {}
        user_id = request.user.id if request.user and request.user.is_authenticated else None
        redirect_uri = request.build_absolute_uri(f"/api/ai/mcp_adapters/{adapter.id}/oauth_callback/")
        result = start_oauth_flow(
            adapter_id=adapter.id,
            mcp_url=adapter.base_url,
            auth_config=config,
            redirect_uri=redirect_uri,
            user_id=user_id,
        )

        response = {
            "ok": result.ok,
            "authorization_url": result.authorization_url,
            "state": result.state,
            "expires_in": result.expires_in,
            "error": result.error,
            "hint": result.hint,
        }
        if result.ok:
            return Response(response)
        return Response(response, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="oauth_status")
    def oauth_status(self, request, pk=None):
        adapter = self.get_object()
        if adapter.auth_type != McpAdapter.AUTH_OAUTH2:
            return Response(
                {"ok": False, "status": "error", "error": "Adapter auth_type must be oauth2."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        state_value = str(request.query_params.get("state") or "").strip()
        if not state_value:
            return Response(
                {"ok": False, "status": "error", "error": "state is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = request.user.id if request.user and request.user.is_authenticated else None
        status_result = get_oauth_flow_status(
            state=state_value,
            adapter_id=adapter.id,
            user_id=user_id,
        )
        response = {
            "ok": status_result.ok,
            "status": status_result.status,
            "error": status_result.error,
            "has_access_token": status_result.has_access_token,
        }
        if status_result.ok:
            return Response(response)
        if status_result.status == "expired":
            return Response(response, status=status.HTTP_404_NOT_FOUND)
        return Response(response, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=["get"],
        url_path="oauth_callback",
        permission_classes=[AllowAny],
        authentication_classes=[],
    )
    def oauth_callback(self, request, pk=None):
        adapter = self.get_object()
        state_value = str(request.query_params.get("state") or "").strip()
        code_value = str(request.query_params.get("code") or "").strip()
        error_value = str(request.query_params.get("error") or "").strip()
        error_description = str(request.query_params.get("error_description") or "").strip()

        if not state_value:
            return HttpResponse(
                self._oauth_callback_html(
                    ok=False,
                    title="Authorization failed",
                    message="Missing OAuth state. Restart the OAuth flow from Agent Studio.",
                ),
                status=400,
                content_type="text/html; charset=utf-8",
            )

        result = complete_oauth_flow(
            state=state_value,
            code=code_value,
            error=error_value,
            error_description=error_description,
        )

        if not result.ok:
            return HttpResponse(
                self._oauth_callback_html(
                    ok=False,
                    title="Authorization failed",
                    message=result.error or "OAuth callback could not complete.",
                ),
                status=400,
                content_type="text/html; charset=utf-8",
            )

        if int(result.adapter_id or -1) != int(adapter.id):
            return HttpResponse(
                self._oauth_callback_html(
                    ok=False,
                    title="Authorization failed",
                    message="OAuth session does not match this adapter.",
                ),
                status=400,
                content_type="text/html; charset=utf-8",
            )

        config = dict(adapter.auth_config) if isinstance(adapter.auth_config, dict) else {}
        config["access_token"] = result.access_token
        if result.refresh_token:
            config["refresh_token"] = result.refresh_token
        if result.token_type:
            config["token_type"] = result.token_type
        if result.scope:
            config["scope"] = result.scope
        if isinstance(result.expires_in, int):
            config["expires_in"] = result.expires_in
            config["expires_at_epoch"] = int(timezone.now().timestamp()) + result.expires_in
        if result.authorization_endpoint:
            config["authorize_url"] = result.authorization_endpoint
        if result.token_endpoint:
            config["token_url"] = result.token_endpoint
        config["oauth_last_authorized_at"] = timezone.now().isoformat()
        adapter.auth_config = config
        adapter.save(update_fields=["auth_config", "updated_at"])

        return HttpResponse(
            self._oauth_callback_html(
                ok=True,
                title="Authorization successful",
                message="You can return to Agent Studio. This window will close automatically.",
            ),
            status=200,
            content_type="text/html; charset=utf-8",
        )

    @staticmethod
    def _oauth_callback_html(*, ok: bool, title: str, message: str) -> str:
        badge = "#16a34a" if ok else "#dc2626"
        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      body {{
        margin: 0;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
        background: #0b1020;
        color: #e5e7eb;
        display: grid;
        place-items: center;
        min-height: 100vh;
      }}
      .card {{
        width: min(92vw, 560px);
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 12px;
        padding: 20px;
      }}
      .badge {{
        display: inline-block;
        font-size: 12px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 999px;
        background: {badge};
        color: #fff;
        margin-bottom: 12px;
      }}
      h1 {{ margin: 0 0 8px 0; font-size: 20px; }}
      p {{ margin: 0; color: #cbd5e1; line-height: 1.5; }}
    </style>
  </head>
  <body>
    <div class="card">
      <span class="badge">{'Success' if ok else 'Error'}</span>
      <h1>{title}</h1>
      <p>{message}</p>
    </div>
    <script>
      if ({'true' if ok else 'false'}) {{
        setTimeout(() => window.close(), 1200);
      }}
    </script>
  </body>
</html>"""

    @action(detail=True, methods=["post"], url_path="oauth_token")
    def oauth_token(self, request, pk=None):
        adapter = self.get_object()
        if adapter.auth_type != McpAdapter.AUTH_OAUTH2:
            return Response(
                {"ok": False, "error": "Adapter auth_type must be oauth2."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        access_token = str(request.data.get("access_token") or "").strip()
        refresh_token = str(request.data.get("refresh_token") or "").strip()
        if not access_token:
            return Response(
                {"ok": False, "error": "access_token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        config = dict(adapter.auth_config) if isinstance(adapter.auth_config, dict) else {}
        config["access_token"] = access_token
        if refresh_token:
            config["refresh_token"] = refresh_token
        adapter.auth_config = config
        adapter.save(update_fields=["auth_config", "updated_at"])

        return Response(
            {
                "ok": True,
                "id": adapter.id,
                "has_access_token": True,
            }
        )


class KnowledgeGraphViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response(
            {
                "documents": KnowledgeDocument.objects.count(),
                "entities": KnowledgeEntity.objects.count(),
                "relations": KnowledgeRelation.objects.count(),
            }
        )

    def create(self, request):
        return self._ingest_payload(request)

    @action(detail=False, methods=["post"], url_path="expand")
    def expand(self, request):
        return self._ingest_payload(request)

    @action(detail=False, methods=["post"], url_path="add")
    def add(self, request):
        return self._ingest_payload(request)

    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request):
        return self._ingest_payload(request)

    def _ingest_payload(self, request):
        content = str(request.data.get("content") or request.data.get("text") or "").strip()
        context = str(request.data.get("context") or "").strip()
        if not content:
            return Response({"error": "content is required."}, status=status.HTTP_400_BAD_REQUEST)

        metadata = {
            "ingestion_source": "knowledge_graph",
            "provider": request.data.get("provider"),
            "model": request.data.get("model"),
            "urls": request.data.get("urls") or [],
            "mcp_adapters": request.data.get("mcp_adapters") or [],
            "snippets": request.data.get("snippets") or [],
        }
        if context:
            metadata["context_preview"] = context[:1500]

        user = request.user if request.user and request.user.is_authenticated else None
        title = content.splitlines()[0][:255] if content.splitlines() else f"Knowledge graph note {KnowledgeDocument.objects.count() + 1}"
        merged_content = content if not context else f"{content}\n\nContext:\n{context}"

        with transaction.atomic():
            document = KnowledgeDocument.objects.create(
                source_type=KnowledgeDocument.SOURCE_OTHER,
                title=title,
                content=merged_content,
                metadata=metadata,
                created_by=user,
            )
            chunking = rebuild_document_chunks(document=document, chunk_size=120, overlap=20)

            terms = []
            seen_terms = set()
            for token in _tokenize_for_entities(merged_content):
                if token in seen_terms:
                    continue
                seen_terms.add(token)
                terms.append(token)
                if len(terms) >= 14:
                    break

            entities = []
            for term in terms:
                entity, _ = KnowledgeEntity.objects.get_or_create(
                    name=term,
                    entity_type="term",
                    defaults={"metadata": {"source": "knowledge_graph_ingest"}},
                )
                entities.append(entity)

            relation_count = 0
            for idx in range(len(entities) - 1):
                source = entities[idx]
                target = entities[idx + 1]
                relation, created = KnowledgeRelation.objects.get_or_create(
                    source_entity=source,
                    target_entity=target,
                    relation_type="related_to",
                    defaults={"weight": 1.0, "metadata": {"source_document_id": document.id}},
                )
                if not created:
                    relation.weight = round(float(relation.weight) + 0.1, 3)
                    relation.save(update_fields=["weight"])
                relation_count += 1

        return Response(
            {
                "ok": True,
                "document_id": document.id,
                "entities_upserted": len(entities),
                "relations_upserted": relation_count,
                "chunking": chunking,
            },
            status=status.HTTP_201_CREATED,
        )


class AgentActionProposalViewSet(viewsets.ModelViewSet):
    queryset = AgentActionProposal.objects.select_related("created_by", "approved_by").prefetch_related("traces")
    serializer_class = AgentActionProposalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = self.queryset
        status_value = str(self.request.query_params.get("status") or "").strip().lower()
        action_type = str(self.request.query_params.get("action_type") or "").strip().lower()
        if status_value:
            queryset = queryset.filter(status=status_value)
        if action_type:
            queryset = queryset.filter(action_type=action_type)
        return queryset

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        proposal = self.get_object()
        proposal = approve_agent_action(proposal, actor=request.user)
        return Response(self.get_serializer(proposal).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        proposal = self.get_object()
        reason = str(request.data.get("reason") or "").strip()
        proposal = reject_agent_action(proposal, actor=request.user, reason=reason)
        return Response(self.get_serializer(proposal).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="execute")
    def execute(self, request, pk=None):
        proposal = self.get_object()
        proposal = execute_agent_action(proposal, actor=request.user)
        return Response(self.get_serializer(proposal).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="trace")
    def trace(self, request, pk=None):
        proposal = self.get_object()
        traces = AgentExecutionTrace.objects.filter(proposal=proposal).order_by("-created_at")
        return Response(AgentExecutionTraceSerializer(traces, many=True).data, status=status.HTTP_200_OK)


class AgentPromptCurrentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        prompt = AgentPromptConfig.get_current()
        return Response(AgentPromptConfigSerializer(prompt).data)

    def put(self, request):
        prompt = AgentPromptConfig.get_current()
        serializer = AgentPromptConfigSerializer(prompt, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AIChatAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}

        query = str(payload.get("query") or "").strip()
        if not query:
            query = _extract_query_from_messages(payload.get("messages"))
        if not query:
            return Response({"error": "A user query is required."}, status=status.HTTP_400_BAD_REQUEST)

        raw_context = payload.get("context", "")
        if isinstance(raw_context, dict):
            context_payload = dict(raw_context)
        elif isinstance(raw_context, str):
            try:
                parsed = json.loads(raw_context)
                context_payload = parsed if isinstance(parsed, dict) else {"context_block": raw_context}
            except json.JSONDecodeError:
                context_payload = {"context_block": raw_context}
        else:
            context_payload = {"context_block": _coerce_context_text(raw_context)}

        prompt_config = AgentPromptConfig.get_current()
        context_payload.setdefault("system_prompt", prompt_config.system_prompt)
        context_payload.setdefault("domain_guardrail_prompt", prompt_config.domain_guardrail_prompt)
        selected_mcp_adapter_ids: list[str] = []
        for candidate in (
            payload.get("mcp_adapters"),
            context_payload.get("mcp_adapters"),
            context_payload.get("mcp_adapter"),
        ):
            if isinstance(candidate, list):
                selected_mcp_adapter_ids.extend(str(item).strip() for item in candidate if str(item).strip())
            elif isinstance(candidate, str) and candidate.strip():
                selected_mcp_adapter_ids.append(candidate.strip())
        deduped_adapter_ids: list[str] = []
        seen_adapters = set()
        for adapter_id in selected_mcp_adapter_ids:
            if adapter_id in seen_adapters:
                continue
            seen_adapters.add(adapter_id)
            deduped_adapter_ids.append(adapter_id)
        context_payload["mcp_adapters"] = deduped_adapter_ids
        context = json.dumps(context_payload)
        provider = str(payload.get("provider") or "").strip().lower() or None
        model = str(payload.get("model") or "").strip() or None
        retrieval_limit = _safe_int(payload.get("retrieval_limit", 6), default=6, minimum=1, maximum=20)

        try:
            result = run_langgraph_agent(
                query=query,
                context=context,
                provider=provider,
                model=model,
                retrieval_limit=retrieval_limit,
            )
            planning_error = ""
            planning_result = None
            try:
                planning_result = plan_agent_actions(
                    query=query,
                    context_payload=context_payload,
                    selected_mcp_adapter_ids=deduped_adapter_ids,
                    user=request.user,
                )
            except Exception as exc:
                planning_error = str(exc)

            proposals = []
            telemetry = {
                "adapters_selected": deduped_adapter_ids,
                "reads": [],
                "planning_error": planning_error,
            }
            if planning_result:
                proposals = AgentActionProposalSerializer(planning_result.proposals, many=True).data
                telemetry["reads"] = planning_result.mcp_reads

            return Response(
                {
                    **result,
                    "proposals": proposals,
                    "telemetry": telemetry,
                },
                status=status.HTTP_200_OK,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
