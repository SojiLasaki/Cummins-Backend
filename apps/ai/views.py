import json
import os
import re
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AgentPromptConfig,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeRelation,
    McpAdapter,
    ModelEndpoint,
)
from .serializers import (
    AgentPromptConfigSerializer,
    KnowledgeChunkSerializer,
    KnowledgeDocumentIngestSerializer,
    KnowledgeDocumentSerializer,
    KnowledgeEntitySerializer,
    KnowledgeRelationSerializer,
    McpAdapterSerializer,
    ModelEndpointSerializer,
)
from .services.langgraph_agent import run_langgraph_agent
from .services.fastmcp_oauth import start_fastmcp_oauth
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
            "name": "LangGraph Backend",
            "provider": "langgraph",
            "model_identifier": os.getenv("FELIX_LANGGRAPH_MODEL", "gpt-4o-mini"),
            "label": "LangGraph (Backend) · GPT-4o Mini",
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
        result = start_fastmcp_oauth(
            mcp_url=adapter.base_url,
            client_id=str(config.get("client_id") or "").strip() or None,
            client_secret=str(config.get("client_secret") or "").strip() or None,
            scopes=config.get("scopes"),
            callback_port=_safe_int(config.get("callback_port", 8765), default=8765, minimum=1024, maximum=65535),
        )

        response = {
            "ok": result.ok,
            "authorization_url": result.authorization_url,
            "error": result.error,
            "hint": result.hint,
        }
        if result.ok:
            return Response(response)
        return Response(response, status=status.HTTP_400_BAD_REQUEST)

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
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
