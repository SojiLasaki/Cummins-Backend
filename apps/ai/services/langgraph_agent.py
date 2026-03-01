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
    policy_mode: str
    intent: str
    context_refs: list[str]
    enabled_connectors: list[str]
    diagnostic_summary: str
    learning_summary: str
    agent_trace: list[dict[str, Any]]
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
ALLOWED_POLICY_MODES = {"manual", "semi_auto", "auto"}
ALLOWED_INTENTS = {"qa", "triage", "ticket_ops", "parts_ops", "assignment_ops"}

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


def _normalize_policy_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_POLICY_MODES else "manual"


def _normalize_intent(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALLOWED_INTENTS else "qa"


def _coerce_context_refs(payload: dict[str, Any] | None, state_refs: Any = None) -> list[str]:
    refs: list[str] = []
    candidates: list[Any] = []
    if isinstance(state_refs, list):
        candidates.extend(state_refs)
    elif isinstance(state_refs, str):
        candidates.append(state_refs)
    if isinstance(payload, dict):
        raw_refs = payload.get("context_refs")
        if isinstance(raw_refs, list):
            candidates.extend(raw_refs)
        elif isinstance(raw_refs, str):
            candidates.append(raw_refs)
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        text = str(candidate or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text[:280])
    return deduped


def _trace(
    state: AgentState,
    *,
    agent: str,
    status: str = "ok",
    detail: str = "",
    outputs: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    entries = list(state.get("agent_trace") or [])
    entries.append(
        {
            "agent": agent,
            "status": status,
            "detail": _trim_text(detail, 240),
            "outputs": outputs or {},
        }
    )
    return entries


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
    context_refs = state.get("context_refs", [])
    enabled_connectors = state.get("enabled_connectors", [])

    blocks = [f"Question:\n{query}"]
    if context:
        blocks.append(f"User context:\n{context}")
    if context_refs:
        blocks.append("Context references:\n" + "\n".join(f"- {ref}" for ref in context_refs[:8]))
    if enabled_connectors:
        blocks.append("Enabled connectors:\n" + "\n".join(f"- {name}" for name in enabled_connectors[:12]))
    diagnostic_summary = _trim_text(state.get("diagnostic_summary", ""), 600)
    if diagnostic_summary:
        blocks.append(f"Diagnostic summary:\n{diagnostic_summary}")
    learning_summary = _trim_text(state.get("learning_summary", ""), 600)
    if learning_summary:
        blocks.append(f"Learning summary:\n{learning_summary}")

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
        return {"snippets": [], "agent_trace": _trace(state, agent="retrieve", status="skip", detail="No query provided.")}
    limit = max(int(state.get("retrieval_limit", 6)), 1)
    snippets = search_knowledge_chunks(query, limit=limit)
    return {
        "snippets": snippets,
        "agent_trace": _trace(
            state,
            agent="retrieve",
            detail=f"Retrieved {len(snippets)} snippets.",
            outputs={"snippet_count": len(snippets)},
        ),
    }


def _intake_node(state: AgentState) -> AgentState:
    payload = _parse_json_context(str(state.get("context", "") or ""))
    policy_mode = _normalize_policy_mode(state.get("policy_mode") or payload.get("policy_mode"))
    intent = _normalize_intent(state.get("intent") or payload.get("intent"))
    context_refs = _coerce_context_refs(payload, state.get("context_refs"))

    enabled_connectors: list[str] = []
    for candidate in (
        state.get("enabled_connectors"),
        payload.get("enabled_connectors"),
        payload.get("mcp_adapters"),
        payload.get("mcp_adapter"),
    ):
        if isinstance(candidate, list):
            enabled_connectors.extend(str(item).strip() for item in candidate if str(item).strip())
        elif isinstance(candidate, str) and candidate.strip():
            enabled_connectors.append(candidate.strip())
    deduped_connectors: list[str] = []
    seen_connectors: set[str] = set()
    for connector in enabled_connectors:
        if connector in seen_connectors:
            continue
        seen_connectors.add(connector)
        deduped_connectors.append(connector)

    return {
        "intent": intent,
        "policy_mode": policy_mode,
        "context_refs": context_refs,
        "enabled_connectors": deduped_connectors,
        "agent_trace": _trace(
            state,
            agent="intake",
            detail=f"Intent={intent}, policy_mode={policy_mode}, connectors={len(deduped_connectors)}.",
            outputs={"intent": intent, "policy_mode": policy_mode, "context_refs": len(context_refs)},
        ),
    }


def _guardrail_node(state: AgentState) -> AgentState:
    _, guardrail_override = _extract_prompt_overrides(str(state.get("context", "") or ""))
    guardrail_message = guardrail_override or DOMAIN_GUARDRAIL_MESSAGE
    if _is_domain_allowed(state):
        return {
            "blocked": False,
            "guardrail_message": "",
            "agent_trace": _trace(state, agent="guardrail", detail="Domain request allowed."),
        }
    return {
        "blocked": True,
        "guardrail_message": guardrail_message,
        "snippets": [],
        "agent_trace": _trace(
            state,
            agent="guardrail",
            status="blocked",
            detail="Request blocked by domain guardrail.",
        ),
    }


def _diagnostic_node(state: AgentState) -> AgentState:
    if state.get("blocked"):
        return {"agent_trace": _trace(state, agent="diagnostic", status="skip", detail="Guardrail blocked request.")}
    query = str(state.get("query") or "")
    tokens = list(_domain_tokens(query))
    highlighted = ", ".join(tokens[:6]) if tokens else "general service request"
    summary = (
        f"Initial triage signals suggest focus on {highlighted}. "
        f"Intent is '{state.get('intent', 'qa')}' with '{state.get('policy_mode', 'manual')}' policy mode."
    )
    return {
        "diagnostic_summary": summary,
        "agent_trace": _trace(state, agent="diagnostic", detail="Generated triage summary."),
    }


def _ticket_agent_node(state: AgentState) -> AgentState:
    if state.get("blocked"):
        return {"agent_trace": _trace(state, agent="ticket_agent", status="skip", detail="Guardrail blocked request.")}
    intent = str(state.get("intent") or "qa")
    if intent in {"ticket_ops", "triage", "qa"}:
        return {"agent_trace": _trace(state, agent="ticket_agent", detail="Ticket planning path enabled.")}
    return {"agent_trace": _trace(state, agent="ticket_agent", status="skip", detail="Ticket planning not requested by intent.")}


def _assignment_agent_node(state: AgentState) -> AgentState:
    if state.get("blocked"):
        return {"agent_trace": _trace(state, agent="assignment_agent", status="skip", detail="Guardrail blocked request.")}
    intent = str(state.get("intent") or "qa")
    if intent in {"assignment_ops", "ticket_ops", "triage"}:
        return {"agent_trace": _trace(state, agent="assignment_agent", detail="Assignment recommendation path enabled.")}
    return {"agent_trace": _trace(state, agent="assignment_agent", status="skip", detail="Assignment recommendation not requested.")}


def _supply_chain_agent_node(state: AgentState) -> AgentState:
    if state.get("blocked"):
        return {"agent_trace": _trace(state, agent="supply_chain_agent", status="skip", detail="Guardrail blocked request.")}
    intent = str(state.get("intent") or "qa")
    if intent in {"parts_ops", "ticket_ops", "triage"}:
        return {"agent_trace": _trace(state, agent="supply_chain_agent", detail="Supply chain recommendation path enabled.")}
    return {"agent_trace": _trace(state, agent="supply_chain_agent", status="skip", detail="Supply chain path not requested.")}


def _learning_agent_node(state: AgentState) -> AgentState:
    if state.get("blocked"):
        return {"agent_trace": _trace(state, agent="learning_agent", status="skip", detail="Guardrail blocked request.")}
    snippets = state.get("snippets", [])
    learning_summary = (
        "Capture this resolution pattern into learning memory after ticket completion."
        if snippets
        else "No retrieved snippets. Capture technician notes before adding to learning memory."
    )
    return {
        "learning_summary": learning_summary,
        "agent_trace": _trace(state, agent="learning_agent", detail="Prepared learning-loop recommendation."),
    }


def _answer_node(state: AgentState) -> AgentState:
    if state.get("blocked"):
        return {
            "answer": state.get("guardrail_message", DOMAIN_GUARDRAIL_MESSAGE),
            "agent_trace": _trace(state, agent="answer", status="blocked", detail="Returned guardrail response."),
        }

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
    return {
        "answer": response.content if isinstance(response.content, str) else str(response.content),
        "agent_trace": _trace(state, agent="answer", detail="Returned grounded response."),
    }


def run_langgraph_agent(
    *,
    query: str,
    context: str = "",
    provider: str | None = None,
    model: str | None = None,
    retrieval_limit: int = 6,
    intent: str | None = None,
    policy_mode: str | None = None,
    context_refs: list[str] | None = None,
    enabled_connectors: list[str] | None = None,
):
    config = _resolve_model_config(provider, model)

    graph_builder: StateGraph = StateGraph(AgentState)
    graph_builder.add_node("retrieve", _retrieve_node)
    graph_builder.add_node("intake", _intake_node)
    graph_builder.add_node("guardrail", _guardrail_node)
    graph_builder.add_node("diagnostic", _diagnostic_node)
    graph_builder.add_node("ticket_agent", _ticket_agent_node)
    graph_builder.add_node("assignment_agent", _assignment_agent_node)
    graph_builder.add_node("supply_chain_agent", _supply_chain_agent_node)
    graph_builder.add_node("learning_agent", _learning_agent_node)
    graph_builder.add_node("answer", _answer_node)
    graph_builder.add_edge(START, "retrieve")
    graph_builder.add_edge("retrieve", "intake")
    graph_builder.add_edge("intake", "guardrail")
    graph_builder.add_edge("guardrail", "diagnostic")
    graph_builder.add_edge("diagnostic", "ticket_agent")
    graph_builder.add_edge("ticket_agent", "assignment_agent")
    graph_builder.add_edge("assignment_agent", "supply_chain_agent")
    graph_builder.add_edge("supply_chain_agent", "learning_agent")
    graph_builder.add_edge("learning_agent", "answer")
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
        "policy_mode": _normalize_policy_mode(policy_mode),
        "intent": _normalize_intent(intent),
        "context_refs": _coerce_context_refs(_parse_json_context(context), context_refs),
        "enabled_connectors": [str(item).strip() for item in (enabled_connectors or []) if str(item).strip()],
        "agent_trace": [],
    }
    result = graph.invoke(state)

    return {
        "answer": result.get("answer", ""),
        "snippets": result.get("snippets", []),
        "provider": config["provider"],
        "model": config["model"],
        "agent_trace": result.get("agent_trace", []),
    }
