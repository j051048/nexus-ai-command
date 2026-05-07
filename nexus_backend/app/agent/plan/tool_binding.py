"""[G] Tool binding decision logic."""

from app.agent.node_helpers import (
    _ALWAYS_INCLUDE_TOOLS,
    AgentConfig,
    QueryComplexity,
    _get_llm,
    _get_tool_schemas,
    logger,
)
from app.agent.plan.tracing import log_decision


def _lexical_prune_tool_schemas(
    schemas: list[dict],
    user_query: str,
    max_tools: int,
) -> list[dict]:
    """Deterministic fallback when embedding-based Tool RAG is unavailable."""
    if len(schemas) <= max_tools:
        return schemas

    terms = {t.lower() for t in user_query.replace("_", " ").split() if len(t) >= 2}
    always = [s for s in schemas if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS]
    rest = [s for s in schemas if s["function"]["name"] not in _ALWAYS_INCLUDE_TOOLS]

    def score(schema: dict) -> tuple[int, int]:
        fn = schema.get("function", {})
        haystack = f"{fn.get('name', '')} {fn.get('description', '')}".lower()
        exact_hits = sum(1 for term in terms if term in haystack)
        return (exact_hits, len(haystack))

    rest.sort(key=score, reverse=True)
    return (always + rest)[:max_tools]


async def bind_tools_to_llm(
    *,
    agent_config: AgentConfig,
    model: str | None,
    state: dict,
    complexity: QueryComplexity,
    intent_summary: str,
    iteration: int,
    resolved: dict | None,
    trace_id: str | None,
    user_query: str = "",
):
    """Create LLM instance and bind appropriate tools. Returns (llm, bind_kwargs)."""
    llm = _get_llm(agent_config, model=model, streaming=True, resolved_config=resolved)

    # Determine if any pending tools are irreversible (for tool_choice enforcement)
    _has_irreversible_context = False
    if iteration > 0 and state.get("completed_tool_calls"):
        _has_irreversible_context = any(
            getattr(tc, "status", None) == "blocked"
            for tc in state.get("completed_tool_calls", [])
        )

    bind_kwargs: dict = {}

    if complexity == QueryComplexity.SIMPLE:
        # SIMPLE queries: only bind lightweight universal tools
        simple_schemas = [
            s
            for s in _get_tool_schemas(
                agent_config.user_role, scene_code=state.get("scene_code")
            )
            if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS
        ]
        if simple_schemas:
            llm = llm.bind_tools(simple_schemas, parallel_tool_calls=True)
    else:
        bind_kwargs = {"parallel_tool_calls": True}
        # For re-planning after irreversible tool confirmation, force tool usage
        if _has_irreversible_context and agent_config.system_confirmed:
            bind_kwargs["tool_choice"] = "required"
        # Structured reflection constraint: when reflect detected "no tool call",
        # force the LLM to use a tool on the next iteration
        reflection_guidance = state.get("reflection_guidance", "")
        if (
            iteration > 0
            and reflection_guidance
            and any(
                kw in reflection_guidance
                for kw in ["未调用工具", "no tool call", "未使用工具", "无工具调用"]
            )
        ):
            bind_kwargs["tool_choice"] = "required"
        schemas = _get_tool_schemas(
            agent_config.user_role,
            intent_summary=intent_summary,
            scene_code=state.get("scene_code"),
            intent_domains=state.get("intent_domains"),
        )

        # ── Embedding-based secondary filtering ──
        # When schemas are still too many and we have a user query, use semantic
        # retrieval to keep only the most relevant tools.
        _embedding_pruned = False
        _pre_embed_count = len(schemas)
        from app.core.config import settings as _cfg

        if len(schemas) > _cfg.TOOL_EMBEDDING_GATE and user_query:
            try:
                from app.agent.tool_embedding_index import tool_embedding_index

                candidate_names = {s["function"]["name"] for s in schemas}
                ranked = await tool_embedding_index.retrieve(
                    query=user_query,
                    top_k=_cfg.TOOL_EMBEDDING_TOP_K,
                    min_score=_cfg.TOOL_EMBEDDING_MIN_SCORE,
                    candidate_names=candidate_names,
                )
                if ranked:
                    keep_names = _ALWAYS_INCLUDE_TOOLS | {name for name, _ in ranked}
                    schemas = [
                        s for s in schemas if s["function"]["name"] in keep_names
                    ]
                    _embedding_pruned = True
                    logger.info(
                        "[ToolBind] Embedding pruned %d → %d tools (query='%s')",
                        _pre_embed_count,
                        len(schemas),
                        user_query[:60],
                    )
            except Exception as e:
                logger.debug("[ToolBind] Embedding pruning skipped: %s", e)

        if len(schemas) > _cfg.TOOL_MAX_TOOLS:
            before_count = len(schemas)
            schemas = _lexical_prune_tool_schemas(
                schemas,
                user_query=user_query or intent_summary,
                max_tools=_cfg.TOOL_MAX_TOOLS,
            )
            logger.info(
                "[ToolBind] Deterministic pruned %d -> %d tools",
                before_count,
                len(schemas),
            )

        llm = llm.bind_tools(schemas, **bind_kwargs)

    # ── Explainability: log tool binding decision ──
    _tool_choice_mode = (
        bind_kwargs.get("tool_choice", "auto")
        if complexity != QueryComplexity.SIMPLE
        else "simple_only"
    )
    log_decision(
        trace_id,
        step_id=f"plan_tool_binding_iter{iteration}",
        decision=f"tool_choice={_tool_choice_mode}, complexity={complexity.value}",
        reasoning=(
            "SIMPLE查询仅绑定轻量工具"
            if complexity == QueryComplexity.SIMPLE
            else f"绑定完整工具集, tool_choice={'required(反思强制)' if bind_kwargs.get('tool_choice') == 'required' else 'auto'}"
        ),
        alternatives=["bind_no_tools", "bind_simple_only", "bind_all_tools"],
    )

    return llm, bind_kwargs
