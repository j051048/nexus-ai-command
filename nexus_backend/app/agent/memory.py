"""
Hybrid Memory Manager for the LangGraph Agent.

Combines:
1. Short-term: Sliding window of recent messages (configurable size)
2. Long-term: Summary of older messages via LLM compression
3. Semantic: Vector search for relevant past context
4. Semantic Cache: Fast-path for repeated / similar queries

This module is called BEFORE the graph runs to prepare the initial
message list, and AFTER the graph runs to persist results.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage

from app.core.config import settings
from app.core.database import supabase
from app.services.cache_service import cache_service
from app.services.chat_service import ChatService
from app.agent.state import AgentConfig

logger = logging.getLogger(__name__)

# Configurable window size
SHORT_TERM_WINDOW = getattr(settings, "MAX_CHAT_HISTORY", 10)


async def prepare_initial_state(
    raw_messages: List[Dict[str, str]],
    system_prompt: str,
    config: AgentConfig,
    db_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Build the initial state components for the agent graph.

    Steps:
    1. Semantic Cache Lookup
    2. Summarization (if needed)
    3. RAG Retrieval (if enabled)
    4. BaseMessage conversion

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
        "rag_sources": []
    }

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

    # ── 2. RAG Retrieval ──
    if config.enable_rag_inject and last_user_msg:
        try:
            from app.services.vector_service import vector_service
            # Search knowledge base for relevant docs
            docs = await vector_service.search_documents(
                query=last_user_msg,
                org_id=config.org_id,
                limit=config.rag_inject_limit,
                min_score=config.rag_inject_threshold,
                db_client=client
            )
            if docs:
                context_parts = []
                sources = []
                for d in docs:
                    context_parts.append(d.get("content", ""))
                    sources.append(d.get("metadata", {}).get("source", "知识库"))
                
                result["rag_context"] = "\n\n".join(context_parts)
                result["rag_sources"] = list(set(sources))
                logger.info(f"[Memory] RAG injected {len(docs)} docs for user {config.user_id}")
        except Exception as e:
            logger.warning(f"[Memory] RAG retrieval failed: {e}")

    # ── 3. Sliding Window with Summary ──
    if len(raw_messages) > SHORT_TERM_WINDOW:
        older = raw_messages[:-SHORT_TERM_WINDOW]
        recent = raw_messages[-SHORT_TERM_WINDOW:]

        summary = await _summarize_messages(older, config)
        if summary:
            recent.insert(0, {
                "role": "system",
                "content": f"[对话历史摘要] {summary}",
            })
        raw_messages = recent

    # ── 4. Convert to LangChain messages ──
    lc_messages: List[BaseMessage] = []
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
    agent_name: Optional[str] = None,
    metadata: Optional[Dict] = None,
    db_client: Optional[Any] = None,
):
    """
    Post-graph: persist messages and update caches.

    1. Save user + assistant messages to DB
    2. Update semantic cache with the new Q-A pair
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
            await semantic_cache_service.set_cache(
                user_message, assistant_response, user_id
            )
        except Exception as e:
            logger.debug(f"[Memory] Failed to update semantic cache: {e}")


async def load_session_history(
    user_id: str,
    session_id: str,
    limit: int = SHORT_TERM_WINDOW,
    db_client: Optional[Any] = None,
) -> List[Dict[str, str]]:
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
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in (response.data or [])
        ]
    except Exception as e:
        logger.warning(f"[Memory] Failed to load session history: {e}")
        return []


# ─── Internal Helpers ────────────────────────────────────────────────────────

async def _summarize_messages(
    messages: List[Dict[str, str]],
    config: AgentConfig,
) -> Optional[str]:
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
