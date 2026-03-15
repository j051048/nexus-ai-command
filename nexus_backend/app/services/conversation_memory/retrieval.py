"""Memory retrieval: get, search (semantic + keyword), context building."""

import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

from .cleanup import compute_decay_score, mmr_rerank

logger = logging.getLogger(__name__)


async def get_memories(
    user_id: str,
    category: str | None = None,
    limit: int = 20,
    db: Any = None,
) -> list[dict]:
    """获取用户记忆列表（仅最新版本）"""
    client = db or supabase
    if not client:
        return []

    query = client.table("conversation_memories").select("*").eq("user_id", user_id)

    if category:
        query = query.eq("category", category)

    # P0: 只返回未被取代的最新版本
    query = query.is_("superseded_by", "null")

    result = await query.order("importance", desc=True).order("updated_at", desc=True).limit(limit).execute()

    return result.data or []


async def search_memories(
    user_id: str,
    query: str,
    limit: int = 5,
    org_id: str | None = None,
    db: Any = None,
) -> list[dict]:
    """搜索相关记忆（混合检索：embedding 语义搜索 + 关键字匹配）

    P0 Security: 强制 org_id 过滤，防止跨租户记忆泄露。
    P1 Enhancement: 优先使用 embedding 向量搜索，关键字匹配作为 fallback。
    """
    client = db or supabase
    if not client:
        return []

    memories: list[dict] = []

    try:
        # Strategy 1: Embedding-based semantic search (preferred)
        semantic_results = await _semantic_search(user_id, query, limit, org_id, client)
        if semantic_results:
            memories.extend(semantic_results)

        # Strategy 2: Keyword fallback (supplement if semantic results insufficient)
        if len(memories) < limit:
            keyword_results = await _keyword_search(user_id, query, limit - len(memories), org_id, client)
            seen_ids = {m["id"] for m in memories}
            for item in keyword_results:
                if item["id"] not in seen_ids:
                    memories.append(item)
    except Exception as e:
        logger.warning(f"Memory search failed: {e}")

    # Update access counts for returned memories
    now = datetime.now(UTC).isoformat()
    for mem in memories[:limit]:
        with contextlib.suppress(Exception):
            await (
                client.table("conversation_memories")
                .update(
                    {
                        "access_count": (mem.get("access_count", 0) or 0) + 1,
                        "last_accessed_at": now,
                    }
                )
                .eq("id", mem["id"])
                .execute()
            )

    # Apply temporal decay for final ranking, then MMR diversity reranking
    memories.sort(key=lambda m: compute_decay_score(m), reverse=True)
    memories = mmr_rerank(memories, limit)

    # Feature 3: 1-hop connection expansion on top results
    try:
        expanded = await _expand_top_connections(memories[:3], user_id, db=client)
        if expanded:
            seen_ids = {m["id"] for m in memories}
            for em in expanded:
                if em["id"] not in seen_ids:
                    memories.append(em)
    except Exception as e:
        logger.debug(f"Connection expansion skipped: {e}")

    return memories


async def _semantic_search(user_id: str, query: str, limit: int, org_id: str | None, client) -> list[dict]:
    """Embedding-based semantic search on memories using pgvector.
    P1: 优先使用 search_memories_hybrid（向量+FTS 融合+时间衰减），
    降级到 search_memories_by_embedding。
    """
    try:
        from app.services.vector_service import vector_service

        query_embedding = await vector_service.embed_text(query)
        if not query_embedding:
            return []

        # P1: Try hybrid search first (vector + FTS + time decay)
        try:
            params = {
                "p_user_id": user_id,
                "p_query_embedding": query_embedding,
                "p_query_text": query,
                "p_limit": limit,
            }
            if org_id:
                params["p_org_id"] = org_id
            result = await client.rpc("search_memories_hybrid", params).execute()
            if result.data:
                return result.data
        except Exception as e:
            logger.debug(f"Hybrid memory search unavailable, falling back: {e}")

        # Fallback: original embedding-only RPC
        params = {
            "query_embedding": query_embedding,
            "match_user_id": user_id,
            "match_limit": limit,
        }
        if org_id:
            params["match_org_id"] = org_id

        result = await client.rpc("search_memories_by_embedding", params).execute()
        return result.data or []
    except Exception as e:
        logger.debug(f"Semantic memory search unavailable, falling back to keyword: {e}")
        return []


async def _keyword_search(user_id: str, query: str, limit: int, org_id: str | None, client) -> list[dict]:
    """Keyword-based fallback search using ILIKE (P0: only latest versions)."""
    memories: list[dict] = []

    # Build base query with mandatory tenant isolation + version filter
    base_query = (
        client.table("conversation_memories")
        .select("*")
        .eq("user_id", user_id)
        .is_("superseded_by", "null")
    )
    if org_id:
        base_query = base_query.eq("organization_id", org_id)

    # Search in key field
    result_key = await base_query.ilike("key", f"%{query}%").limit(limit).execute()
    if result_key.data:
        memories.extend(result_key.data)

    # Search in value field
    if len(memories) < limit:
        seen_ids = {m["id"] for m in memories}
        val_query = (
            client.table("conversation_memories")
            .select("*")
            .eq("user_id", user_id)
            .is_("superseded_by", "null")
        )
        if org_id:
            val_query = val_query.eq("organization_id", org_id)
        result_value = await val_query.ilike("value", f"%{query}%").limit(limit).execute()
        if result_value.data:
            for item in result_value.data:
                if item["id"] not in seen_ids:
                    memories.append(item)

    return memories


async def _expand_top_connections(
    memories: list[dict],
    user_id: str,
    limit: int = 3,
    db: Any = None,
) -> list[dict]:
    """1-hop expansion: fetch connected memories for top results."""
    client = db or supabase
    if not client:
        return []

    connected_ids: set[str] = set()
    seen_ids = {m["id"] for m in memories}

    for mem in memories[:limit]:
        connections = mem.get("connections", [])
        if not isinstance(connections, list):
            continue
        for conn in connections:
            mid = conn.get("memory_id")
            if mid and mid not in seen_ids and mid not in connected_ids:
                connected_ids.add(mid)

    if not connected_ids:
        return []

    try:
        result = (
            await client.table("conversation_memories")
            .select("*")
            .eq("user_id", user_id)
            .in_("id", list(connected_ids)[:10])
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.debug(f"Connection expansion failed: {e}")
        return []


async def search_consolidations(
    user_id: str,
    query: str,
    limit: int = 3,
    org_id: str | None = None,
    db: Any = None,
) -> list[dict]:
    """Search consolidated insights via embedding similarity."""
    client = db or supabase
    if not client:
        return []
    try:
        from app.services.vector_service import vector_service

        query_embedding = await vector_service.embed_text(query)
        if not query_embedding:
            return []

        params = {
            "query_embedding": query_embedding,
            "match_user_id": user_id,
            "match_limit": limit,
        }
        if org_id:
            params["match_org_id"] = org_id

        result = await client.rpc("search_consolidations_by_embedding", params).execute()
        return result.data or []
    except Exception as e:
        logger.debug(f"Consolidation search failed: {e}")
        return []


async def build_memory_context(
    user_id: str,
    current_query: str,
    db: Any = None,
) -> str:
    """
    构建记忆上下文，注入到 system prompt 中。

    策略：
    1. 显式记忆无条件注入（用户主动要求记住的，量少且重要）
    2. 其余记忆（偏好/事实等）走语义搜索，只注入与当前查询相关的
    """
    context_parts: list[str] = []

    # 1) Explicit memories -- always inject (user explicitly asked to remember)
    explicit = await get_memories(
        user_id=user_id,
        category="explicit_memory",
        limit=5,
        db=db,
    )
    if explicit:
        mem_lines = [f"- {m['value']}" for m in explicit]
        context_parts.append("用户记忆:\n" + "\n".join(mem_lines))

    # 2) Query-relevant memories -- semantic search across all categories
    if current_query and len(current_query) >= 2:
        relevant = await search_memories(
            user_id=user_id,
            query=current_query,
            limit=5,
            db=db,
        )
        if relevant:
            existing_ids = {m["id"] for m in explicit}
            new_relevant = [m for m in relevant if m["id"] not in existing_ids]
            if new_relevant:
                rel_lines = [f"- {m['value']}" for m in new_relevant]
                context_parts.append("相关记忆:\n" + "\n".join(rel_lines))

    # 3) Consolidated insights -- semantic search for cross-memory patterns
    if current_query and len(current_query) >= 2:
        try:
            consolidations = await search_consolidations(
                user_id=user_id,
                query=current_query,
                limit=3,
                db=db,
            )
            if consolidations:
                cons_lines = [
                    f"- [{c['insight_type']}] {c['title']}: {c['content']}"
                    for c in consolidations
                ]
                context_parts.append("记忆洞察:\n" + "\n".join(cons_lines))
        except Exception as e:
            logger.debug(f"Consolidation context injection skipped: {e}")

    if not context_parts:
        return ""

    return "[用户记忆上下文]\n" + "\n\n".join(context_parts) + "\n[记忆上下文结束]"
