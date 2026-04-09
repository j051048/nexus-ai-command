"""Memory retrieval: get, search (semantic + keyword), context building."""

import asyncio
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

from app.core.database import supabase

from .cleanup import compute_decay_score, mmr_rerank

logger = logging.getLogger(__name__)

# ── Chinese stop words for keyword extraction ────────────────────────────
_STOP_WORDS = frozenset(
    [
        "的",
        "了",
        "么",
        "吗",
        "嘛",
        "呢",
        "吧",
        "啊",
        "呀",
        "哦",
        "是",
        "在",
        "有",
        "和",
        "与",
        "或",
        "不",
        "也",
        "都",
        "就",
        "还",
        "又",
        "能",
        "可以",
        "要",
        "会",
        "把",
        "被",
        "让",
        "给",
        "从",
        "到",
        "对",
        "向",
        "为",
        "我",
        "你",
        "他",
        "她",
        "它",
        "我们",
        "你们",
        "他们",
        "这",
        "那",
        "什么",
        "怎么",
        "哪",
        "几",
        "多少",
        "一个",
        "一些",
        "每",
        "个",
        "的话",
        "以及",
        "记得",
        "记住",
        "还记得",
        "知道",
        "想起",
        "回忆",
        "前提",
        "哪些",
        "怎样",
        "如何",
        "为什么",
    ]
)

_EN_STOP_WORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "shall",
        "should",
        "can",
        "could",
        "may",
        "might",
        "must",
        "need",
        "dare",
        "ought",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "for",
        "with",
        "from",
        "as",
        "into",
        "about",
        "between",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "and",
        "or",
        "but",
        "not",
        "no",
        "nor",
        "so",
        "yet",
        "both",
        "either",
        "neither",
        "each",
        "every",
        "all",
        "any",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "than",
        "too",
        "very",
        "also",
        "just",
        "only",
        "even",
        "still",
        "already",
        "again",
        "ever",
        "never",
        "always",
        "often",
        "usually",
        "sometimes",
        "i",
        "me",
        "my",
        "mine",
        "we",
        "us",
        "our",
        "ours",
        "you",
        "your",
        "yours",
        "he",
        "him",
        "his",
        "she",
        "her",
        "hers",
        "it",
        "its",
        "they",
        "them",
        "their",
        "theirs",
        "this",
        "that",
        "these",
        "those",
        "here",
        "there",
        "where",
        "when",
        "how",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "if",
        "then",
        "else",
        "while",
        "until",
        "because",
        "since",
        "although",
        "though",
        "unless",
        "whether",
        "up",
        "down",
        "out",
        "off",
        "over",
        "under",
        "way",
        "much",
        "many",
        "well",
        "back",
        "even",
        "go",
        "get",
        "make",
        "like",
        "know",
        "think",
        "want",
        "say",
        "tell",
        "give",
        "take",
        "come",
        "see",
        "find",
        "use",
        "work",
        "call",
        "try",
        "ask",
        "keep",
        "let",
        "begin",
        "seem",
        "help",
        "show",
        "hear",
        "play",
        "run",
        "move",
        "live",
        "believe",
        "hold",
        "bring",
        "happen",
        "write",
        "provide",
        "sit",
        "stand",
        "lose",
        "pay",
        "meet",
        "include",
        "continue",
        "set",
        "learn",
        "change",
        "lead",
        "understand",
        "watch",
        "follow",
        "stop",
        "create",
        "speak",
        "read",
        "grow",
        "open",
        "walk",
        "win",
        "offer",
        "remember",
        "love",
        "consider",
        "appear",
        "buy",
        "wait",
        "serve",
        "die",
        "send",
        "expect",
        "build",
        "stay",
        "fall",
        "cut",
        "reach",
        "kill",
        "remain",
        "suggest",
        "raise",
        "pass",
        "sell",
        "require",
        "report",
        "decide",
        "pull",
        "develop",
    ]
)

# Minimum meaningful term length (Chinese characters)
_MIN_TERM_LEN = 2

# Check if text contains Latin characters (English content indicator)
_HAS_LATIN = re.compile(r"[a-zA-Z]{2,}")


def _extract_search_terms(query: str) -> list[str]:
    """Extract meaningful search terms from Chinese, English, or mixed queries.

    - Chinese path: jieba segmentation → stop word filter
    - English path: whitespace split → stop word filter → keep 2+ char tokens
    - Mixed: both paths merged, deduplicated
    - P1 Fix: 保留人名（2-4个中文字符的词）
    """
    # Strip punctuation (keep Latin + CJK characters)
    clean = re.sub(r"[，。！？、；：\u201c\u201d\u2018\u2019（）【】…—\s\d]+", " ", query)
    clean = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", clean).strip()
    if not clean:
        return []

    has_latin = bool(_HAS_LATIN.search(clean))
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", clean))

    terms: list[str] = []

    # English path: whitespace tokenization + stop word filter
    if has_latin:
        for word in clean.split():
            w = word.strip().lower()
            if len(w) >= 2 and w not in _EN_STOP_WORDS and not w.isdigit():
                # Keep original case for proper nouns (capitalized words)
                terms.append(word.strip() if word[0].isupper() else w)

    # Chinese path: jieba segmentation
    if has_cjk:
        # Extract only CJK portions for jieba
        cjk_text = re.sub(r"[^\u4e00-\u9fff]+", " ", clean).strip()
        if cjk_text:
            try:
                import jieba

                words = jieba.lcut(cjk_text)
                for w in words:
                    w = w.strip()
                    if not w or len(w) < _MIN_TERM_LEN:
                        continue
                    # P1 Fix: 2-4字的中文词可能是人名，不过滤
                    if 2 <= len(w) <= 4 or w not in _STOP_WORDS:
                        terms.append(w)
            except ImportError:
                chars = re.sub(r"\s+", "", cjk_text)
                for i in range(len(chars) - 1):
                    bigram = chars[i : i + 2]
                    if bigram not in _STOP_WORDS:
                        terms.append(bigram)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in terms:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique[:8]  # Cap at 8 terms (up from 6) for bilingual queries


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


def _absolute_date(date_str: str) -> str:
    """Extract absolute date (YYYY-MM-DD) from ISO timestamp for time anchoring."""
    if not date_str:
        return ""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


def _format_by_temperature(mem: dict) -> str:
    """根据记忆温度选择详细度（热=全文，温=截断，冷=摘要），结构化 XML 格式。

    P0 LoCoMo Fix: 每条记忆强制携带绝对时间戳 date="YYYY-MM-DD"，
    解决 LLM 时序推理混乱（将相对时间误解为系统当前时间）。
    """
    updated_at = mem.get("updated_at") or mem.get("valid_from") or mem.get("created_at") or ""
    days_old = _days_since(updated_at)
    age_str = _relative_age(updated_at)
    abs_date = _absolute_date(updated_at)
    category = mem.get("category", "")
    importance = float(mem.get("importance", 0.5))
    value = mem.get("value", "")

    # Decrypt if the value was encrypted at rest
    from app.services.conversation_memory.storage import decrypt_memory_value

    value = decrypt_memory_value(value)

    # Time anchor: absolute date + relative age for LLM temporal reasoning
    # If valid_until exists, show as date range
    valid_until = mem.get("valid_until")
    if abs_date and valid_until:
        end_date = _absolute_date(valid_until)
        date_attr = f' date="{abs_date} ~ {end_date}"' if end_date else f' date="{abs_date}"'
    elif abs_date:
        date_attr = f' date="{abs_date}"'
    else:
        date_attr = ""
    fact_type_attr = (
        f' fact_type="{mem.get("fact_type", "fact")}"'
        if mem.get("fact_type") and mem.get("fact_type") != "fact"
        else ""
    )

    # Status annotation: expired (valid_until in the past) or possibly-outdated (same-key conflict)
    status_attr = ""
    if mem.get("valid_until"):
        try:
            vu = datetime.fromisoformat(str(mem["valid_until"]).replace("Z", "+00:00"))
            if vu < datetime.now(UTC):
                status_attr = ' status="expired"'
        except (ValueError, TypeError):
            pass
    if not status_attr and mem.get("_outdated"):
        status_attr = ' status="possibly-outdated"'

    parts = [
        f'  <memory type="{category}"{date_attr}{fact_type_attr}{status_attr} age="{age_str}" importance="{importance:.1f}">'
    ]
    # P1 Fix: 严格限制每条记忆的最大长度，防止注入过大
    if days_old < 3 and importance > 0.7:
        parts.append(value[:300])  # 限制最新高重要性记忆为 300 字符
    elif days_old < 30:
        parts.append(value[:100])  # 限制近期记忆为 100 字符
    else:
        key = mem.get("key", "")
        parts.append(f"{key}: {value[:30]}... (需使用 search_long_term_memory 工具查看详情)")
    parts.append("</memory>")
    return "".join(parts)


async def get_memories(
    user_id: str,
    category: str | None = None,
    limit: int = 20,
    db: Any = None,
    org_id: str | None = None,
    user_role: str = "employee",
) -> list[dict]:
    """获取用户记忆列表（仅最新版本）

    P1.1: 支持 RBAC 可见性过滤，根据用户角色展示不同级别的记忆。
    """
    client = db or supabase
    if not client:
        return []

    query = client.table("conversation_memories").select("*")

    # P1.1: Apply visibility-based RBAC filtering
    try:
        from .visibility import apply_visibility_filter

        query = apply_visibility_filter(query, user_id, org_id, user_role)
    except Exception:
        # Fallback to simple user filter if visibility column doesn't exist
        query = query.eq("user_id", user_id)

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
    user_role: str = "employee",
) -> list[dict]:
    """搜索相关记忆（混合检索：embedding 语义搜索 + 关键字匹配）

    P0 Security: 强制 org_id 过滤，防止跨租户记忆泄露。
    P1 Enhancement: 优先使用 embedding 向量搜索，关键字匹配作为 fallback。
    P1.1: RBAC 可见性过滤，根据角色控制记忆访问权。
    P2.1: 语义标签预筛，在向量检索前通过标签重叠度预过滤候选集。
    """
    client = db or supabase
    if not client:
        return []

    memories: list[dict] = []

    # ── RRF 融合所需的各路排名列表 ──────────────────────────
    rrf_lists: list[list[dict]] = []  # each sub-list is one retrieval path

    # Pre-compute query embedding once for reuse across semantic search + reranking
    query_embedding = None
    try:
        from app.services.vector_service import vector_service

        query_embedding = await vector_service.embed_text(query)
    except Exception:
        pass

    try:
        # P1 LoCoMo Fix: Expand retrieval to combat context loss (Top-20 → Top-40)
        # When Reranker is offline, we need more candidates to ensure key memories aren't filtered out
        retrieval_multiplier = 4  # Increased from 2
        sem_task = _semantic_search(
            user_id, query, limit * retrieval_multiplier, org_id, client, query_embedding=query_embedding
        )
        entity_task = _entity_precise_search(user_id, query, min(10, limit * 2), org_id, client)
        anchor_task = _user_anchor_search(user_id, min(10, limit * 2), org_id, client)
        keyword_task = _keyword_search(user_id, query, limit * 2, org_id, client)
        results = await asyncio.wait_for(
            asyncio.gather(
                sem_task,
                entity_task,
                anchor_task,
                keyword_task,
                return_exceptions=True,
            ),
            timeout=20.0,
        )

        for r in results:
            if isinstance(r, list) and r:
                rrf_lists.append(r)

        # ── RRF (Reciprocal Rank Fusion) ──────────────────────
        # Score = Σ 1/(k + rank_i) across all lists where the item appears
        _RRF_K = 30  # Optimized RRF constant for sharper ranking
        rrf_scores: dict[str, float] = {}
        id_to_mem: dict[str, dict] = {}

        for ranked_list in rrf_lists:
            for rank, mem in enumerate(ranked_list):
                mid = mem["id"]
                rrf_scores[mid] = rrf_scores.get(mid, 0.0) + 1.0 / (_RRF_K + rank + 1)
                if mid not in id_to_mem:
                    id_to_mem[mid] = mem

        # ── Adaptive Time-Decay + Temporal Boost ─────────────────────────────
        # P0 LoCoMo Fix: Add temporal matching bonus for time-sensitive queries
        from .temporal_normalizer import calculate_temporal_overlap, extract_time_range_from_query

        query_time_range = extract_time_range_from_query(query)
        is_temporal_query = any(kw in query.lower() for kw in ["when", "what time", "什么时候", "何时", "哪天"])

        for mid, mem in id_to_mem.items():
            updated = mem.get("updated_at") or mem.get("created_at") or ""
            days_old = _days_since(updated)
            cat = mem.get("category", "")

            # Adaptive decay: facts and documents stay "fresh" longer
            if cat in ("explicit_memory", "policy", "document", "fact"):
                freshness = 1.0 if days_old <= 90 else 0.8
            elif days_old <= 14:
                freshness = 1.0
            elif days_old <= 60:
                freshness = 1.0 - 0.2 * ((days_old - 14) / 46.0)
            else:
                freshness = max(0.5, 0.8 * (60.0 / max(days_old, 1)))

            # P0: Temporal matching boost (5x multiplier for time-matched memories)
            temporal_boost = 1.0
            if is_temporal_query and query_time_range:
                meta = mem.get("metadata", {})
                temporal_anchors = meta.get("temporal_anchors", [])
                overlap = calculate_temporal_overlap(temporal_anchors, query_time_range)
                if overlap > 0.5:
                    temporal_boost = 5.0  # Stronger boost (was 3.0)

            # Apply decay factor softly (0.8 base + 0.2 freshness variation)
            confidence = float(mem.get("confidence", 1.0) or 1.0)
            rrf_scores[mid] = rrf_scores[mid] * (0.8 + 0.2 * freshness) * confidence * temporal_boost

        # ── P2.1: Semantic tag pre-filtering boost ──────────────────────
        # Boost memories whose semantic_tags overlap with query-extracted tags
        try:
            from .semantic_tags import compute_tag_overlap, extract_query_tags

            q_tags = extract_query_tags(query)
            if q_tags:
                for mid, mem in id_to_mem.items():
                    mem_tags = mem.get("semantic_tags") or mem.get("metadata", {}).get("semantic_tags", [])
                    if mem_tags and isinstance(mem_tags, list):
                        overlap = compute_tag_overlap(q_tags, mem_tags)
                        if overlap > 0:
                            # 1.0 + 0.5 * overlap → max 1.5x boost for perfect tag match
                            rrf_scores[mid] = rrf_scores[mid] * (1.0 + 0.5 * overlap)
        except Exception as e:
            logger.debug(f"[SemanticTag] Tag boost skipped: {e}")

        # ── Embedding-based rerank (lightweight cross-encoder substitute) ──
        # For candidates from non-semantic arms that lack similarity scores,
        # compute cosine similarity with query embedding as a precision signal.
        if query_embedding and len(id_to_mem) > 1:
            try:
                import numpy as np

                q_vec = np.array(query_embedding, dtype=np.float32)
                q_norm = np.linalg.norm(q_vec)
                if q_norm > 0:
                    max_rrf = max(rrf_scores.values()) if rrf_scores else 1.0
                    for mid, mem in id_to_mem.items():
                        mem_emb = mem.get("embedding")
                        if mem_emb and isinstance(mem_emb, list):
                            m_vec = np.array(mem_emb, dtype=np.float32)
                            m_norm = np.linalg.norm(m_vec)
                            cos_sim = float(np.dot(q_vec, m_vec) / (q_norm * m_norm)) if m_norm > 0 else 0.0
                        else:
                            cos_sim = float(mem.get("similarity", 0) or 0)
                        # Blend: 0.6 * normalized_rrf + 0.4 * cosine_similarity
                        norm_rrf = rrf_scores.get(mid, 0) / max_rrf if max_rrf else 0
                        rrf_scores[mid] = 0.6 * norm_rrf + 0.4 * max(cos_sim, 0)
            except Exception as e:
                logger.debug(f"Embedding rerank skipped: {e}")

        # ── Reranker 精排 (cross-encoder level) ──────────────────────
        # Call reranker_service on top-15 candidates for query-doc interaction scoring.
        # Falls back silently to cosine rerank results on failure.
        from app.core.config import settings

        if settings.RERANK_ENABLED and len(id_to_mem) > 3:
            try:
                from app.services.reranker_service import reranker_service

                top_candidates = sorted(
                    id_to_mem.keys(),
                    key=lambda x: rrf_scores.get(x, 0),
                    reverse=True,
                )[:15]
                rerank_docs = []
                for mid in top_candidates:
                    mem = id_to_mem[mid]
                    content = mem.get("value") or mem.get("key", "")
                    rerank_docs.append({"content": content, "id": mid})

                if len(rerank_docs) > 3:
                    rr = await reranker_service.rerank(query, rerank_docs, top_k=limit)
                    for rank, doc in enumerate(rr.documents):
                        mid = doc.get("id")
                        if mid and mid in rrf_scores:
                            rrf_scores[mid] = 1.0 - rank * 0.05
                    logger.debug(
                        "[MemRerank] %d → %d via %s in %.0fms",
                        len(rerank_docs),
                        len(rr.documents),
                        rr.backend_used,
                        rr.latency_ms,
                    )
            except Exception as e:
                logger.debug(f"[MemRerank] Reranker skipped: {e}")

        # Sort by RRF score descending
        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
        memories = [id_to_mem[mid] for mid in sorted_ids]

    except TimeoutError:
        logger.warning(f"[Memory] Parallel search timeout for user {user_id}")
    except Exception as e:
        logger.warning(f"Memory search failed: {e}")

    # P1: Fire-and-forget DB updates in a separate task group to avoid blocking retrieval
    async def _bg_updates(mems_to_update):
        now = datetime.now(UTC).isoformat()
        update_tasks = []
        for mem in mems_to_update:
            try:
                current_importance = float(mem.get("importance", 0.5) or 0.5)
                access_count = int(mem.get("access_count", 0) or 0)
                delta = 0.05 / (1 + access_count * 0.3)
                new_importance = min(current_importance + delta, 1.0)
                update_tasks.append(
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
            except Exception:
                pass
        if update_tasks:
            await asyncio.gather(*update_tasks, return_exceptions=True)

    if memories:
        asyncio.create_task(_bg_updates(memories[:limit]))

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

    # P1 LoCoMo Fix: Temporal reranking for time-sensitive queries
    from .temporal_normalizer import rerank_by_temporal_relevance

    memories = rerank_by_temporal_relevance(query, memories, boost_factor=2.0)

    memories = mmr_rerank(memories, limit)

    # P0: 最低相关性阈值过滤，防止冷旧记忆污染上下文
    _MIN_DECAY_SCORE = 0.15
    if memories:
        pre_count = len(memories)
        memories = [m for m in memories if _weighted_score(m) >= _MIN_DECAY_SCORE]
        if len(memories) < pre_count:
            logger.info(f"[Memory] Relevance filter: {pre_count} → {len(memories)}")

    # Feature 3: KG Spreading Activation — 脉冲式激活扩散
    # P1: Skip during heavy benchmarks to prevent DB connection pool exhaustion
    from app.core.config import settings

    if os.environ.get("RAG_BENCHMARK_MODE") != "1":
        try:
            expanded = await _spreading_activation(memories[:5], user_id, db=client)
            if expanded:
                seen_ids = {m["id"] for m in memories}
                for em in expanded:
                    if em["id"] not in seen_ids:
                        memories.append(em)
        except Exception as e:
            logger.debug(f"Spreading activation skipped: {e}")
    else:
        logger.info("[Memory] Skipping spreading activation (BENCHMARK_MODE)")

    return memories


async def _semantic_search(
    user_id: str, query: str, limit: int, org_id: str | None, client, *, query_embedding: list[float] | None = None
) -> list[dict]:
    """Embedding-based semantic search on memories using pgvector.
    P1: 优先使用 search_memories_hybrid（向量+时间衰减），
    降级到 search_memories_by_embedding。

    注: hybrid RPC 的 FTS 分支已移除 (20260323 迁移)，因为 Supabase 'simple'
    分词器对中文无效。中文关键词搜索由 _keyword_search (jieba+ILIKE) 负责。
    """
    try:
        if not query_embedding:
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

        print(f"DEBUG SEMANTIC: Calling search_memories_by_embedding with {list(params.keys())}")
        result = await client.rpc("search_memories_by_embedding", params).execute()
        return result.data or []
    except Exception as e:
        logger.debug(f"Semantic memory search unavailable, falling back to keyword: {e}")
        return []


async def _keyword_search(user_id: str, query: str, limit: int, org_id: str | None, client) -> list[dict]:
    """Keyword-based fallback search using ILIKE with Chinese tokenization.
    Optimized for bulk querying to reduce DB roundtrips.
    """
    terms = _extract_search_terms(query)
    if not terms:
        terms = [query] if len(query) > 1 else []

    if not terms:
        return []

    # Build a single bulk OR query: "key.ilike.%term1%,value.ilike.%term1%,key.ilike.%term2%,..."
    # Limit to first 4 terms to keep query string reasonable
    or_parts = []
    for t in terms[:4]:
        or_parts.append(f"key.ilike.%{t}%,value.ilike.%{t}%")

    or_filter = ",".join(or_parts)

    try:
        q = (
            client.table("conversation_memories")
            .select("*")
            .eq("user_id", user_id)
            .is_("superseded_by", "null")
            .or_(or_filter)
            .limit(limit)
        )
        if org_id:
            q = q.eq("organization_id", org_id)

        result = await q.execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Keyword search failed: {e}")
        return []


# ── 实体精确搜索（双路并行的第二路）─────────────────────────
_ENTITY_PATTERNS = [
    re.compile(r"([\u4e00-\u9fff]{2,4}(?:总|经理|老师|同学|先生|女士|老板|主管|领导|组长))"),
    re.compile(r"([\u4e00-\u9fff]{2,4})(?:说|提到|要求|反馈|告诉|认为|觉得)"),
    re.compile(r"(?:关于|有关|涉及)([\u4e00-\u9fff\w]{2,10}?)(?:的|项目|方案|合同|订单)"),
    # English: multi-word proper names like "Kanoa Manu", "John Smith"
    re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"),
    # English: single capitalized word (likely a name) adjacent to possessive/verb
    re.compile(r"\b([A-Z][a-z]{2,})'s\b"),
]


async def _entity_precise_search(
    user_id: str,
    query: str,
    limit: int,
    org_id: str | None,
    client,
) -> list[dict]:
    """Extract entities and perform bulk ILIKE search.
    Optimized to avoid looping DB queries.
    """
    entities: list[str] = []
    for pat in _ENTITY_PATTERNS:
        entities.extend(pat.findall(query))
    entities = list(dict.fromkeys(e for e in entities if len(e) >= 2))

    extra_terms = _extract_search_terms(query)
    for t in extra_terms:
        if t not in entities and (t[0].isupper() or len(t) >= 4):
            entities.append(t)

    if not entities:
        return []

    # Bulk OR query for entities
    or_parts = []
    for e in entities[:5]:
        or_parts.append(f"key.ilike.%{e}%,value.ilike.%{e}%")

    try:
        q = (
            client.table("conversation_memories")
            .select("*")
            .eq("user_id", user_id)
            .is_("superseded_by", "null")
            .or_(",".join(or_parts))
            .limit(limit)
        )
        if org_id:
            q = q.eq("organization_id", org_id)

        result = await q.execute()
        memories = result.data or []

        # Phase 2: Combo search (only if small results and multiple entities)
        # We keep this limited to 1 extra query if needed
        if len(memories) < limit and len(entities) >= 2:
            e1, e2 = entities[0], entities[1]
            combo_q = (
                client.table("conversation_memories")
                .select("*")
                .eq("user_id", user_id)
                .is_("superseded_by", "null")
                .ilike("value", f"%{e1}%")
                .ilike("value", f"%{e2}%")
                .limit(3)
            )
            if org_id:
                combo_q = combo_q.eq("organization_id", org_id)
            combo_res = await combo_q.execute()
            if combo_res.data:
                seen_ids = {m["id"] for m in memories}
                for item in combo_res.data:
                    if item["id"] not in seen_ids:
                        memories.append(item)

        return memories[:limit]
    except Exception:
        return memories[:limit] if "memories" in locals() else []


async def _user_anchor_search(
    user_id: str,
    limit: int,
    org_id: str | None,
    client,
) -> list[dict]:
    """无条件拉取用户最重要的 TOP-N 记忆（不依赖查询语义）。

    解决语义向量搜索在隐式关联场景下的盲区：
    即使用户查询与记忆文本的向量距离大，高重要性记忆仍应被召回。
    """
    try:
        q = (
            client.table("conversation_memories")
            .select("*")
            .eq("user_id", user_id)
            .is_("superseded_by", "null")
            .order("importance", desc=True)
            .limit(limit)
        )
        if org_id:
            q = q.eq("organization_id", org_id)
        result = await q.execute()
        return result.data or []
    except Exception as e:
        logger.error(f"User anchor search failed: {e}")
        return []


async def _spreading_activation(
    seed_memories: list[dict],
    user_id: str,
    max_hops: int = 2,
    decay_factor: float = 0.5,
    activation_threshold: float = 0.15,
    max_total: int = 8,
    db: Any = None,
) -> list[dict]:
    """KG Spreading Activation — 脉冲式激活扩散检索。

    从种子记忆出发，沿 connections 网络传播激活信号：
    - 每一跳激活分数乘以 decay_factor × connection strength
    - 激活分数低于 activation_threshold 的节点停止传播
    - 最终按累积激活分数排序返回 top-N 扩散记忆

    这比简单的 1-hop/2-hop 扩展更精准：
    - 多路径汇聚的节点获得更高分数
    - 弱连接自然被过滤掉
    """
    client = db or supabase
    if not client or not seed_memories:
        return []

    seed_ids = {m["id"] for m in seed_memories}

    # activation_map: node_id -> cumulative activation score

    # Initialize seeds with their importance as initial activation
    frontier: list[tuple[str, float]] = []  # (memory_id, activation_score)
    for mem in seed_memories:
        imp = float(mem.get("importance", 0.5) or 0.5)
        connections = mem.get("connections", [])
        if not isinstance(connections, list):
            continue
        for conn in connections:
            target_id = conn.get("memory_id")
            strength = float(conn.get("strength", 0.5) or 0.5)
            if target_id and target_id not in seed_ids:
                # Hindsight-inspired: causal links get 2x boost, contradicts 1.5x
                relation = conn.get("relation", "supplements")
                link_mult = 2.0 if relation == "causal" else (1.5 if relation == "contradicts" else 1.0)
                activation = imp * strength * decay_factor * link_mult
                if activation >= activation_threshold:
                    frontier.append((target_id, activation))

    # BFS-style propagation
    visited: set[str] = set(seed_ids)
    all_activated: dict[str, float] = {}

    for _hop in range(max_hops):
        if not frontier:
            break

        # Accumulate activations for this frontier
        for mid, score in frontier:
            all_activated[mid] = all_activated.get(mid, 0.0) + score

        # Fetch frontier memories to get their connections for next hop
        frontier_ids = list({mid for mid, _ in frontier if mid not in visited})
        if not frontier_ids:
            break

        try:
            result = await (
                client.table("conversation_memories")
                .select("id, connections, importance")
                .eq("user_id", user_id)
                .in_("id", frontier_ids[:20])
                .execute()
            )
            fetched = {m["id"]: m for m in (result.data or [])}
        except Exception:
            break

        next_frontier: list[tuple[str, float]] = []
        for mid, score in frontier:
            visited.add(mid)
            mem_data = fetched.get(mid)
            if not mem_data:
                continue
            connections = mem_data.get("connections", [])
            if not isinstance(connections, list):
                continue
            for conn in connections:
                target_id = conn.get("memory_id")
                strength = float(conn.get("strength", 0.5) or 0.5)
                if target_id and target_id not in visited and target_id not in seed_ids:
                    relation = conn.get("relation", "supplements")
                    link_mult = 2.0 if relation == "causal" else (1.5 if relation == "contradicts" else 1.0)
                    propagated = score * strength * decay_factor * link_mult
                    if propagated >= activation_threshold:
                        next_frontier.append((target_id, propagated))

        frontier = next_frontier

    if not all_activated:
        return []

    # Sort by activation score, fetch top memories
    sorted_activated = sorted(all_activated.items(), key=lambda x: x[1], reverse=True)
    top_ids = [mid for mid, _ in sorted_activated[:max_total]]

    try:
        result = await (
            client.table("conversation_memories").select("*").eq("user_id", user_id).in_("id", top_ids).execute()
        )
        expanded = result.data or []
        # Attach activation score for downstream ranking
        for mem in expanded:
            mem["_activation_score"] = all_activated.get(mem["id"], 0)
        # Sort by activation score
        expanded.sort(key=lambda m: m.get("_activation_score", 0), reverse=True)
        return expanded
    except Exception as e:
        logger.error(f"Spreading activation fetch failed: {e}")
        return []


async def _expand_top_connections(
    memories: list[dict],
    user_id: str,
    limit: int = 3,
    max_total: int = 10,
    hop2_strength: float = 0.7,
    hop2_threshold: float = 0.8,
    hop2_max: int = 5,
    db: Any = None,
) -> list[dict]:
    """1-hop + 2-hop expansion: fetch connected memories for top results.

    2-hop is only attempted for 1-hop connections with strength > hop2_strength,
    and uses a stricter threshold (hop2_threshold) for the second hop.
    Total results are capped at max_total (shared between 1-hop and 2-hop).
    """
    client = db or supabase
    if not client:
        return []

    seen_ids = {m["id"] for m in memories}
    hop1_ids: set[str] = set()
    hop1_strong_ids: set[str] = set()  # High-strength connections eligible for 2-hop

    # --- 1-hop: collect connected memory IDs ---
    for mem in memories[:limit]:
        connections = mem.get("connections", [])
        if not isinstance(connections, list):
            continue
        for conn in connections:
            mid = conn.get("memory_id")
            if mid and mid not in seen_ids and mid not in hop1_ids:
                hop1_ids.add(mid)
                strength = float(conn.get("strength", 0))
                if strength > hop2_strength:
                    hop1_strong_ids.add(mid)

    if not hop1_ids:
        return []

    # --- Fetch 1-hop memories ---
    try:
        result = (
            await client.table("conversation_memories")
            .select("*")
            .eq("user_id", user_id)
            .in_("id", list(hop1_ids)[:max_total])
            .execute()
        )
        hop1_memories = result.data or []
    except Exception as e:
        logger.error(f"Connection expansion (1-hop) failed: {e}")
        return []

    # --- 2-hop: expand high-strength 1-hop results ---
    remaining_quota = max_total - len(hop1_memories)
    if remaining_quota > 0 and hop1_strong_ids:
        all_known = seen_ids | hop1_ids
        hop2_ids: set[str] = set()
        hop2_limit = min(hop2_max, remaining_quota)

        for mem in hop1_memories:
            if mem["id"] not in hop1_strong_ids:
                continue
            connections = mem.get("connections", [])
            if not isinstance(connections, list):
                continue
            for conn in connections:
                mid = conn.get("memory_id")
                strength = float(conn.get("strength", 0))
                if mid and mid not in all_known and mid not in hop2_ids and strength > hop2_threshold:
                    hop2_ids.add(mid)
                    if len(hop2_ids) >= hop2_limit:
                        break
            if len(hop2_ids) >= hop2_limit:
                break

        if hop2_ids:
            try:
                result2 = (
                    await client.table("conversation_memories")
                    .select("*")
                    .eq("user_id", user_id)
                    .in_("id", list(hop2_ids))
                    .execute()
                )
                hop1_memories.extend(result2.data or [])
            except Exception as e:
                logger.error(f"Connection expansion (2-hop) failed: {e}")

    return hop1_memories[:max_total]


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
        logger.error(f"Consolidation search failed: {e}")
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
    client = db or supabase

    # 0-pre) 注入用户画像 observation（如果存在）
    try:
        if client:
            obs_result = await (
                client.table("memory_consolidations")
                .select("content")
                .eq("user_id", user_id)
                .eq("insight_type", "observation")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if obs_result.data:
                obs_content = obs_result.data[0].get("content", "")
                if obs_content:
                    context_parts.append(f"<observation>\n{obs_content}\n</observation>")
    except Exception as e:
        logger.debug(f"Observation injection skipped: {e}")

    # Analyze complexity to optimize retrieval caps (P2: Intent-Aware Memory Router)
    explicit_limit = 5
    relevant_limit = 5
    consolidated_limit = 3

    # P0 LoCoMo Fix: 检测列表/计数类查询，自动提升检索量和多样性
    # 解决 "Where has X been?" / "What types of Y?" 类问题只返回部分记忆的问题
    _LIST_PATTERNS = re.compile(
        r"(how many|what (?:types?|kinds?|all)|where (?:has|have|did)|"
        r"list|哪些|多少|几个|几次|都有|所有|有哪|列举|分别)",
        re.IGNORECASE,
    )
    is_list_query = bool(_LIST_PATTERNS.search(current_query)) if current_query else False
    if is_list_query:
        relevant_limit = max(relevant_limit, 15)  # Force higher recall for list queries
        consolidated_limit = max(consolidated_limit, 5)

    # Detect recency-oriented queries — boost recent memories when user asks about "lately"
    _RECENCY_PATTERNS = re.compile(
        r"(最近|近期|刚才|刚刚|今天|昨天|这几天|这周|上周|recently|lately|just now|today|yesterday|this week|last week)",
        re.IGNORECASE,
    )
    is_recency_query = bool(_RECENCY_PATTERNS.search(current_query)) if current_query else False

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

            # P0 LoCoMo Fix: 对列表查询启用日期多样性过滤
            # 确保返回的记忆来自不同日期/session，避免同 session 记忆挤占配额
            if is_list_query and len(new_relevant) > 5:
                date_seen: dict[str, list[dict]] = {}
                for m in new_relevant:
                    d = _absolute_date(m.get("updated_at") or m.get("created_at") or "")
                    date_key = d or "unknown"
                    date_seen.setdefault(date_key, []).append(m)
                # Round-robin pick from each date to ensure cross-session diversity
                diverse: list[dict] = []
                max_per_date = max(2, relevant_limit // max(len(date_seen), 1))
                for date_key in sorted(date_seen.keys()):
                    diverse.extend(date_seen[date_key][:max_per_date])
                new_relevant = diverse[:relevant_limit]

            # Recency-first reranking: when user asks about recent events,
            # sort memories so that last-7-days items come first
            if is_recency_query and len(new_relevant) > 1:
                datetime.now(UTC)

                def _recency_tier(m: dict) -> int:
                    ts = m.get("valid_from") or m.get("updated_at") or m.get("created_at") or ""
                    d = _days_since(ts) if ts else 999
                    if d <= 7:
                        return 0  # recent — top tier
                    if d <= 30:
                        return 1  # warm
                    return 2  # older

                new_relevant.sort(key=_recency_tier)

            if new_relevant:
                # Same-key conflict detection: mark older entries as possibly-outdated
                key_groups: dict[str, list[dict]] = {}
                for m in new_relevant:
                    k = m.get("key", "")
                    if k:
                        key_groups.setdefault(k, []).append(m)
                for _k, group in key_groups.items():
                    if len(group) > 1:
                        group.sort(
                            key=lambda m: m.get("valid_from") or m.get("updated_at") or "",
                            reverse=True,
                        )
                        for old_mem in group[1:]:
                            old_mem["_outdated"] = True

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

    # P2 LoCoMo Fix: 反 RLHF 偏见指令 — 防止 AI 美化用户的负面体验
    if result_parts:
        result_parts.append(
            "<memory-instructions>\n"
            "When answering questions about the user based on their memories:\n"
            "- Respect negative sentiments faithfully. If a memory says the user had a bad experience, "
            "do NOT speculate they would want to repeat it.\n"
            '- Use the exact dates from memory date attributes (date="YYYY-MM-DD") for temporal reasoning. '
            "Do NOT substitute the current system date for historical events.\n"
            "- For list/enumeration questions, gather evidence from ALL available memories across different dates, "
            "not just the most relevant single memory.\n"
            "</memory-instructions>"
        )

    # P1 Fix: 限制总记忆上下文大小，防止注入过大
    final_context = "\n\n".join(result_parts)
    MAX_CONTEXT_SIZE = 30000  # 30KB 限制
    if len(final_context) > MAX_CONTEXT_SIZE:
        logger.warning(f"[MemoryContext] Truncated from {len(final_context)} to {MAX_CONTEXT_SIZE} chars")
        final_context = (
            final_context[:MAX_CONTEXT_SIZE] + "\n\n... (更多记忆已省略，使用 search_long_term_memory 工具查看)"
        )

    return final_context


# ── Tiered Memory Retrieval (L0-L3 Stack) ──────────────────────────────
# L0 = user identity (handled in memory.py via users table, always in system_prompt)
# L1 = critical facts / directives / anti-patterns (~120 tokens, always injected)
# L2 = query-relevant contextual memories (~300 tokens, budget-aware)
# L3 = on-demand deep search (existing search_long_term_memory tool)


async def get_l1_critical_facts(
    user_id: str,
    db: Any = None,
) -> str:
    """L1: 高重要性记忆 + 用户指令 + 纠正记录。~120 tokens，始终注入。

    Returns a compact <constraints> block with the user's most critical
    directives and anti-patterns that must never be truncated.
    """
    client = db or supabase
    if not client:
        return ""

    lines: list[str] = []

    try:
        # 1) High-importance directives (importance >= 0.85, any category)
        directive_res = await (
            client.table("conversation_memories")
            .select("value, enriched_value, importance, category")
            .eq("user_id", user_id)
            .gte("importance", 0.85)
            .is_("superseded_by", "null")
            .order("importance", desc=True)
            .limit(5)
            .execute()
        )
        for m in directive_res.data or []:
            val = m.get("enriched_value") or m.get("value", "")
            if val:
                lines.append(f"  - {val[:120]}")

        # 2) Anti-patterns (user corrections — always high signal)
        anti_res = await (
            client.table("conversation_memories")
            .select("value, enriched_value")
            .eq("user_id", user_id)
            .eq("category", "anti_pattern")
            .is_("superseded_by", "null")
            .order("updated_at", desc=True)
            .limit(3)
            .execute()
        )
        seen = {l for l in lines}  # dedup against directives
        for m in anti_res.data or []:
            val = m.get("enriched_value") or m.get("value", "")
            candidate = f"  - [纠正] {val[:100]}"
            if val and candidate not in seen:
                lines.append(candidate)
    except Exception as e:
        logger.debug(f"[L1] Critical facts retrieval failed: {e}")

    if not lines:
        return ""

    return "<constraints>\n" + "\n".join(lines) + "\n</constraints>"


async def get_l2_contextual(
    user_id: str,
    query: str,
    complexity: str | None = None,
    db: Any = None,
) -> str:
    """L2: 查询相关记忆，预算感知 ~300 tokens。

    Performs semantic search and consolidation lookup, excluding items
    already covered by L1 (high-importance directives, anti-patterns).
    """
    if not query or len(query) < 2:
        return ""

    # Adaptive limits based on complexity
    relevant_limit = 5
    consolidated_limit = 3
    if complexity:
        _c = str(complexity).upper()
        if _c in ("CRITICAL", "COMPLEX"):
            relevant_limit = 8
            consolidated_limit = 4
        elif _c == "SIMPLE":
            relevant_limit = 3

    parts: list[str] = []

    try:
        # Semantic search across all categories
        relevant = await search_memories(
            user_id=user_id,
            query=query,
            limit=relevant_limit,
            db=db,
        )
        if relevant:
            # Exclude L1 items: high-importance directives and anti-patterns
            filtered = [
                m for m in relevant if not ((m.get("importance") or 0) >= 0.85 or m.get("category") == "anti_pattern")
            ]
            for m in filtered:
                parts.append(_format_by_temperature(m))
    except Exception as e:
        logger.debug(f"[L2] Contextual search failed: {e}")

    # Consolidated insights
    try:
        consolidations = await search_consolidations(
            user_id=user_id,
            query=query,
            limit=consolidated_limit,
            db=db,
        )
        if consolidations:
            for c in consolidations:
                parts.append(
                    f'  <insight type="{c["insight_type"]}" ' f'title="{c["title"]}">{c["content"][:150]}</insight>'
                )
    except Exception as e:
        logger.debug(f"[L2] Consolidation search failed: {e}")

    if not parts:
        return ""

    context = "<user-memories>\n" + "\n".join(parts) + "\n</user-memories>"

    # Budget cap: ~300 tokens ≈ 900 chars
    _L2_MAX_CHARS = 900
    if len(context) > _L2_MAX_CHARS:
        context = context[:_L2_MAX_CHARS] + "\n... (更多记忆可用 search_long_term_memory 工具查看)"

    return context
