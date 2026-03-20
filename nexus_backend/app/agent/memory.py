"""
Hybrid Memory Manager for the LangGraph Agent.

Combines:
1. Short-term: Sliding window of recent messages (configurable size)
2. Long-term: Summary of older messages via LLM compression
3. Semantic: Vector search for relevant past context
4. Semantic Cache: Fast-path for repeated / similar queries
5. Query Transformation: HyDE and Multi-Query for better retrieval

This module is called BEFORE the graph runs to prepare the initial
message list, and AFTER the graph runs to persist results.
"""

import asyncio
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent.state import AgentConfig
from app.agent.query_transformer import QueryTransformer, llm_rerank as _llm_rerank
from app.core.config import settings
from app.core.database import supabase
from app.services.chat_service import ChatService
from app.services.token_service import token_counter

logger = logging.getLogger(__name__)

# Configurable window size
SHORT_TERM_WINDOW = getattr(settings, "MAX_CHAT_HISTORY", 10)

# Absolute turn limit — safety net before any LLM-based compaction.
# Prevents runaway token costs on very long sessions.
HARD_TURN_LIMIT = 40

# Quick token estimation: chars/4 + 20% safety margin (OpenClaw-inspired)
# Used as fast pre-check before expensive precise token counting
_TOKEN_ESTIMATE_RATIO = 4
_TOKEN_SAFETY_MARGIN = 1.2

# ─── Micro-Compaction (P0) ────────────────────────────────────────────────
# Inspired by Claude Code S06: proactively shrink old tool outputs and long
# code blocks BEFORE the expensive token-window trim kicks in.  This is the
# first line of defence against context bloat.

# Messages within the most recent N turns are never micro-compacted.
MICRO_COMPACT_PRESERVE_RECENT = 3  # keep last 3 user-assistant pairs intact

# Per-message content thresholds (characters)
_TOOL_RESULT_TRUNCATE_THRESHOLD = 2000   # single tool_result max chars
_CODE_BLOCK_TRUNCATE_THRESHOLD = 1500    # code block max chars
_ASSISTANT_MSG_TRUNCATE_THRESHOLD = 3000 # assistant message max chars

# Regex patterns for micro-compaction
_CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

# Regex to strip <think>...</think> blocks from historical assistant messages
_THINK_BLOCK_RE = re.compile(r"<think>[\s\S]*?</think>", re.DOTALL)


def _count_recent_turn_boundary(messages: list[dict[str, str]]) -> int:
    """Find the index where the 'recent N turns' begin (counting from end).

    A turn = one user message + its following assistant reply.
    Returns the index into *messages* such that messages[index:] contains
    the last MICRO_COMPACT_PRESERVE_RECENT turns.
    """
    turns_found = 0
    i = len(messages) - 1
    while i >= 0 and turns_found < MICRO_COMPACT_PRESERVE_RECENT:
        if messages[i].get("role") == "user":
            turns_found += 1
        i -= 1
    # i+1 is the start of the protected recent window
    return max(i + 1, 0)


def _compact_tool_result(content: str) -> str:
    """Shrink a tool result to a short summary placeholder."""
    if not content:
        return content
    # Extract tool name hint from common patterns like "[工具: xxx]" or "调用了 xxx"
    lines = content.split("\n", 3)
    first_line = lines[0][:120] if lines else content[:120]
    char_count = len(content)
    line_count = content.count("\n") + 1
    return f"[已执行工具, 返回 {line_count} 行 / {char_count} 字符] {first_line}..."


def _compact_code_blocks(content: str) -> str:
    """Replace large code blocks with compact placeholders."""
    def _replacer(match):
        lang = match.group(1) or "code"
        code = match.group(2)
        if len(code) <= _CODE_BLOCK_TRUNCATE_THRESHOLD:
            return match.group(0)  # keep small blocks
        line_count = code.count("\n") + 1
        # Keep first 3 and last 2 lines
        code_lines = code.split("\n")
        preview = "\n".join(code_lines[:3])
        tail = "\n".join(code_lines[-2:])
        return f"```{lang}\n{preview}\n... ({line_count} 行, 已省略中间部分) ...\n{tail}\n```"
    return _CODE_BLOCK_RE.sub(_replacer, content)


def _compact_long_assistant_msg(content: str) -> str:
    """Truncate overly long assistant messages, keeping head + tail."""
    if len(content) <= _ASSISTANT_MSG_TRUNCATE_THRESHOLD:
        return content
    # Compact code blocks first
    content = _compact_code_blocks(content)
    if len(content) <= _ASSISTANT_MSG_TRUNCATE_THRESHOLD:
        return content
    # Still too long — hard truncate with head + tail
    head_size = _ASSISTANT_MSG_TRUNCATE_THRESHOLD * 2 // 3
    tail_size = _ASSISTANT_MSG_TRUNCATE_THRESHOLD // 3
    return (
        content[:head_size]
        + f"\n\n... (原文 {len(content)} 字符, 已省略中间部分) ...\n\n"
        + content[-tail_size:]
    )


def micro_compact_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Apply micro-compaction to older messages in the conversation.

    Rules:
    1. Messages in the most recent N turns are NEVER touched.
    2. Older assistant messages: truncate long content, compact code blocks.
    3. Older tool-result-like system messages: replace with short summaries.
    4. Single tool_result exceeding threshold: truncate even in recent window.

    This runs BEFORE trim_messages_to_window as a lightweight first pass.
    """
    if len(messages) <= MICRO_COMPACT_PRESERVE_RECENT * 2:
        return messages  # too few messages to bother

    boundary = _count_recent_turn_boundary(messages)
    result = []

    for i, msg in enumerate(messages):
        role = msg.get("role", "")
        content = msg.get("content", "")

        if i >= boundary:
            # Recent window — only apply per-message size guard
            if role == "assistant" and len(content) > _TOOL_RESULT_TRUNCATE_THRESHOLD * 2:
                # Even recent messages get code-block compaction if huge
                new_content = _compact_code_blocks(content)
                result.append({**msg, "content": new_content})
            else:
                result.append(msg)
            continue

        # --- Older messages: aggressive compaction ---
        if role == "system":
            # Tool result injections often appear as system messages
            # with patterns like "[工具结果]" or very long structured data
            if len(content) > _TOOL_RESULT_TRUNCATE_THRESHOLD:
                result.append({**msg, "content": _compact_tool_result(content)})
            else:
                result.append(msg)
        elif role == "assistant":
            new_content = _compact_long_assistant_msg(content)
            result.append({**msg, "content": new_content})
        else:
            # User messages — keep as-is (they're usually short)
            result.append(msg)

    # Log compaction stats
    original_chars = sum(len(m.get("content", "")) for m in messages)
    compacted_chars = sum(len(m.get("content", "")) for m in result)
    if compacted_chars < original_chars:
        saved = original_chars - compacted_chars
        logger.info(
            f"[MicroCompact] Compacted {len(messages)} messages: "
            f"{original_chars} → {compacted_chars} chars (saved {saved}, "
            f"{saved * 100 // original_chars}%)"
        )

    return result


def _strip_reasoning_from_history(content: str) -> str:
    """Remove reasoning/thinking artifacts from historical assistant messages.

    Handles:
    - <think>...</think> blocks (DeepSeek-R1, QwQ)
    - Orphan <think> or </think> tags (partial streaming artifacts)
    """
    if not content:
        return content
    if "<think>" not in content and "</think>" not in content:
        return content
    cleaned = _THINK_BLOCK_RE.sub("", content)
    cleaned = cleaned.replace("<think>", "").replace("</think>", "")
    return cleaned.lstrip("\n")

# Default context window sizes per model family (in tokens)
_MODEL_CONTEXT_WINDOWS = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-3.5-turbo": 16385,
}
_DEFAULT_CONTEXT_WINDOW = 128000


async def trim_messages_to_window(
    messages: list[dict[str, str]],
    config: AgentConfig,
    threshold_ratio: float = 0.80,
) -> list[dict[str, str]]:
    """
    Token window management: when the total token count of *messages* exceeds
    ``threshold_ratio`` (default 80 %) of the model's context window, the
    earliest non-system messages are summarised into a single compact summary
    message, keeping the conversation within budget.

    Steps:
      1. Count total tokens via ``token_counter``.
      2. If under threshold → return messages unchanged.
      3. Otherwise, split into *older* and *recent* halves, summarise the
         older portion with ``_summarize_messages``, and prepend the summary
         as a system message.

    Returns:
        A (potentially shortened) message list that fits within the window.
    """
    model = config.model or "gpt-4o"
    context_window = _MODEL_CONTEXT_WINDOWS.get(model, _DEFAULT_CONTEXT_WINDOW)
    token_limit = int(context_window * threshold_ratio)

    # Fast pre-check: estimate tokens via chars/4 + safety margin
    # Avoids expensive precise counting when clearly under budget
    total_chars = sum(len(m.get("content", "")) for m in messages)
    estimated_tokens = int(total_chars / _TOKEN_ESTIMATE_RATIO * _TOKEN_SAFETY_MARGIN)
    if estimated_tokens <= token_limit:
        return messages

    total_tokens = token_counter.count_messages_tokens(messages, model)
    if total_tokens <= token_limit:
        return messages

    logger.info(
        f"[Memory] Token window exceeded: {total_tokens}/{token_limit} "
        f"({total_tokens / context_window:.0%} of {context_window}). "
        f"Compressing early messages."
    )

    # Separate system messages (index 0 is usually the main system prompt)
    # and keep at least the last SHORT_TERM_WINDOW messages intact.
    keep_count = max(SHORT_TERM_WINDOW, 2)
    if len(messages) <= keep_count:
        return messages  # Nothing to trim

    older = messages[:-keep_count]
    recent = messages[-keep_count:]

    # Only summarise non-system older messages
    non_system_older = [m for m in older if m.get("role") != "system"]
    system_older = [m for m in older if m.get("role") == "system"]

    summary = await _summarize_messages(non_system_older, config)
    trimmed: list[dict[str, str]] = []

    # Preserve original system messages
    trimmed.extend(system_older)

    if summary:
        trimmed.append(
            {
                "role": "system",
                "content": f"[对话历史摘要 — 早期 {len(non_system_older)} 条消息已压缩] {summary}",
            }
        )

    trimmed.extend(recent)

    new_tokens = token_counter.count_messages_tokens(trimmed, model)
    logger.info(
        f"[Memory] Trimmed from {total_tokens} to {new_tokens} tokens ({len(messages)} → {len(trimmed)} messages)"
    )
    return trimmed


# ─── Query Transformer & LLM Rerank (extracted to query_transformer.py) ───────
# QueryTransformer and _llm_rerank are now imported at module top.


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
    result = {"messages": [], "cached_response": None, "rag_context": "", "rag_sources": []}

    # ── 0. Filter out system messages from frontend ──
    # The frontend sends the full conversation history including system messages
    # from previous turns. Since system_prompt and context injection are always
    # re-added below, keeping old system messages causes duplication and massive
    # token waste. Only keep user/assistant messages.
    raw_messages = [m for m in raw_messages if m.get("role") != "system"]

    # ── 1. Semantic Cache Lookup ──
    last_user_msg = ""
    for msg in reversed(raw_messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    if last_user_msg and config.user_id and not config.system_confirmed and not skip_semantic:
        try:
            from app.services.semantic_cache import semantic_cache_service

            cached = await semantic_cache_service.get_cache(last_user_msg, config.user_id)
            if cached:
                logger.info(f"[Memory] Semantic cache hit for user {config.user_id}")
                result["cached_response"] = cached
                return result
        except Exception as e:
            logger.debug(f"[Memory] Semantic cache lookup failed: {e}")

    # ── 2. RAG Retrieval with Query Transformation ──
    # P1 Fix #22: Add HyDE and Multi-Query for better retrieval
    if config.enable_rag_inject and last_user_msg:
        try:
            from app.services.vector_service import vector_service

            # Initialize query transformer
            transformer = QueryTransformer(config)

            # Determine transformation strategy — adaptive by complexity
            is_knowledge_agent = getattr(config, "agent_name", "") in ("knowledge", "knowledge_base")
            use_hyde = getattr(config, "use_hyde", is_knowledge_agent)
            use_multi_query = getattr(config, "use_multi_query", is_knowledge_agent)

            # 按复杂度自动升级（config 显式设置优先）
            complexity = state.get("complexity") if state else None
            if not getattr(config, "_query_transform_override", False) and complexity:
                from app.agent.node_helpers import QueryComplexity
                if complexity == QueryComplexity.CRITICAL:
                    use_hyde = True
                    use_multi_query = True
                elif complexity == QueryComplexity.COMPLEX:
                    use_multi_query = True
                # SIMPLE/MODERATE: 保持默认，跳过变换以降低延迟

            # ── 上下文感知 Query Rewriting（COMPLEX/CRITICAL + 含代词） ──
            _pronoun_hints = ("那个", "这个", "上次", "之前", "它", "他们", "她")
            _needs_rewrite = (
                complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
                and (len(last_user_msg) >= 10 or any(p in last_user_msg for p in _pronoun_hints))
            ) if complexity else False
            if _needs_rewrite:
                try:
                    rewritten = await transformer.rewrite_query(last_user_msg, messages=raw_messages)
                    if rewritten and rewritten != last_user_msg:
                        logger.info(f"[Memory] Query rewritten: '{last_user_msg[:40]}' → '{rewritten[:40]}'")
                        last_user_msg = rewritten
                except Exception as e:
                    logger.debug(f"[Memory] Query rewrite failed: {e}")

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
                expanded_queries = await transformer.expand_multi_query(last_user_msg, num_queries=3)
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
                            all_docs.append({"content": docs, "source": f"查询: {expanded_queries[i][:30]}"})

            # Strategy 3: Original query (always included)
            original_docs = await vector_service.search(
                query=last_user_msg,
                user_id=config.user_id,
                limit=config.rag_inject_limit,
                org_id=config.org_id,
            )
            if isinstance(original_docs, str) and original_docs and "未找到" not in original_docs:
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

                # LLM Reranking: COMPLEX/CRITICAL 查询用 mini_model 重排
                if complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL) and len(unique_docs) > 3:
                    try:
                        unique_docs = await _llm_rerank(last_user_msg, unique_docs, config, top_k=5)
                        logger.info(f"[Memory] LLM reranked {len(unique_docs)} docs")
                    except Exception as e:
                        logger.debug(f"[Memory] LLM rerank skipped: {e}")

                # Limit per-snippet and total context length (OpenClaw-inspired)
                max_snippet_chars = 700   # Per-document snippet limit
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
                result["rag_sources"] = list(set(doc.get("source", "知识库") for doc in unique_docs))
                logger.info(
                    f"[Memory] RAG injected {len(unique_docs)} docs (HyDE+MultiQuery) for user {config.user_id}"
                )

        except Exception as e:
            logger.warning(f"[Memory] RAG retrieval failed: {e}", exc_info=True)

    # ── 2b–2f. Collect all context blocks in parallel, then inject as ONE system message ──
    injected_contexts: list[str] = []
    user_profile_ctx = None  # initialized here so it's always defined

    # ── 2g-profile. User profile — ALWAYS fetched regardless of skip_semantic ──
    # Knowing who the user is is essential even for simple queries.
    import asyncio

    if config.user_id:
        try:
            parts: list[str] = []
            user_res = await client.table("users").select(
                "name, role, department"
            ).eq("id", config.user_id).maybe_single().execute()

            dept_name = None
            if config.org_id:
                try:
                    emp_res = await client.table("employees").select(
                        "departments(name)"
                    ).eq("user_id", config.user_id).eq(
                        "organization_id", config.org_id
                    ).maybe_single().execute()
                    if emp_res.data:
                        dept_info = emp_res.data.get("departments")
                        if isinstance(dept_info, dict):
                            dept_name = dept_info.get("name")
                except Exception:
                    pass

            if user_res.data:
                name = user_res.data.get("name", "")
                role = user_res.data.get("role", "employee")
                # Fallback to department column on users table if employees lookup didn't find one
                if not dept_name:
                    dept_name = user_res.data.get("department")
                dept_str = f"，{dept_name}" if dept_name else ""
                parts.append(f"当前用户: {name}（{role}{dept_str}）")

            if parts:
                user_profile_ctx = "[用户画像上下文]\n" + "\n".join(parts) + "\n[用户画像结束]"
                logger.info(f"[Memory] Collected user profile context for {config.user_id}")
        except Exception as e:
            logger.debug(f"[Memory] User profile context failed: {e}")

    # ── 2g-tasks. Agent Task Board injection (P1a) ──
    # Inject a compact task status summary so the agent always knows
    # where it is in a multi-step workflow, even after context compression.
    if config.user_id and config.session_id:
        try:
            task_res = await client.table("agent_tasks").select(
                "id, title, status, depends_on"
            ).eq("user_id", config.user_id).eq(
                "conversation_id", config.session_id
            ).neq("status", "done").order("sort_order").order("created_at").limit(10).execute()

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
                logger.info(f"[Memory] Injected {len(active_tasks)} active tasks into context")
        except Exception as e:
            logger.debug(f"[Memory] Task board injection skipped: {e}")

    if last_user_msg and not skip_semantic:
        # All 5 context lookups are independent — run them concurrently

        async def _fetch_long_term_memory():
            """2b. Long-term Memory"""
            if not config.user_id:
                return None
            try:
                from app.services.conversation_memory_service import conversation_memory_service
                ctx = await conversation_memory_service.build_memory_context(
                    user_id=config.user_id, current_query=last_user_msg, db=client,
                )
                if ctx:
                    logger.info(f"[Memory] Collected long-term memory context for user {config.user_id}")
                return ctx
            except Exception as e:
                logger.debug(f"[Memory] Long-term memory injection skipped: {e}")
                return None

        async def _fetch_org_memory():
            """2c. Organization Memory"""
            if not config.org_id:
                return None
            try:
                from app.services.conversation_memory_service import conversation_memory_service
                ctx = await conversation_memory_service.build_org_memory_context(
                    org_id=config.org_id, query=last_user_msg, db=client,
                )
                if ctx:
                    logger.info(f"[Memory] Collected org memory context for org {config.org_id}")
                    return "[组织共享记忆上下文]\n" + ctx + "\n[组织记忆结束]"
                return None
            except Exception as e:
                logger.debug(f"[Memory] Org memory context failed: {e}")
                return None

        async def _fetch_kg_context():
            """2d. Knowledge Graph Context — hybrid search (FTS + entity match)."""
            if not config.org_id:
                return None
            try:
                # Primary: use new hybrid search (FTS + ILIKE + RRF)
                from app.services.conversation_memory.graph_extraction import search_kg_hybrid
                triples = await search_kg_hybrid(
                    org_id=config.org_id, query=last_user_msg, limit=10,
                )
                parts: list[str] = []
                if triples:
                    for t in triples:
                        src = t.get("source_entity", "")
                        rel = t.get("relationship", "")
                        dst = t.get("destination_entity", "")
                        parts.append(f"{src} —{rel}→ {dst}")

                # Supplement: legacy entity_relations graph
                from app.services.knowledge_graph_service import query_entity_context
                legacy_ctx = await query_entity_context(query=last_user_msg, org_id=config.org_id)
                if legacy_ctx:
                    parts.append(legacy_ctx)

                if parts:
                    ctx = "\n".join(parts)
                    logger.info(f"[Memory] Collected knowledge graph context for org {config.org_id}")
                    return ctx
                return None
            except Exception as e:
                logger.debug(f"[Memory] Knowledge graph context failed: {e}")
                return None

        async def _fetch_pattern_suggestions():
            """2e. Behavior Pattern Suggestions"""
            if not config.user_id or not config.org_id:
                return None
            try:
                from app.services.knowledge_graph_service import get_pattern_suggestions
                ctx = await get_pattern_suggestions(
                    user_id=config.user_id, org_id=config.org_id, current_query=last_user_msg,
                )
                if ctx:
                    logger.info(f"[Memory] Collected pattern suggestions for user {config.user_id}")
                return ctx
            except Exception as e:
                logger.debug(f"[Memory] Pattern suggestion failed: {e}")
                return None

        async def _fetch_episodic_memory():
            """2f. Episodic Memory Recall"""
            if not config.user_id:
                return None
            try:
                from app.services.conversation_memory_service import episodic_memory_service
                episodes = await episodic_memory_service.search_similar_episodes(
                    user_id=config.user_id, query=last_user_msg, limit=3,
                    org_id=config.org_id, db=client,
                )
                if episodes:
                    ctx = episodic_memory_service.build_episode_context(episodes)
                    if ctx:
                        logger.info(f"[Memory] Collected {len(episodes)} episode recalls for user {config.user_id}")
                    return ctx
                return None
            except Exception as e:
                logger.debug(f"[Memory] Episode recall failed: {e}")
                return None

        # Fire all 5 lookups concurrently (profile already fetched above)
        results = await asyncio.gather(
            _fetch_long_term_memory(),
            _fetch_org_memory(),
            _fetch_kg_context(),
            _fetch_pattern_suggestions(),
            _fetch_episodic_memory(),
            return_exceptions=True,
        )

        # Collect context results (profile already handled above)
        for r in results:
            if isinstance(r, str) and r:
                injected_contexts.append(r)
            elif isinstance(r, Exception):
                logger.debug(f"[Memory] Parallel context fetch error: {r}")

    # Embed user profile directly into system_prompt (highest priority)
    if user_profile_ctx:
        system_prompt = system_prompt + "\n\n" + user_profile_ctx
        logger.info("[Memory] User profile embedded into system prompt")

    # Inject remaining contexts as a single system message
    if injected_contexts:
        # Add save_memory tool guidance at the end of context blocks
        injected_contexts.append(
            '[记忆工具提示] 当用户明确要求"记住"某事, 或你发现重要的用户偏好/事实时, '
            "立即调用 save_memory 工具保存, 不要等到对话结束。"
        )
        raw_messages.insert(
            0,
            {
                "role": "system",
                "content": "\n\n".join(injected_contexts),
            },
        )
        logger.info(f"[Memory] Injected {len(injected_contexts)} context blocks as one system message")

    # ── 2g. Pre-compaction Memory Flush ──
    # Before discarding old messages, extract any memorizable content
    # so important information isn't lost during compression.
    if config.user_id and len(raw_messages) > SHORT_TERM_WINDOW:
        try:
            from app.services.conversation_memory_service import conversation_memory_service

            older_msgs = raw_messages[:-SHORT_TERM_WINDOW]
            user_msgs_to_flush = [
                m for m in older_msgs
                if m.get("role") == "user" and m.get("content")
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
                from app.services.conversation_memory.storage import conversation_memory_service
                import asyncio
                asyncio.create_task(
                    conversation_memory_service.save_memory(
                        user_id=config.user_id,
                        key=f"tool_confirmed_usage_{_ct_name}",
                        value=f"用户确认调用 {_ct_name} 的正确参数: {_json.dumps(_ct_args, ensure_ascii=False)[:300]}",
                        category="tool_correction",
                        importance=0.8,
                        org_id=config.org_id,
                    )
                )
            except Exception:
                logger.debug("Failed to record HITL correction memory", exc_info=True)

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


async def persist_result(
    user_id: str,
    session_id: str,
    user_message: str,
    assistant_response: str,
    agent_name: str | None = None,
    metadata: dict | None = None,
    db_client: Any | None = None,
    org_id: str | None = None,
    completed_tool_calls: list[dict] | None = None,
    skip_cache: bool = False,
    skip_semantic: bool = False,
):
    """
    Post-graph: persist messages and update caches.

    1. Save user + assistant messages to DB
    2. Update semantic cache with the new Q-A pair
    3. Extract user-level and org-level long-term memories
    """
    client = db_client or supabase

    # Belt-and-suspenders: ensure no reasoning artifacts leak to DB
    if assistant_response:
        assistant_response = _strip_reasoning_from_history(assistant_response)

    # Save to DB (fire-and-forget)
    try:
        await ChatService.save_message(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=user_message,
            agent=agent_name,
            db_client=client,
            org_id=org_id,
        )
        await ChatService.save_message(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=assistant_response,
            agent=agent_name,
            metadata=metadata or {},
            db_client=client,
            org_id=org_id,
        )
    except Exception as e:
        logger.error(f"[Memory] Failed to persist messages: {e}")

    # Update semantic cache (skip for confirmation/blocked responses and SIMPLE queries)
    # ── Phase 2: Parallel extraction tasks (mutually independent) ──
    # All these tasks are independent — run in parallel for ~3-5x speedup
    extraction_tasks: list[tuple[str, Any]] = []

    # Task: Semantic cache update
    if user_message and assistant_response and not skip_cache and not skip_semantic:
        async def _update_semantic_cache():
            from app.services.semantic_cache import semantic_cache_service
            await semantic_cache_service.set_cache(user_message, assistant_response, user_id)
        extraction_tasks.append(("semantic_cache", _update_semantic_cache()))

    # Task: Extract user-level long-term memories (with conflict resolution)
    if user_message and not skip_semantic:
        # Detect if this conversation used llm_task (subtask delegation)
        # — subtask outputs should not be extracted as user preferences
        _has_subtask = bool(
            completed_tool_calls
            and any(
                (tc.get("tool_name") or tc.get("name")) == "llm_task"
                for tc in completed_tool_calls
                if isinstance(tc, dict)
            )
        )

        async def _extract_user_memories():
            from app.services.conversation_memory_service import conversation_memory_service
            messages_for_extraction = [
                {"role": "user", "content": user_message},
            ]
            if assistant_response:
                messages_for_extraction.append({"role": "assistant", "content": assistant_response})
            extracted = await conversation_memory_service.extract_preferences(
                user_id=user_id,
                messages=messages_for_extraction,
                db=client,
                is_subtask=_has_subtask,
            )
            if extracted:
                logger.info(f"[Memory] Extracted {len(extracted)} long-term memories for user {user_id}")
        extraction_tasks.append(("user_memories", _extract_user_memories()))

    # Task: Extract organization-level memories
    if user_message and org_id and not skip_semantic:
        async def _extract_org_memories():
            from app.services.conversation_memory_service import conversation_memory_service
            org_extracted = await conversation_memory_service.extract_org_memories(
                org_id=org_id,
                user_id=user_id,
                message=user_message,
                ai_response=assistant_response or "",
                db=client,
            )
            if org_extracted:
                logger.info(f"[Memory] Extracted {len(org_extracted)} org memories for org {org_id} by user {user_id}")
        extraction_tasks.append(("org_memories", _extract_org_memories()))

    # Task: Extract entity relationships for knowledge graph
    if user_message and org_id and not skip_semantic:
        async def _extract_graph():
            from app.services.conversation_memory.graph_extraction import extract_graph_entities
            tool_output_list = []
            if completed_tool_calls:
                tool_output_list = [
                    {"tool_name": tc.get("tool_name", ""), "result": tc.get("result", "")}
                    for tc in completed_tool_calls
                    if tc.get("tool_name")
                ]
            entities = await extract_graph_entities(
                user_message=user_message,
                ai_response=assistant_response or "",
                org_id=org_id,
                user_id=user_id,
                tool_outputs=tool_output_list,
                db=client,
                session_id=session_id,
            )
            if entities:
                logger.info(f"[Memory] Extracted {len(entities)} entity relations for org {org_id}")
        extraction_tasks.append(("graph_entities", _extract_graph()))

    # Task: Behavior pattern learning from tool usage
    if completed_tool_calls and org_id:
        async def _learn_patterns():
            from app.services.knowledge_graph_service import learn_tool_patterns
            patterns = await learn_tool_patterns(
                user_id=user_id,
                org_id=org_id,
                tool_calls=completed_tool_calls,
                user_message=user_message,
            )
            if patterns:
                logger.info(f"[Memory] Detected {len(patterns)} behavior patterns for org {org_id}")
        extraction_tasks.append(("tool_patterns", _learn_patterns()))

    # Task: Save interaction episode for experience recall
    if user_message and assistant_response and not skip_semantic:
        async def _save_episode():
            from app.services.conversation_memory_service import episodic_memory_service
            tools_used = []
            if completed_tool_calls:
                tools_used = list({tc.get("tool_name", "") for tc in completed_tool_calls if tc.get("tool_name")})
            await episodic_memory_service.save_episode(
                user_id=user_id,
                user_intent=user_message[:500],
                strategy=metadata.get("plan", "") if metadata else "",
                tools_used=tools_used,
                outcome=assistant_response[:500],
                confidence_score=metadata.get("confidence_score", 0.0) if metadata else 0.0,
                duration_ms=metadata.get("duration_ms", 0) if metadata else 0,
                total_tokens=metadata.get("total_tokens", 0) if metadata else 0,
                complexity=metadata.get("complexity", "moderate") if metadata else "moderate",
                thinking_steps=metadata.get("thinking_steps", 0) if metadata else 0,
                session_id=session_id,
                org_id=org_id,
                db=client,
            )
        extraction_tasks.append(("episode", _save_episode()))

    # Task: Save completed task summary as long-term memory (P1 memory fix)
    # Only when meaningful work was done: tool calls executed OR long response generated
    _has_tools = bool(completed_tool_calls and len(completed_tool_calls) > 0)
    _is_long_response = bool(assistant_response and len(assistant_response) > 300)
    if user_message and assistant_response and (_has_tools or _is_long_response) and not skip_semantic:
        async def _save_task_memory():
            from app.services.conversation_memory_service import conversation_memory_service
            # Build a concise task summary
            tool_names = []
            if completed_tool_calls:
                tool_names = list({tc.get("tool_name", "") for tc in completed_tool_calls if tc.get("tool_name")})
            tool_part = f"（使用了工具: {', '.join(tool_names)}）" if tool_names else ""
            # Truncate for storage
            task_summary = (
                f"用户请求: {user_message[:200]}\n"
                f"完成结果: {assistant_response[:300]}{tool_part}"
            )
            import hashlib
            task_key = f"task_{hashlib.md5(user_message[:100].encode()).hexdigest()[:10]}"
            await conversation_memory_service.save_memory(
                user_id=user_id,
                key=task_key,
                value=task_summary,
                category="completed_task",
                importance=0.7,
                org_id=org_id,
                db=client,
                metadata={
                    "session_id": session_id,
                    "tools_used": tool_names,
                    "response_length": len(assistant_response),
                },
            )
            logger.info(f"[Memory] Saved completed_task memory for user {user_id}: {task_key}")
        extraction_tasks.append(("task_memory", _save_task_memory()))

    # Execute all extraction tasks in parallel
    if extraction_tasks:
        task_names = [name for name, _ in extraction_tasks]
        coros = [coro for _, coro in extraction_tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        # Log any failures (non-fatal)
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.debug(f"[Memory] Parallel task '{name}' failed: {result}")





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
            if repaired and isinstance(repaired[-1], AIMessage) and getattr(repaired[-1], "tool_calls", None):
                repaired.append(msg)
            else:
                logger.debug("[Memory] Dropping orphaned ToolMessage (no preceding tool_calls AIMessage)")
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
                logger.debug("[Memory] Dropping AIMessage with orphaned tool_calls (no subsequent ToolMessages)")
                i += 1
                continue

        repaired.append(msg)
        i += 1

    dropped = len(messages) - len(repaired)
    if dropped:
        logger.info(f"[Memory] Repaired message list: {len(messages)} → {len(repaired)} ({dropped} orphans removed)")

    return repaired


async def _summarize_messages(
    messages: list[dict[str, str]],
    config: AgentConfig,
) -> str | None:
    """Three-level compaction pipeline (inspired by OpenClaw compaction.ts).

    Level 1: LLM chunk summarization with retry + exponential backoff
    Level 2: Filter oversized messages → retry with smaller input
    Level 3: Simple truncation fallback (no LLM)

    Preserves active tasks and last user request across all levels.
    """
    if not messages:
        return None

    # --- Level 1: LLM summarization with retry ---
    for attempt in range(3):
        try:
            from app.services.summary_service import summary_service

            # Split into chunks if too large (OpenClaw: independent chunk summaries)
            chunk_size = 15
            if len(messages) <= chunk_size:
                result = await summary_service.summarize_messages(
                    messages,
                    config={
                        "api_key": config.api_key,
                        "base_url": config.base_url,
                        "model": config.mini_model,
                    },
                )
                if result:
                    return result
            else:
                # Stage summarization: chunk independently then merge
                chunk_summaries = []
                for i in range(0, len(messages), chunk_size):
                    chunk = messages[i : i + chunk_size]
                    chunk_result = await summary_service.summarize_messages(
                        chunk,
                        config={
                            "api_key": config.api_key,
                            "base_url": config.base_url,
                            "model": config.mini_model,
                        },
                    )
                    if chunk_result:
                        chunk_summaries.append(chunk_result)

                if chunk_summaries:
                    return " | ".join(chunk_summaries)

        except Exception as e:
            wait = 2**attempt
            logger.warning(f"[Memory] Summarization attempt {attempt + 1}/3 failed: {e}, retry in {wait}s")
            if attempt < 2:
                await asyncio.sleep(wait)
            continue

    # --- Level 2: Filter oversized messages, retry with smaller input ---
    try:
        from app.services.summary_service import summary_service

        # Remove messages longer than 500 chars (likely tool results / RAG dumps)
        filtered = [m for m in messages if len(m.get("content", "")) <= 500]
        if filtered and len(filtered) >= 2:
            result = await summary_service.summarize_messages(
                filtered[-10:],
                config={
                    "api_key": config.api_key,
                    "base_url": config.base_url,
                    "model": config.mini_model,
                },
            )
            if result:
                return result
    except Exception as e:
        logger.warning(f"[Memory] Level-2 summarization failed: {e}")

    # --- Level 3: Simple truncation (no LLM, never fails) ---
    try:
        texts = []
        for msg in messages[-5:]:
            role_label = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")[:100]
            texts.append(f"{role_label}: {content}")
        return "历史摘要(截断): " + " | ".join(texts)
    except Exception:
        return None
