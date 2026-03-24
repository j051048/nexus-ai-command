"""Memory retrieval: get, search (semantic + keyword), context building."""

import contextlib
import logging
import re
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

from .cleanup import compute_decay_score, mmr_rerank

logger = logging.getLogger(__name__)

# ── Chinese stop words for keyword extraction ────────────────────────────
_STOP_WORDS = frozenset(
    "的 了 么 吗 嘛 呢 吧 啊 呀 哦 是 在 有 和 与 或 不 也 都 就 还 又 能 可以 "
    "要 会 把 被 让 给 从 到 对 向 为 我 你 他 她 它 我们 你们 他们 "
    "这 那 什么 怎么 哪 几 多少 一个 一些 每 个 的话 以及 "
    "记得 记住 还记得 知道 想起 回忆 前提 哪些 怎样 如何 为什么".split()
)

# Minimum meaningful term length (Chinese characters)
_MIN_TERM_LEN = 2


def _extract_search_terms(query: str) -> list[str]:
    """Extract meaningful search terms from a Chinese query.

    Uses jieba word segmentation if available, otherwise falls back to
    bigram extraction for Chinese text.
    """
    # Strip punctuation
    clean = re.sub(r"[，。！？、；：""''（）【】…—\s\d\W]+", " ", query).strip()
    if not clean:
        return []

    terms: list[str] = []
    try:
        import jieba
        words = jieba.lcut(clean)
        terms = [w.strip() for w in words if w.strip() and len(w.strip()) >= _MIN_TERM_LEN and w.strip() not in _STOP_WORDS]
    except ImportError:
        # Fallback: sliding bigrams for Chinese text
        chars = re.sub(r"\s+", "", clean)
        for i in range(len(chars) - 1):
            bigram = chars[i:i + 2]
            if bigram not in _STOP_WORDS:
                terms.append(bigram)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:6]  # Cap at 6 terms to limit DB queries


def _days_since(date_str: str) -> int:
    if not date_str:
        return 0
    try:
        from datetime import UTC, datetime
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return (datetime.now(UTC) - dt).days
    except Exception:
        return 0

def _relative_age(date_str: str) -> str:
    if not date_str:
        return "未知时间"
    days = _days_since(date_str)
    if days == 0:
        return "今天"
    elif days < 30:
        return f"{days}天前"
    elif days < 365:
        return f"{days // 30}个月前"
    return f"{days // 365}年前"

def _format_by_temperature(mem: dict) -> str:
    """根据记忆温度选择详细度（热=全文，温=截断，冷=摘要），结构化 XML 格式。"""
    updated_at = mem.get("updated_at") or mem.get("valid_from") or mem.get("created_at") or ""
    days_old = _days_since(updated_at)
    age_str = _relative_age(updated_at)
    category = mem.get("category", "")
    importance = float(mem.get("importance", 0.5))
    value = mem.get("value", "")

    # Decrypt if the value was encrypted at rest
    from app.services.conversation_memory.storage import decrypt_memory_value
    value = decrypt_memory_value(value)
    
    parts = [f'  <memory type="{category}" age="{age_str}" importance="{importance:.1f}">']
    if days_old < 3 and importance > 0.7:
        parts.append(value)
    elif days_old < 30:
        parts.append(value[:150])
    else:
        key = mem.get("key", "")
        parts.append(f"{key}: {value[:30]}... (需使用 search_long_term_memory 工具查看详情)")
    parts.append('</memory>')
    return "".join(parts)


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

    # Update access counts and Bayesian importance reinforcement for returned memories
    now = datetime.now(UTC).isoformat()
    for mem in memories[:limit]:
        with contextlib.suppress(Exception):
            current_importance = float(mem.get("importance", 0.5) or 0.5)
            access_count = int(mem.get("access_count", 0) or 0)
            # Bayesian reinforcement: small boost on retrieval, diminishing returns
            # Formula: delta = 0.05 / (1 + access_count * 0.3), capped at importance=1.0
            # First hit: +0.05, 5th hit: +0.02, 10th hit: +0.013
            delta = 0.05 / (1 + access_count * 0.3)
            new_importance = min(current_importance + delta, 1.0)
            await (
                client.table("conversation_memories")
                .update(
                    {
                        "access_count": access_count + 1,
                        "last_accessed_at": now,
                        "importance": round(new_importance, 4),
                    }
                )
                .eq("id", mem["id"])
                .execute()
            )

    # Apply temporal decay for final ranking, then MMR diversity reranking
    _TYPE_WEIGHTS = {
        "explicit_memory": 1.5,
        "preference": 1.0,
        "fact": 1.0,
        "behavior_pattern": 0.8,
        "tool_usage": 0.7,
    }

    def _weighted_score(m: dict) -> float:
        base = compute_decay_score(m)
        weight = _TYPE_WEIGHTS.get(m.get("category", "preference"), 1.0)
        return base * weight

    memories.sort(key=_weighted_score, reverse=True)
    memories = mmr_rerank(memories, limit)

    # P0: 最低相关性阈值过滤，防止冷旧记忆污染上下文
    _MIN_DECAY_SCORE = 0.15
    if memories:
        pre_count = len(memories)
        memories = [m for m in memories if _weighted_score(m) >= _MIN_DECAY_SCORE]
        if len(memories) < pre_count:
            logger.info(f"[Memory] Relevance filter: {pre_count} → {len(memories)}")

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
    P1: 优先使用 search_memories_hybrid（向量+时间衰减），
    降级到 search_memories_by_embedding。

    注: hybrid RPC 的 FTS 分支已移除 (20260323 迁移)，因为 Supabase 'simple'
    分词器对中文无效。中文关键词搜索由 _keyword_search (jieba+ILIKE) 负责。
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
    """Keyword-based fallback search using ILIKE with Chinese tokenization."""
    # Extract meaningful terms from the query (e.g. "还记得我的2个同学么" → ["同学"])
    terms = _extract_search_terms(query)
    if not terms:
        # Fallback: use original query if tokenization yields nothing
        terms = [query]

    memories: list[dict] = []
    seen_ids: set[str] = set()

    for term in terms:
        if len(memories) >= limit:
            break

        # Search in key field
        key_query = (
            client.table("conversation_memories")
            .select("*")
            .eq("user_id", user_id)
            .is_("superseded_by", "null")
        )
        if org_id:
            key_query = key_query.eq("organization_id", org_id)
        try:
            result_key = await key_query.ilike("key", f"%{term}%").limit(limit).execute()
            for item in (result_key.data or []):
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    memories.append(item)
        except Exception:
            pass

        if len(memories) >= limit:
            break

        # Search in value field
        val_query = (
            client.table("conversation_memories")
            .select("*")
            .eq("user_id", user_id)
            .is_("superseded_by", "null")
        )
        if org_id:
            val_query = val_query.eq("organization_id", org_id)
        try:
            result_val = await val_query.ilike("value", f"%{term}%").limit(limit).execute()
            for item in (result_val.data or []):
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    memories.append(item)
        except Exception:
            pass

    return memories[:limit]


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
    complexity: str | None = None,
) -> str:
    """
    构建记忆上下文，注入到 system prompt 中。
    使用 complexity 执行意图感知动态路由 (Intent-Aware Router)。
    """
    context_parts: list[str] = []

    # Analyze complexity to optimize retrieval caps (P2: Intent-Aware Memory Router)
    explicit_limit = 5
    relevant_limit = 5
    consolidated_limit = 3

    if complexity:
        _c = str(complexity).upper()
        if _c in ("CRITICAL", "COMPLEX"):
            relevant_limit = 10
            consolidated_limit = 5
        elif _c == "SIMPLE":
            relevant_limit = 3
            explicit_limit = 3
            
    # 0) Directive memories — high-importance constraints injected separately
    directive_block = ""

    # 1) Explicit memories -- always inject (user explicitly asked to remember)
    explicit = await get_memories(
        user_id=user_id,
        category="explicit_memory",
        limit=explicit_limit,
        db=db,
    )
    if explicit:
        # Split: importance >= 0.85 → <constraints> header; rest → <user-memories>
        directives = [m for m in explicit if (m.get("importance") or 0) >= 0.85]
        non_directives = [m for m in explicit if (m.get("importance") or 0) < 0.85]

        if directives:
            d_lines = [f"  - {m.get('enriched_value') or m.get('value', '')}" for m in directives]
            directive_block = "<constraints>\n" + "\n".join(d_lines) + "\n</constraints>"

        if non_directives:
            mem_lines = [_format_by_temperature(m) for m in non_directives]
            context_parts.append("\n".join(mem_lines))

    # 2) Query-relevant memories -- semantic search across all categories
    if current_query and len(current_query) >= 2:
        relevant = await search_memories(
            user_id=user_id,
            query=current_query,
            limit=relevant_limit,
            db=db,
        )
        if relevant:
            existing_ids = {m["id"] for m in explicit}
            new_relevant = [m for m in relevant if m["id"] not in existing_ids]
            if new_relevant:
                rel_lines = [_format_by_temperature(m) for m in new_relevant]
                context_parts.append("\n".join(rel_lines))

    # 3) Consolidated insights -- semantic search for cross-memory patterns
    if current_query and len(current_query) >= 2:
        try:
            consolidations = await search_consolidations(
                user_id=user_id,
                query=current_query,
                limit=consolidated_limit,
                db=db,
            )
            if consolidations:
                cons_lines = [
                    f"  <insight type=\"{c['insight_type']}\" title=\"{c['title']}\">{c['content']}</insight>"
                    for c in consolidations
                ]
                context_parts.append("\n".join(cons_lines))
        except Exception as e:
            logger.debug(f"Consolidation context injection skipped: {e}")

    if not context_parts and not directive_block:
        return ""

    result_parts = []
    if directive_block:
        result_parts.append(directive_block)
    if context_parts:
        result_parts.append("<user-memories>\n" + "\n".join(context_parts) + "\n</user-memories>")
    return "\n\n".join(result_parts)
