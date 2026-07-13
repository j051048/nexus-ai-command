"""
Pre-graph state preparation for the Hybrid Memory Manager.

Builds the initial state for the agent graph by combining:
- Semantic cache lookup
- Query transformation (HyDE/Multi-Query)
- RAG retrieval
- Multi-layer memory injection (L1/L2, org, KG, episodic, etc.)
- History compaction and BaseMessage conversion
"""

import asyncio
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent.memory.compaction import (
    _strip_reasoning_from_history,
    micro_compact_messages,
)
from app.agent.memory.token_window import (
    HARD_TURN_LIMIT,
    SHORT_TERM_WINDOW,
    _summarize_messages,
    trim_messages_to_window,
)
from app.agent.query_transformer import QueryTransformer
from app.agent.query_transformer import llm_rerank as _llm_rerank
from app.agent.state import AgentConfig
from app.core.database import supabase

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


async def prepare_initial_state(
    raw_messages: list[dict[str, str]],
    system_prompt: str,
    config: AgentConfig,
    db_client: Any | None = None,
    *,
    skip_semantic: bool = False,
    state: dict | None = None,
) -> dict[str, Any]:
    """
    Build the initial state components for the agent graph.

    Steps:
    1. Semantic Cache Lookup
    2. Query Transformation (HyDE/Multi-Query)
    3. RAG Retrieval (if enabled)
    4. Summarization (if needed)
    5. BaseMessage conversion

    Returns:
        {
            "messages": List[BaseMessage],
            "cached_response": Optional[str],
            "rag_context": str,
            "rag_sources": List[str]
        }
    """
    client = db_client or supabase
    result = {
        "messages": [],
        "cached_response": None,
        "rag_context": "",
        "rag_sources": [],
    }

    # ── 0. Filter out system messages from frontend ──
    # The frontend sends the full conversation history including system messages
    # from previous turns. Since system_prompt and context injection are always
    # re-added below, keeping old system messages causes duplication and massive
    # token waste. Only keep user/assistant messages.
    raw_messages = [m for m in raw_messages if m.get("role") != "system"]

    # ── 1. Semantic Cache Lookup ──
    # P0 #3: Skipped — semantic cache is already checked in chat.py entry point.
    # If we reach here, cache was already missed or bypassed (system_confirmed).
    # The skip_semantic flag still controls downstream RAG/memory behavior.
    last_user_msg = ""
    for msg in reversed(raw_messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # ── 2. RAG Retrieval with Query Transformation ──
    # P1 Fix #22: Add HyDE and Multi-Query for better retrieval
    if config.enable_rag_inject and last_user_msg:
        try:
            from app.agent.node_helpers import QueryComplexity
            from app.services.vector_service import vector_service

            # Initialize query transformer
            transformer = QueryTransformer(config)

            # Determine transformation strategy — adaptive by complexity
            is_knowledge_agent = getattr(config, "agent_name", "") in (
                "knowledge",
                "knowledge_base",
            )
            use_hyde = getattr(config, "use_hyde", is_knowledge_agent)
            use_multi_query = getattr(config, "use_multi_query", is_knowledge_agent)

            # 按复杂度自动升级（config 显式设置优先）
            complexity = state.get("complexity") if state else None
            if not getattr(config, "_query_transform_override", False) and complexity:
                if complexity == QueryComplexity.CRITICAL:
                    use_hyde = True
                    use_multi_query = True
                elif complexity == QueryComplexity.COMPLEX:
                    use_multi_query = True
                # SIMPLE/MODERATE: 保持默认，跳过变换以降低延迟

            # ── 上下文感知 Query Rewriting（COMPLEX/CRITICAL + 含代词） ──
            _pronoun_hints = ("那个", "这个", "上次", "之前", "它", "他们", "她")
            _needs_rewrite = (
                (
                    complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
                    and (
                        len(last_user_msg) >= 10
                        or any(p in last_user_msg for p in _pronoun_hints)
                    )
                )
                if complexity
                else False
            )
            if _needs_rewrite:
                try:
                    rewritten = await transformer.rewrite_query(
                        last_user_msg, messages=raw_messages
                    )
                    if rewritten and rewritten != last_user_msg:
                        logger.info(
                            f"[Memory] Query rewritten: '{last_user_msg[:40]}' → '{rewritten[:40]}'"
                        )
                        last_user_msg = rewritten
                except Exception as e:
                    logger.error(f"[Memory] Query rewrite failed: {e}")

            all_docs = []

            # Strategy 1: HyDE (Hypothetical Document Embeddings)
            if use_hyde:
                hyde_doc = await transformer.generate_hyde(last_user_msg)
                if hyde_doc and hyde_doc != last_user_msg:
                    docs = await vector_service.search(
                        query=hyde_doc,
                        user_id=config.user_id,
                        limit=config.rag_inject_limit,
                        org_id=config.org_id,
                    )
                    # Parse docs from string result
                    if isinstance(docs, str) and "检索到" in docs:
                        all_docs.append({"content": docs, "source": "HyDE搜索"})

            # Strategy 2: Multi-Query Expansion (parallel searches)
            if use_multi_query:
                expanded_queries = await transformer.expand_multi_query(
                    last_user_msg, num_queries=3
                )
                if expanded_queries:
                    import asyncio as _asyncio

                    async def _search_expanded(q):
                        return await vector_service.search(
                            query=q,
                            user_id=config.user_id,
                            limit=config.rag_inject_limit // len(expanded_queries),
                            org_id=config.org_id,
                        )

                    expanded_results = await _asyncio.gather(
                        *[_search_expanded(q) for q in expanded_queries],
                        return_exceptions=True,
                    )
                    for i, docs in enumerate(expanded_results):
                        if isinstance(docs, str) and docs and "未找到" not in docs:
                            all_docs.append(
                                {
                                    "content": docs,
                                    "source": f"查询: {expanded_queries[i][:30]}",
                                }
                            )

            # Strategy 3: Original query (always included)
            original_docs = await vector_service.search(
                query=last_user_msg,
                user_id=config.user_id,
                limit=config.rag_inject_limit,
                org_id=config.org_id,
            )
            if (
                isinstance(original_docs, str)
                and original_docs
                and "未找到" not in original_docs
            ):
                all_docs.insert(0, {"content": original_docs, "source": "原始查询"})

            # Deduplicate and merge results
            if all_docs:
                seen_content = set()
                unique_docs = []
                for doc in all_docs:
                    content_hash = hash(doc.get("content", "")[:100])
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        unique_docs.append(doc)

                # LLM Reranking: MODERATE+ 查询用 mini_model 重排
                if (
                    complexity
                    in (
                        QueryComplexity.MODERATE,
                        QueryComplexity.COMPLEX,
                        QueryComplexity.CRITICAL,
                    )
                    and len(unique_docs) > 3
                ):
                    try:
                        rerank_top_k = (
                            3 if complexity == QueryComplexity.MODERATE else 5
                        )
                        unique_docs = await _llm_rerank(
                            last_user_msg, unique_docs, config, top_k=rerank_top_k
                        )
                        logger.info(
                            f"[Memory] LLM reranked {len(unique_docs)} docs (top_k={rerank_top_k})"
                        )
                    except Exception as e:
                        logger.debug(f"[Memory] LLM rerank skipped: {e}")

                # Limit per-snippet and total context length (OpenClaw-inspired)
                max_snippet_chars = 700  # Per-document snippet limit
                max_injected_chars = 4000  # Total injection budget
                context_parts = []
                current_length = 0
                for doc in unique_docs:
                    content = doc.get("content", "")
                    # Truncate individual snippets
                    if len(content) > max_snippet_chars:
                        content = content[:max_snippet_chars] + "…(已截断)"
                    if current_length + len(content) <= max_injected_chars:
                        context_parts.append(content)
                        current_length += len(content)
                    else:
                        break

                result["rag_context"] = "\n\n---\n\n".join(context_parts)
                result["rag_sources"] = list(
                    set(doc.get("source", "知识库") for doc in unique_docs)
                )
                logger.info(
                    f"[Memory] RAG injected {len(unique_docs)} docs (HyDE+MultiQuery) for user {config.user_id}"
                )

        except Exception as e:
            logger.warning(f"[Memory] RAG retrieval failed: {e}", exc_info=True)

    # ── 2b–2f. Collect all context blocks in parallel, then inject as ONE system message ──
    injected_contexts: list[str] = []
    from app.agent.memory.context_policy import choose_memory_context_policy

    memory_policy = choose_memory_context_policy(last_user_msg, None)
    user_profile_ctx = None  # initialized here so it's always defined

    # ── 2g-profile. User profile — ALWAYS fetched regardless of skip_semantic ──
    # Knowing who the user is is essential even for simple queries.

    if config.user_id:
        try:
            parts: list[str] = []
            user_res = (
                await client.table("users")
                .select("name, role, department")
                .eq("id", config.user_id)
                .maybe_single()
                .execute()
            )

            dept_name = None
            # P0 #4: department is already in the users query above — no need for a second query
            if user_res.data:
                dept_name = user_res.data.get("department")

            if user_res.data:
                name = user_res.data.get("name", "")
                role = user_res.data.get("role", "employee")
                dept_str = f"，{dept_name}" if dept_name else ""
                parts.append(f"当前用户: {name}（{role}{dept_str}）")

            if parts:
                user_profile_ctx = (
                    "[用户画像上下文]\n" + "\n".join(parts) + "\n[用户画像结束]"
                )
                logger.info(
                    f"[Memory] Collected user profile context for {config.user_id}"
                )
        except Exception as e:
            logger.error(f"[Memory] User profile context failed: {e}")

    # ── 2g-pref. 追加用户偏好画像（冻结快照） ──
    if config.user_id:
        try:
            from app.agent.preference_learner import preference_learner

            pref_snapshot = await preference_learner.build_profile_snapshot(
                user_id=config.user_id, org_id=config.org_id
            )
            if pref_snapshot:
                if user_profile_ctx:
                    # 插入到 [用户画像结束] 之前
                    user_profile_ctx = user_profile_ctx.replace(
                        "[用户画像结束]", pref_snapshot + "\n[用户画像结束]"
                    )
                else:
                    user_profile_ctx = pref_snapshot
        except Exception as e:
            logger.debug(f"[Memory] Preference snapshot skipped: {e}")

    # ── 2g-tasks. Agent Task Board injection (P1a) ──
    # Inject a compact task status summary so the agent always knows
    # where it is in a multi-step workflow, even after context compression.
    if config.user_id and config.session_id:
        try:
            task_res = (
                await client.table("agent_tasks")
                .select("id, title, status, depends_on")
                .eq("user_id", config.user_id)
                .eq("conversation_id", config.session_id)
                .neq("status", "done")
                .order("sort_order")
                .order("created_at")
                .limit(10)
                .execute()
            )

            active_tasks = task_res.data or []
            if active_tasks:
                status_icons = {"pending": "⬜", "in_progress": "🔄", "blocked": "🚫"}
                task_lines = []
                for t in active_tasks:
                    icon = status_icons.get(t["status"], "❓")
                    task_lines.append(f"{icon} [{t['id'][:8]}] {t['title']}")
                task_board = "\n".join(task_lines)
                injected_contexts.append(
                    f"[当前任务板 — {len(active_tasks)} 个待办]\n{task_board}\n[任务板结束]"
                )
                logger.info(
                    f"[Memory] Injected {len(active_tasks)} active tasks into context"
                )
        except Exception as e:
            logger.debug(f"[Memory] Task board injection skipped: {e}")

    if last_user_msg and not skip_semantic:
        # All 5 context lookups are independent — run them concurrently

        async def _fetch_l1_critical():
            """2b-L1. Critical facts & directives — always injected, never truncated."""
            if not config.user_id:
                return None
            try:
                from app.services.conversation_memory.retrieval import (
                    get_l1_critical_facts,
                )

                ctx = await get_l1_critical_facts(
                    user_id=config.user_id,
                    db=client,
                )
                if ctx:
                    logger.info(
                        f"[Memory] L1 critical facts collected for user {config.user_id}"
                    )
                return ctx
            except Exception as e:
                logger.debug(f"[Memory] L1 critical facts skipped: {e}")
                return None

        async def _fetch_l2_contextual():
            """2b-L2. Query-relevant contextual memories — budget-aware."""
            if not config.user_id:
                return None
            try:
                from app.services.conversation_memory.retrieval import get_l2_contextual

                ctx = await get_l2_contextual(
                    user_id=config.user_id,
                    query=last_user_msg,
                    complexity=str(state.get("complexity", "")) if state else None,
                    db=client,
                )
                if ctx:
                    logger.info(
                        f"[Memory] L2 contextual memories collected for user {config.user_id}"
                    )
                return ctx
            except Exception as e:
                logger.debug(f"[Memory] L2 contextual memories skipped: {e}")
                return None

        async def _fetch_org_memory():
            """2c. Organization Memory"""
            if not config.org_id:
                return None
            try:
                from app.services.conversation_memory_service import (
                    conversation_memory_service,
                )

                ctx = await conversation_memory_service.build_org_memory_context(
                    org_id=config.org_id,
                    query=last_user_msg,
                    db=client,
                )
                if ctx:
                    logger.info(
                        f"[Memory] Collected org memory context for org {config.org_id}"
                    )
                    return "[组织共享记忆上下文]\n" + ctx + "\n[组织记忆结束]"
                return None
            except Exception as e:
                logger.error(f"[Memory] Org memory context failed: {e}")
                return None

        async def _fetch_kg_context():
            """2d. Knowledge Graph Context — hybrid search (FTS + entity match)."""
            if not config.org_id:
                return None
            try:
                # Primary: use new hybrid search (FTS + ILIKE + RRF)
                from app.services.conversation_memory.graph_extraction import (
                    search_kg_hybrid,
                )

                triples = await search_kg_hybrid(
                    org_id=config.org_id,
                    query=last_user_msg,
                    limit=10,
                )
                parts: list[str] = []
                if triples:
                    for t in triples:
                        src = t.get("source_entity", "")
                        rel = t.get("relationship", "")
                        dst = t.get("destination_entity", "")
                        parts.append(f"{src} —{rel}→ {dst}")

                # Temporal supplement: detect time intent and query historical KG
                _TEMPORAL_RE = re.compile(
                    r"(之前|以前|过去|去年|前年|上个月|曾经|历史|原来|以往"
                    r"|previously|before|last year|used to|formerly)"
                )
                if _TEMPORAL_RE.search(last_user_msg):
                    try:
                        from app.services.conversation_memory.graph_extraction import (
                            query_entity_at_time,
                        )
                        from app.services.conversation_memory.temporal_normalizer import (
                            extract_time_range_from_query,
                        )

                        time_range = extract_time_range_from_query(last_user_msg)
                        target = (time_range or {}).get("start")
                        if target:
                            # Extract entity name: first 2-4 char Chinese name in query
                            entity_match = re.search(
                                r"([\u4e00-\u9fa5]{2,4})(?:之前|以前|过去|曾经|原来|去年)",
                                last_user_msg,
                            )
                            entity = entity_match.group(1) if entity_match else None
                            if entity:
                                temporal_triples = await query_entity_at_time(
                                    org_id=config.org_id,
                                    entity_name=entity,
                                    target_time=target,
                                )
                                for t in temporal_triples:
                                    src = t.get("source_entity", "")
                                    rel = t.get("relationship", "")
                                    dst = t.get("destination_entity", "")
                                    vf = (t.get("valid_from") or "")[:10]
                                    vt = (t.get("valid_to") or "至今")[:10]
                                    parts.append(f"{src} —{rel}→ {dst} [{vf} ~ {vt}]")
                    except Exception as e:
                        logger.debug(f"[Memory] Temporal KG query skipped: {e}")

                # Supplement: legacy entity_relations graph
                from app.services.knowledge_graph_service import query_entity_context

                legacy_ctx = await query_entity_context(
                    query=last_user_msg, org_id=config.org_id
                )
                if legacy_ctx:
                    parts.append(legacy_ctx)

                if parts:
                    ctx = "\n".join(parts)
                    logger.info(
                        f"[Memory] Collected knowledge graph context for org {config.org_id}"
                    )
                    return ctx
                return None
            except Exception as e:
                logger.error(f"[Memory] Knowledge graph context failed: {e}")
                return None

        async def _fetch_pattern_suggestions():
            """2e. Behavior Pattern Suggestions"""
            if not config.user_id or not config.org_id:
                return None
            try:
                from app.services.knowledge_graph_service import get_pattern_suggestions

                ctx = await get_pattern_suggestions(
                    user_id=config.user_id,
                    org_id=config.org_id,
                    current_query=last_user_msg,
                )
                if ctx:
                    logger.info(
                        f"[Memory] Collected pattern suggestions for user {config.user_id}"
                    )
                return ctx
            except Exception as e:
                logger.error(f"[Memory] Pattern suggestion failed: {e}")
                return None

        async def _fetch_episodic_memory():
            """2f. Episodic Memory Recall"""
            if not config.user_id:
                return None
            try:
                from app.services.conversation_memory_service import (
                    episodic_memory_service,
                )

                episodes = await episodic_memory_service.search_similar_episodes(
                    user_id=config.user_id,
                    query=last_user_msg,
                    limit=3,
                    org_id=config.org_id,
                    db=client,
                )
                if episodes:
                    ctx = episodic_memory_service.build_episode_context(episodes)
                    if ctx:
                        logger.info(
                            f"[Memory] Collected {len(episodes)} episode recalls for user {config.user_id}"
                        )
                    return ctx
                return None
            except Exception as e:
                logger.error(f"[Memory] Episode recall failed: {e}")
                return None

        async def _fetch_reasoning_trace():
            """2g. Reasoning Trace Recall (JP Morgan AskDavid inspired)"""
            if not config.user_id:
                return None
            try:
                from app.agent.reasoning_trace import reasoning_trace_store

                complexity_str = str(state.get("complexity", "")) if state else None
                trace = await reasoning_trace_store.match_trace(
                    query=last_user_msg,
                    user_id=config.user_id,
                    org_id=config.org_id,
                    complexity=complexity_str,
                    db=client,
                )
                if trace:
                    hint = reasoning_trace_store.trace_to_planning_hint(trace)
                    if hint:
                        logger.info(
                            f"[Memory] Matched reasoning trace for user {config.user_id} "
                            f"(confidence={trace.get('confidence', 0):.2f})"
                        )
                    return hint
                return None
            except Exception as e:
                logger.debug(f"[Memory] Reasoning trace recall skipped: {e}")
                return None

        memory_policy = choose_memory_context_policy(
            last_user_msg,
            str(state.get("complexity", "")) if state else None,
        )

        async def _skip_memory_source():
            return None

        if "org" not in memory_policy.sources:
            _fetch_org_memory = _skip_memory_source
        if "kg" not in memory_policy.sources:
            _fetch_kg_context = _skip_memory_source
        if "patterns" not in memory_policy.sources:
            _fetch_pattern_suggestions = _skip_memory_source
        if "episodic" not in memory_policy.sources:
            _fetch_episodic_memory = _skip_memory_source
        if "reasoning" not in memory_policy.sources:
            _fetch_reasoning_trace = _skip_memory_source

        # Fire selected lookups concurrently (profile already fetched above)
        # L1/L2 replace the old monolithic _fetch_long_term_memory()
        results = await asyncio.gather(
            _fetch_l1_critical(),  # [0] L1: directives — highest priority
            _fetch_l2_contextual(),  # [1] L2: query-relevant memories
            _fetch_org_memory(),  # [2] org memory
            _fetch_kg_context(),  # [3] knowledge graph
            _fetch_pattern_suggestions(),  # [4] behavior patterns
            _fetch_episodic_memory(),  # [5] episodic recall
            _fetch_reasoning_trace(),  # [6] reasoning trace (AskDavid-inspired)
            return_exceptions=True,
        )

        # Collect context results — insertion order = budget priority (FIFO)
        # L1 (index 0) goes first, then L2 (index 1), then the rest
        for r in results:
            if isinstance(r, str) and r:
                injected_contexts.append(r)
            elif isinstance(r, Exception):
                logger.error(f"[Memory] Parallel context fetch error: {r}")

    # Embed user profile directly into system_prompt (highest priority)
    if user_profile_ctx:
        system_prompt = system_prompt + "\n\n" + user_profile_ctx
        logger.info("[Memory] User profile embedded into system prompt")

    # Inject remaining contexts as a single system message (with token budget)
    if injected_contexts:
        # Add save_memory tool guidance at the end of context blocks
        injected_contexts.append(
            '[记忆工具提示] 当用户明确要求"记住"某事, 或你发现重要的用户偏好/事实时, '
            "立即调用 save_memory 工具保存, 不要等到对话结束。"
        )

        # Cross-source conflict resolution instructions
        injected_contexts.append(
            "<source-priority>\n"
            "当不同来源的记忆出现矛盾时，按以下优先级判断最新真实情况：\n"
            "1. 标记了具体日期且日期更近的个人记忆 > 日期更旧的记忆\n"
            "2. 组织行为准则(policy) > 个人偏好（政策必须遵守）\n"
            '3. 有 status="expired" 标记的记忆已过期，仅作历史参考\n'
            "4. confidence 值更高的记忆 > confidence 更低的\n"
            '5. fact_type="fact" > fact_type="opinion"（事实优先于观点）\n'
            "6. 如仍无法判断，明确告知用户存在信息矛盾并询问确认\n"
            "</source-priority>"
        )

        # Unified token budget: cap injected context to avoid unbounded growth
        # Mirrors ContextEngine._MAX_BUDGET to keep total context predictable.
        from app.services.token_service import token_counter

        _INJECT_BUDGET = 6000  # tokens — aligned with ContextEngine budget range
        _INJECT_BUDGET = memory_policy.token_budget
        budgeted: list[str] = []
        running_tokens = 0
        for block in injected_contexts:
            block_tokens = token_counter.count_tokens(block)
            if running_tokens + block_tokens > _INJECT_BUDGET and budgeted:
                logger.info(
                    f"[Memory] Context budget reached ({running_tokens}/{_INJECT_BUDGET}), "
                    f"dropping {len(injected_contexts) - len(budgeted)} remaining blocks"
                )
                break
            budgeted.append(block)
            running_tokens += block_tokens

        raw_messages.insert(
            0,
            {
                "role": "system",
                "content": "\n\n".join(budgeted),
            },
        )
        logger.info(
            f"[Memory] Injected {len(budgeted)} context blocks (~{running_tokens} tokens)"
        )

    # ── 2g. Pre-compaction Memory Flush ──
    # Before discarding old messages, extract any memorizable content
    # so important information isn't lost during compression.
    if config.user_id and len(raw_messages) > SHORT_TERM_WINDOW:
        try:
            from app.services.conversation_memory_service import (
                conversation_memory_service,
            )

            older_msgs = raw_messages[:-SHORT_TERM_WINDOW]
            user_msgs_to_flush = [
                m for m in older_msgs if m.get("role") == "user" and m.get("content")
            ]
            if user_msgs_to_flush:
                extracted = await conversation_memory_service.extract_preferences(
                    user_id=config.user_id,
                    messages=user_msgs_to_flush,
                    org_id=config.org_id,
                )
                if extracted:
                    logger.info(
                        f"[Memory] Pre-compaction flush: extracted {len(extracted)} "
                        f"memories from {len(user_msgs_to_flush)} messages about to be discarded"
                    )
        except Exception as e:
            logger.debug(f"[Memory] Pre-compaction memory flush skipped: {e}")

    # ── 2h. Micro-Compaction (P0) ──
    # Proactively shrink old tool outputs and long assistant messages
    # BEFORE the expensive LLM-based summarization or token-window trim.
    # This is the first line of defence against context bloat.
    raw_messages = micro_compact_messages(raw_messages)

    # ── 3. History Hard-Limiting (safety net) ──
    # Absolute turn limit before any LLM-based compaction to prevent
    # runaway token costs on very long sessions.
    if len(raw_messages) > HARD_TURN_LIMIT:
        system_msgs = [m for m in raw_messages if m.get("role") == "system"]
        non_system = [m for m in raw_messages if m.get("role") != "system"]
        raw_messages = system_msgs + non_system[-HARD_TURN_LIMIT:]
        logger.info(
            f"[Memory] Hard-limited to {HARD_TURN_LIMIT} non-system messages "
            f"+ {len(system_msgs)} system messages"
        )

    # ── 3b. Sliding Window with Summary ──
    if len(raw_messages) > SHORT_TERM_WINDOW:
        older = raw_messages[:-SHORT_TERM_WINDOW]
        recent = raw_messages[-SHORT_TERM_WINDOW:]

        summary = await _summarize_messages(older, config)
        if summary:
            recent.insert(
                0,
                {
                    "role": "system",
                    "content": f"[对话历史摘要] {summary}",
                },
            )
        raw_messages = recent

    # ── 3c. Token Window Trim ──
    # After the count-based sliding window, apply a token-budget check so
    # that the final message list never exceeds 80 % of the model context.
    raw_messages = await trim_messages_to_window(raw_messages, config)

    # ── 4. Convert to LangChain messages ──
    lc_messages: list[BaseMessage] = []
    lc_messages.append(SystemMessage(content=system_prompt))

    for msg in raw_messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            # Strip reasoning artifacts (<think> tags) from historical messages
            # to avoid wasting tokens and leaking chain-of-thought in context
            content = _strip_reasoning_from_history(content)
            lc_messages.append(AIMessage(content=content))

    # ── 4b. Repair orphaned tool message pairs ──
    # After conversion, ensure no AIMessage with tool_calls is separated
    # from its ToolMessages (can happen if checkpointer state leaks into history).
    lc_messages = _repair_lc_message_pairs(lc_messages)

    # ── 5. HITL Confirmation Injection ──
    # When the user confirmed a blocked tool via the frontend confirmation card,
    # the LLM needs to know it should re-call the same tool. Without this hint,
    # it sees the previous "blocked" tool result in history and refuses to retry.
    #
    # P2-1: Also record the confirmed tool usage as memory so the LLM can
    # reference user-approved parameter patterns in future conversations.
    if config.system_confirmed and config.confirmed_tool:
        _ct_name = config.confirmed_tool.get("tool_name", "")
        _ct_args = config.confirmed_tool.get("args", {})
        if _ct_name and _ct_args:
            try:
                import json as _json

                from app.services.conversation_memory import conversation_memory_service
                from app.services.conversation_memory.admission import (
                    sanitize_tool_arguments,
                )

                _ct_args = sanitize_tool_arguments(_ct_args)

                _t = asyncio.create_task(
                    conversation_memory_service.save_memory(
                        user_id=config.user_id,
                        key=f"tool_confirmed_usage_{_ct_name}",
                        value=f"用户确认调用 {_ct_name} 的正确参数: {_json.dumps(_ct_args, ensure_ascii=False)[:300]}",
                        category="tool_correction",
                        importance=0.8,
                        org_id=config.org_id,
                        source="user_explicit",
                        extraction_method="user_explicit",
                    )
                )
                _background_tasks.add(_t)
                _t.add_done_callback(_background_tasks.discard)
            except Exception:
                logger.error("Failed to record HITL correction memory", exc_info=True)

    if config.system_confirmed:
        confirmed = config.confirmed_tool or {}
        tool_name = confirmed.get("tool_name", "")
        tool_args = confirmed.get("args", {})
        if tool_name and tool_args:
            import json as _json

            args_str = _json.dumps(tool_args, ensure_ascii=False)
            lc_messages.append(
                SystemMessage(
                    content=(
                        f"[系统指令] 用户已在界面上点击「确认执行」按钮。"
                        f"请立即调用工具 {tool_name}，参数为: {args_str}，"
                        f"并追加 confirm=true。这次调用将被系统放行，无需再次确认。"
                        f"不要生成文字回复，直接调用工具。"
                    )
                )
            )
        else:
            lc_messages.append(
                SystemMessage(
                    content=(
                        "[系统指令] 用户已在界面上点击「确认执行」按钮。"
                        "请立即重新调用之前被阻止的工具（即上次返回「操作需要确认」的那个工具），"
                        "使用与之前完全相同的参数。这次调用将被系统放行，无需再次确认。"
                        "不要生成文字回复来询问用户是否确认，直接调用工具。"
                    )
                )
            )

    result["messages"] = lc_messages
    return result


# ─── Internal Helpers ────────────────────────────────────────────────────────


def _repair_lc_message_pairs(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    Repair orphaned tool message pairs in LangChain message lists.

    After history truncation or checkpointer state loading, AIMessage with
    tool_calls can be separated from their corresponding ToolMessages (or
    vice versa). Sending such orphaned messages to the LLM API causes errors.

    Rules:
    - ToolMessage without a preceding AIMessage with tool_calls → drop
    - AIMessage with tool_calls without subsequent ToolMessage(s) → drop
    """
    from langchain_core.messages import ToolMessage

    if not messages:
        return messages

    repaired: list[BaseMessage] = []
    i = 0
    while i < len(messages):
        msg = messages[i]

        if isinstance(msg, ToolMessage):
            # ToolMessage must follow an AIMessage with tool_calls
            if (
                repaired
                and isinstance(repaired[-1], AIMessage)
                and getattr(repaired[-1], "tool_calls", None)
            ):
                repaired.append(msg)
            else:
                logger.debug(
                    "[Memory] Dropping orphaned ToolMessage (no preceding tool_calls AIMessage)"
                )
            i += 1
            continue

        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            # Look ahead for at least one subsequent ToolMessage
            j = i + 1
            has_tool_response = False
            while j < len(messages):
                if isinstance(messages[j], ToolMessage):
                    has_tool_response = True
                    break
                if not isinstance(messages[j], ToolMessage):
                    break
                j += 1

            if not has_tool_response:
                logger.debug(
                    "[Memory] Dropping AIMessage with orphaned tool_calls (no subsequent ToolMessages)"
                )
                i += 1
                continue

        repaired.append(msg)
        i += 1

    dropped = len(messages) - len(repaired)
    if dropped:
        logger.info(
            f"[Memory] Repaired message list: {len(messages)} → {len(repaired)} ({dropped} orphans removed)"
        )

    return repaired
