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

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.agent.state import AgentConfig
from app.core.config import settings
from app.core.database import supabase
from app.services.chat_service import ChatService
from app.services.token_service import token_counter

logger = logging.getLogger(__name__)

# Configurable window size
SHORT_TERM_WINDOW = getattr(settings, "MAX_CHAT_HISTORY", 10)

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
        f"[Memory] Trimmed from {total_tokens} to {new_tokens} tokens " f"({len(messages)} → {len(trimmed)} messages)"
    )
    return trimmed


class QueryTransformer:
    """
    P1 Fix #22: Query Transformation for better RAG retrieval.

    Implements:
    1. HyDE (Hypothetical Document Embeddings)
    2. Multi-Query expansion
    3. Query rewriting for better semantic matching
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self._llm_client = None
        self._resolved_model = None

    async def _get_llm(self):
        """Lazy load LLM client, resolving via LLM gateway when available."""
        if self._llm_client is None:
            try:
                from openai import AsyncOpenAI

                # Try gateway resolution first
                try:
                    from app.services.llm_helpers import resolve_model_config
                    resolved = await resolve_model_config(
                        org_id=getattr(self.config, "org_id", None) or "default",
                    )
                    self._llm_client = AsyncOpenAI(
                        api_key=resolved["api_key"],
                        base_url=resolved["base_url"],
                    )
                    self._resolved_model = resolved.get("model", self.config.mini_model)
                    return self._llm_client
                except Exception:
                    pass

                self._llm_client = AsyncOpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
            except Exception as e:
                logger.warning(f"Failed to init LLM for query transformation: {e}")
        return self._llm_client

    async def generate_hyde(self, query: str) -> str:
        """
        Generate a hypothetical document that would answer the query.
        This document is then used for embedding search.
        """
        llm = await self._get_llm()
        if not llm:
            return query

        prompt = f"""请生成一段假设性的文档内容，这段文档应该能够回答用户的问题。

用户问题: {query}

要求:
1. 文档应该包含问题的答案
2. 使用专业、清晰的语言
3. 长度约200-300字
4. 直接输出文档内容，不要解释

假设性文档:"""

        try:
            response = await llm.chat.completions.create(
                model=self._resolved_model or self.config.mini_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
            hyde_doc = response.choices[0].message.content.strip()
            logger.debug(f"[HyDE] Generated hypothetical doc: {hyde_doc[:100]}...")
            return hyde_doc
        except Exception as e:
            logger.warning(f"HyDE generation failed: {e}")
            return query

    async def expand_multi_query(self, query: str, num_queries: int = 3) -> list[str]:
        """
        Generate multiple related queries for better retrieval coverage.
        """
        llm = await self._get_llm()
        if not llm:
            return [query]

        prompt = f"""请根据用户的问题，生成{num_queries}个语义相近但表达方式不同的问题。
这些问题将用于检索相关知识，以提高检索的全面性。

原问题: {query}

要求:
1. 保持原问题的核心意图
2. 使用不同的词汇和表达方式
3. 覆盖不同的检索角度
4. 每个问题一行，不要编号

生成的问题:"""

        try:
            response = await llm.chat.completions.create(
                model=self._resolved_model or self.config.mini_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.5,
            )
            expanded = response.choices[0].message.content.strip().split("\n")
            expanded = [q.strip() for q in expanded if q.strip()][:num_queries]

            # Always include original query
            all_queries = [query] + expanded
            logger.debug(f"[MultiQuery] Generated {len(all_queries)} query variants")
            return all_queries
        except Exception as e:
            logger.warning(f"Multi-query expansion failed: {e}")
            return [query]

    async def rewrite_query(self, query: str) -> str:
        """
        Rewrite query for better semantic matching.
        """
        llm = await self._get_llm()
        if not llm:
            return query

        prompt = f"""请将以下问题重写为更适合检索的形式。

原问题: {query}

要求:
1. 保留核心信息需求
2. 使用更标准、更清晰的表达
3. 移除口语化表达
4. 添加可能的关键词
5. 直接输出重写后的问题

重写后的问题:"""

        try:
            response = await llm.chat.completions.create(
                model=self._resolved_model or self.config.mini_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.2,
            )
            rewritten = response.choices[0].message.content.strip()
            logger.debug(f"[QueryRewrite] '{query}' -> '{rewritten}'")
            return rewritten
        except Exception as e:
            logger.warning(f"Query rewriting failed: {e}")
            return query


async def prepare_initial_state(
    raw_messages: list[dict[str, str]],
    system_prompt: str,
    config: AgentConfig,
    db_client: Any | None = None,
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

    # ── 1. Semantic Cache Lookup ──
    last_user_msg = ""
    for msg in reversed(raw_messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    if last_user_msg and config.user_id:
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

            # Determine transformation strategy based on config
            # HyDE is expensive; only enable by default for the knowledge agent
            is_knowledge_agent = getattr(config, "agent_name", "") in ("knowledge", "knowledge_base")
            use_hyde = getattr(config, "use_hyde", is_knowledge_agent)
            use_multi_query = getattr(config, "use_multi_query", is_knowledge_agent)

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

            # Strategy 2: Multi-Query Expansion
            if use_multi_query:
                expanded_queries = await transformer.expand_multi_query(last_user_msg, num_queries=3)
                for q in expanded_queries:
                    docs = await vector_service.search(
                        query=q,
                        user_id=config.user_id,
                        limit=config.rag_inject_limit // len(expanded_queries),
                        org_id=config.org_id,
                    )
                    if isinstance(docs, str) and docs:
                        all_docs.append({"content": docs, "source": f"查询: {q[:30]}"})

            # Strategy 3: Original query (always included)
            original_docs = await vector_service.search(
                query=last_user_msg,
                user_id=config.user_id,
                limit=config.rag_inject_limit,
                org_id=config.org_id,
            )
            if isinstance(original_docs, str) and original_docs:
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

                # Limit total context length
                max_context = 3000
                context_parts = []
                current_length = 0
                for doc in unique_docs:
                    content = doc.get("content", "")
                    if current_length + len(content) <= max_context:
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
            logger.warning(f"[Memory] RAG retrieval failed: {e}")

    # ── 2b. Long-term Memory Injection ──
    # Load user preferences and explicit memories from conversation_memory_service
    if config.user_id and last_user_msg:
        try:
            from app.services.conversation_memory_service import conversation_memory_service

            memory_context = await conversation_memory_service.build_memory_context(
                user_id=config.user_id,
                current_query=last_user_msg,
                db=client,
            )
            if memory_context:
                # Inject as the first system-level context message
                raw_messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": memory_context,
                    },
                )
                logger.info(f"[Memory] Injected long-term memory context for user {config.user_id}")
        except Exception as e:
            logger.debug(f"[Memory] Long-term memory injection skipped: {e}")

    # ── 2c. Organization Memory Injection ──
    if config.org_id and last_user_msg:
        try:
            from app.services.conversation_memory_service import conversation_memory_service

            org_memory_ctx = await conversation_memory_service.build_org_memory_context(
                org_id=config.org_id,
                query=last_user_msg,
                db=client,
            )
            if org_memory_ctx:
                raw_messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": "[组织共享记忆上下文]\n" + org_memory_ctx + "\n[组织记忆结束]",
                    },
                )
                logger.info(f"[Memory] Injected org memory context for org {config.org_id}")
        except Exception as e:
            logger.debug(f"[Memory] Org memory context failed: {e}")

    # ── 3. Sliding Window with Summary ──
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

    # ── 3b. Token Window Trim ──
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
            lc_messages.append(AIMessage(content=content))

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
):
    """
    Post-graph: persist messages and update caches.

    1. Save user + assistant messages to DB
    2. Update semantic cache with the new Q-A pair
    3. Extract user-level and org-level long-term memories
    """
    client = db_client or supabase

    # Save to DB (fire-and-forget)
    try:
        await ChatService.save_message(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=user_message,
            agent=agent_name,
            db_client=client,
        )
        await ChatService.save_message(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=assistant_response,
            agent=agent_name,
            metadata=metadata or {},
            db_client=client,
        )
    except Exception as e:
        logger.error(f"[Memory] Failed to persist messages: {e}")

    # Update semantic cache
    if user_message and assistant_response:
        try:
            from app.services.semantic_cache import semantic_cache_service

            await semantic_cache_service.set_cache(user_message, assistant_response, user_id)
        except Exception as e:
            logger.debug(f"[Memory] Failed to update semantic cache: {e}")

    # Extract and persist long-term memories from conversation
    if user_message:
        try:
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
            )
            if extracted:
                logger.info(f"[Memory] Extracted {len(extracted)} long-term memories for user {user_id}")
        except Exception as e:
            logger.debug(f"[Memory] Memory extraction skipped: {e}")

    # Extract and persist organization-level memories
    if user_message and org_id:
        try:
            from app.services.conversation_memory_service import conversation_memory_service

            org_extracted = await conversation_memory_service.extract_org_memories(
                org_id=org_id,
                user_id=user_id,
                message=user_message,
                ai_response=assistant_response or "",
                db=client,
            )
            if org_extracted:
                logger.info(
                    f"[Memory] Extracted {len(org_extracted)} org memories for org {org_id} by user {user_id}"
                )
        except Exception as e:
            logger.debug(f"[Memory] Org memory extraction skipped: {e}")


async def load_session_history(
    user_id: str,
    session_id: str,
    limit: int = SHORT_TERM_WINDOW,
    db_client: Any | None = None,
) -> list[dict[str, str]]:
    """
    Load recent chat history from the database for a session.
    Returns list of {"role": ..., "content": ...} dicts.
    """
    client = db_client or supabase
    try:
        response = (
            await client.table("chat_messages")
            .select("role, content")
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .limit(limit)
            .execute()
        )
        return [{"role": msg["role"], "content": msg["content"]} for msg in (response.data or [])]
    except Exception as e:
        logger.warning(f"[Memory] Failed to load session history: {e}")
        return []


# ─── Internal Helpers ────────────────────────────────────────────────────────


async def _summarize_messages(
    messages: list[dict[str, str]],
    config: AgentConfig,
) -> str | None:
    """
    Use the LLM to compress older messages into a summary.
    Falls back to simple truncation if the LLM call fails.
    """
    if not messages:
        return None

    try:
        from app.services.summary_service import summary_service

        return await summary_service.summarize_messages(
            messages,
            config={
                "api_key": config.api_key,
                "base_url": config.base_url,
                "model": config.mini_model,  # Use cheaper model for summaries
            },
        )
    except Exception as e:
        logger.warning(f"[Memory] LLM summarization failed: {e}")

    # Fallback: simple text truncation
    try:
        texts = []
        for msg in messages[-5:]:
            role_label = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")[:100]
            texts.append(f"{role_label}: {content}")
        return "历史摘要(截断): " + " | ".join(texts)
    except Exception:
        return None
