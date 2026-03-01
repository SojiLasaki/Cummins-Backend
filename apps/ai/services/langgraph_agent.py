import json
import os
import re
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from apps.ai.models import McpAdapter, ModelEndpoint
from apps.ai.services.retrieval import search_knowledge_chunks


class AgentState(TypedDict, total=False):
    query: str
    context: str
    provider: str
    model: str
    base_url: str
    api_key: str
    retrieval_limit: int
    snippets: list[dict[str, Any]]
    blocked: bool
    guardrail_message: str
    answer: str


MCP_HINT_KEYS = ("mcp_adapter", "mcp_adapters", "adapter_hint", "adapter_hints")
MAX_PROMPT_SNIPPETS = 6
MAX_SNIPPET_CHARS = 420
MAX_CONTEXT_CHARS = 1400
MCP_TAG_PATTERN = re.compile(r"\[\[\s*mcp\s*:\s*([A-Za-z0-9._:-]+)\s*\]\]", re.IGNORECASE)
MCP_INLINE_PATTERN = re.compile(
    r"\b(?:mcp(?:_adapter(?:s)?)?|adapter(?:s)?)\s*[:=]\s*([^\n\r;]+)",
    re.IGNORECASE,
)
MCP_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9._:-]+")
WHITESPACE_PATTERN = re.compile(r"\s+")
DOMAIN_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_+-]+")
FAULT_CODE_PATTERN = re.compile(r"\b(?:tk-\d+|spn\s*\d+|fmi\s*\d+|p\d{4})\b", re.IGNORECASE)

DOMAIN_STRONG_KEYWORDS = {
    "cummins",
    "diesel",
    "engine",
    "x15",
    "isx",
    "isb",
    "ism",
    "qsk",
    "aftertreatment",
    "dpf",
    "scr",
    "ecm",
    "injector",
    "turbo",
    "turbocharger",
    "coolant",
    "oil",
    "filter",
    "fault",
    "diagnostic",
    "diagnostics",
    "technician",
    "maintenance",
    "service",
}

DOMAIN_WEAK_KEYWORDS = {
    "repair",
    "replace",
    "troubleshoot",
    "component",
    "parts",
    "procedure",
    "manual",
    "checklist",
}

ADDITIONAL_DOMAIN_KEYWORDS = {
    token.strip().lower()
    for token in os.getenv("FELIX_DOMAIN_KEYWORDS", "").split(",")
    if token.strip()
}

DOMAIN_GUARDRAIL_MESSAGE = (
    "# Out-of-Scope Request\n\n"
    "1. I can only help with Cummins diagnostics, repair procedures, parts, maintenance, and service operations. [GEN]\n"
    "2. Rephrase your question with equipment details, fault codes, symptoms, or service tasks. [GEN]"
)


def _trim_text(text: Any, max_chars: int) -> str:
    normalized = WHITESPACE_PATTERN.sub(" ", str(text or "")).strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3].rstrip() + "..."


def _parse_json_context(context: str) -> dict[str, Any]:
    text = (context or "").strip()
    if not text or (not text.startswith("{") and not text.startswith("[")):
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _extract_prompt_overrides(context: str) -> tuple[str | None, str | None]:
    payload = _parse_json_context(context)
    system_prompt = payload.get("system_prompt")
    guardrail_prompt = payload.get("domain_guardrail_prompt")
    normalized_system = _trim_text(system_prompt, 4000) if isinstance(system_prompt, str) else None
    normalized_guardrail = _trim_text(guardrail_prompt, 2000) if isinstance(guardrail_prompt, str) else None
    return normalized_system, normalized_guardrail


def _domain_tokens(text: Any) -> set[str]:
    return {token.lower() for token in DOMAIN_TOKEN_PATTERN.findall(str(text or ""))}


def _domain_matches(tokens: set[str]) -> tuple[set[str], set[str]]:
    strong = {token for token in tokens if token in DOMAIN_STRONG_KEYWORDS or token in ADDITIONAL_DOMAIN_KEYWORDS}
    weak = {token for token in tokens if token in DOMAIN_WEAK_KEYWORDS}
    return strong, weak


def _snippet_has_domain_signal(snippets: list[dict[str, Any]]) -> bool:
    for snippet in snippets[:MAX_PROMPT_SNIPPETS]:
        combined = f"{snippet.get('document_title', '')} {snippet.get('content', '')}"
        strong, _ = _domain_matches(_domain_tokens(combined))
        if strong:
            return True
    return False


def _extract_guardrail_context_text(raw_context: str) -> str:
    payload = _parse_json_context(raw_context)
    if not payload:
        return raw_context

    parts = []
    for key in ("context_block", "user_context", "ticket_context"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    return "\n".join(parts)


def _is_domain_allowed(state: AgentState) -> bool:
    query_text = str(state.get("query", "") or "")
    if FAULT_CODE_PATTERN.search(query_text):
        return True

    query_tokens = _domain_tokens(query_text)
    context_text = _extract_guardrail_context_text(str(state.get("context", "") or ""))
    context_tokens = _domain_tokens(context_text)
    query_strong, query_weak = _domain_matches(query_tokens)
    context_strong, _ = _domain_matches(context_tokens)

    if query_strong:
        return True
    if len(query_weak) >= 2:
        return True
    if query_weak and context_strong:
        return True
    return False


def _extract_mcp_hint_tokens(context: str) -> list[str]:
    text = (context or "").strip()
    if not text:
        return []

    candidates: list[str] = []
    if text.startswith("{") or text.startswith("["):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            for key in MCP_HINT_KEYS:
                value = payload.get(key)
                if isinstance(value, str):
                    candidates.extend(MCP_TOKEN_PATTERN.findall(value))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            candidates.extend(MCP_TOKEN_PATTERN.findall(item))

    for match in MCP_TAG_PATTERN.finditer(text):
        candidates.append(match.group(1))

    for match in MCP_INLINE_PATTERN.finditer(text):
        candidates.extend(MCP_TOKEN_PATTERN.findall(match.group(1)))

    deduped: list[str] = []
    seen: set[str] = set()
    for token in candidates:
        normalized = token.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(token.strip())
    return deduped


def _build_mcp_hints_block(context: str) -> str:
    tokens = _extract_mcp_hint_tokens(context)
    if not tokens:
        return ""

    adapters = list(
        McpAdapter.objects.filter(is_enabled=True).values("name", "transport", "base_url", "metadata")
    )
    if not adapters:
        return ""

    by_exact_name = {str(adapter["name"]).lower(): adapter for adapter in adapters}
    lines: list[str] = []
    used: set[str] = set()
    placeholder_index = 1

    for token in tokens:
        normalized = token.lower()
        adapter = by_exact_name.get(normalized)
        if not adapter:
            matches = [row for row in adapters if normalized in str(row["name"]).lower()]
            if len(matches) == 1:
                adapter = matches[0]
        if not adapter:
            continue

        adapter_name = str(adapter["name"])
        if adapter_name in used:
            continue
        used.add(adapter_name)

        metadata = adapter.get("metadata") if isinstance(adapter.get("metadata"), dict) else {}
        hint_text = ""
        if metadata:
            hint_text = metadata.get("hint") or metadata.get("description") or ""
        hint_suffix = f" | hint={_trim_text(hint_text, 120)}" if hint_text else ""
        lines.append(
            f"[M{placeholder_index}] name={adapter_name} transport={adapter.get('transport')} "
            f"base_url={adapter.get('base_url')}{hint_suffix}"
        )
        placeholder_index += 1

    if not lines:
        return ""
    return "MCP adapter hints:\n" + "\n".join(lines)


def _build_snippet_block(snippets: list[dict[str, Any]], retrieval_limit: int) -> str:
    if not snippets:
        return "Retrieved snippets:\n(none)"

    prompt_limit = max(1, min(int(retrieval_limit), MAX_PROMPT_SNIPPETS))
    lines = []
    for index, snippet in enumerate(snippets[:prompt_limit], start=1):
        title = _trim_text(snippet.get("document_title", "Untitled"), 100)
        source = _trim_text(snippet.get("document_source_uri") or "n/a", 180)
        excerpt = _trim_text(snippet.get("content", ""), MAX_SNIPPET_CHARS)
        chunk_index = snippet.get("chunk_index", "n/a")
        score = snippet.get("score", 0)
        lines.append(
            f"[S{index}] title={title} chunk={chunk_index} score={score} source={source}\n"
            f"excerpt: {excerpt}"
        )
    return "Retrieved snippets:\n" + "\n".join(lines)


def _build_human_prompt(state: AgentState) -> str:
    query = _trim_text(state.get("query", ""), 600)
    raw_context = str(state.get("context", "") or "")
    parsed_context = _parse_json_context(raw_context)
    context_source = raw_context
    if parsed_context:
        context_block = parsed_context.get("context_block")
        if isinstance(context_block, str) and context_block.strip():
            context_source = context_block
    context = _trim_text(context_source, MAX_CONTEXT_CHARS)
    snippets = state.get("snippets", [])
    retrieval_limit = max(int(state.get("retrieval_limit", 6)), 1)

    blocks = [f"Question:\n{query}"]
    if context:
        blocks.append(f"User context:\n{context}")

    mcp_hint_block = _build_mcp_hints_block(raw_context)
    if mcp_hint_block:
        blocks.append(mcp_hint_block)

    blocks.append(_build_snippet_block(snippets, retrieval_limit))
    return "\n\n".join(blocks)


def _resolve_model_config(provider: str | None, model: str | None):
    queryset = ModelEndpoint.objects.filter(is_enabled=True)
    if provider:
        queryset = queryset.filter(provider=provider)
    if model:
        queryset = queryset.filter(model_identifier=model)
    endpoint = queryset.order_by("-is_default", "name").first()

    resolved_provider = provider or (endpoint.provider if endpoint else "openai")
    resolved_model = model or (endpoint.model_identifier if endpoint else "gpt-4o-mini")
    base_url = endpoint.base_url if endpoint and endpoint.base_url else None

    key = None
    if endpoint and endpoint.api_key_env:
        key = os.getenv(endpoint.api_key_env)
    if not key:
        key = os.getenv("OPENAI_API_KEY")
    if not key and base_url:
        # OpenAI-compatible local endpoints (ollama/vllm/llama.cpp) often ignore API keys
        key = "local-dev-key"

    return {
        "provider": resolved_provider,
        "model": resolved_model,
        "base_url": base_url,
        "api_key": key,
    }


def _retrieve_node(state: AgentState) -> AgentState:
    query = state.get("query", "").strip()
    if not query:
        return {"snippets": []}
    limit = max(int(state.get("retrieval_limit", 6)), 1)
    return {"snippets": search_knowledge_chunks(query, limit=limit)}


def _guardrail_node(state: AgentState) -> AgentState:
    _, guardrail_override = _extract_prompt_overrides(str(state.get("context", "") or ""))
    guardrail_message = guardrail_override or DOMAIN_GUARDRAIL_MESSAGE
    if _is_domain_allowed(state):
        return {"blocked": False, "guardrail_message": ""}
    return {
        "blocked": True,
        "guardrail_message": guardrail_message,
        "snippets": [],
    }


def _answer_node(state: AgentState) -> AgentState:
    if state.get("blocked"):
        return {"answer": state.get("guardrail_message", DOMAIN_GUARDRAIL_MESSAGE)}

    api_key = state.get("api_key")
    if not api_key:
        raise ValueError("OPENAI_API_KEY (or configured model endpoint key) is missing.")

    llm = ChatOpenAI(
        api_key=api_key,
        model=state.get("model", "gpt-4o-mini"),
        base_url=state.get("base_url") or None,
        temperature=0.2,
    )

    default_system_prompt = (
        "You are Fix it Felix, an expert repair copilot. "
        "Return concise markdown with a short heading and numbered actions only. "
        "Each numbered action must end with citation placeholders, preferring [S#] for retrieved snippets, "
        "then [CTX] for user context and [M#] for MCP hints. "
        "If no supporting source exists, use [GEN]. "
        "Do not invent placeholder ids beyond what is provided."
    )
    system_override, _ = _extract_prompt_overrides(str(state.get("context", "") or ""))
    system_prompt = system_override or default_system_prompt
    human_prompt = _build_human_prompt(state)
    response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)])
    return {"answer": response.content if isinstance(response.content, str) else str(response.content)}


def run_langgraph_agent(
    *,
    query: str,
    context: str = "",
    provider: str | None = None,
    model: str | None = None,
    retrieval_limit: int = 6,
):
    config = _resolve_model_config(provider, model)

    graph_builder: StateGraph = StateGraph(AgentState)
    graph_builder.add_node("retrieve", _retrieve_node)
    graph_builder.add_node("guardrail", _guardrail_node)
    graph_builder.add_node("answer", _answer_node)
    graph_builder.add_edge(START, "retrieve")
    graph_builder.add_edge("retrieve", "guardrail")
    graph_builder.add_edge("guardrail", "answer")
    graph_builder.add_edge("answer", END)
    graph = graph_builder.compile()

    state: AgentState = {
        "query": query,
        "context": context,
        "provider": config["provider"],
        "model": config["model"],
        "base_url": config["base_url"],
        "api_key": config["api_key"],
        "retrieval_limit": retrieval_limit,
    }
    result = graph.invoke(state)

    return {
        "answer": result.get("answer", ""),
        "snippets": result.get("snippets", []),
        "provider": config["provider"],
        "model": config["model"],
    }
