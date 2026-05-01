"""
Semantic Cache Service - Cache AI responses for similar queries
"""

import contextlib
import hashlib
import logging
import os
import re
from datetime import UTC, datetime, timedelta

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.database import supabase

logger = logging.getLogger(__name__)

# Default TTL for cache entries: 24 hours
DEFAULT_CACHE_TTL_HOURS = 24
_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# Redis hot-cache TTL: 1 hour (most repeated queries happen within short windows)
_REDIS_HOT_CACHE_TTL = 3600

# Queries matching these patterns should bypass cache entirely
# (creative writing, long-form content — users expect unique output each time)
_CACHE_BYPASS_RE = re.compile(
    r"\d{3,}\s*字|千字|万字|长文|软文|推广文|写一[篇份]"
    r"|方案书|策划案|创作|编写.{0,10}报告"
)

# Error/rejection prefixes — never cache these responses
_ERROR_PREFIXES = ("❌", "⚠️", "抱歉", "对不起", "很抱歉", "Error")

# Intermediate state patterns — never cache these (tool confirmations, pending actions)
# These represent incomplete interactions that require user confirmation before execution
_INTERMEDIATE_RE = re.compile(
    r"需要您的确认|需要确认|请确认后再执行|不可逆操作|确认后才能执行"
    r"|confirmation_message|is_irreversible"
)


def _redis_cache_key(query_hash: str, user_id: str) -> str:
    """Build a namespaced Redis key for hot cache."""
    return f"sem_cache:{user_id}:{query_hash}"


class SemanticCacheService:
    """
    P2 Optimization (Area 9/6): Semantic Caching for AI responses.
    Reduces LLM API calls and latency for repetitive or highly similar queries.
    """

    def __init__(self):
        self.threshold = (
            settings.SEMANTIC_CACHE_THRESHOLD
            if hasattr(settings, "SEMANTIC_CACHE_THRESHOLD")
            else 0.95
        )
        self.ttl_hours = (
            settings.SEMANTIC_CACHE_TTL_HOURS
            if hasattr(settings, "SEMANTIC_CACHE_TTL_HOURS")
            else DEFAULT_CACHE_TTL_HOURS
        )
        # Initialize OpenAI client for embeddings
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=(
                settings.AI_BASE_URL.split("/chat/completions")[0].rstrip("/")
                if settings.AI_BASE_URL
                else None
            ),
        )
        # Embedding model (will be dynamically resolved on first use)
        self._embedding_model = _DEFAULT_EMBEDDING_MODEL
        self._embedding_resolved = False
        # Redis client (lazy init)
        self._redis = None
        self._redis_init_attempted = False
        # ── Cache stats (in-memory counters for observability) ──
        self._hits = 0
        self._misses = 0

    async def _resolve_embedding_model(self):
        """Resolve embedding model via gateway (cached after first call)."""
        if self._embedding_resolved:
            return
        try:
            from app.services.llm_helpers import resolve_embedding_config

            config = await resolve_embedding_config()
            self._embedding_model = config.get("model", _DEFAULT_EMBEDDING_MODEL)
            if config.get("api_key"):
                self.openai_client = AsyncOpenAI(
                    api_key=config["api_key"],
                    base_url=config.get("base_url"),
                )
        except Exception as e:
            logger.error(
                f"Semantic cache embedding resolution failed, using default: {e}"
            )
        self._embedding_resolved = True

    async def _get_redis(self):
        """Lazy-init async Redis client for hot cache layer."""
        if self._redis_init_attempted:
            return self._redis
        self._redis_init_attempted = True
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return None
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            await self._redis.ping()
            logger.info("[SemanticCache] Redis hot-cache layer connected")
        except Exception as e:
            logger.debug(f"[SemanticCache] Redis unavailable, hot-cache disabled: {e}")
            self._redis = None
        return self._redis

    def should_use_cache(self, query: str) -> bool:
        """判断该查询是否应使用缓存。

        创意写作/长文生成类请求返回 False，因为：
        1. 用户每次期望不同的创意输出
        2. 这类请求的旧缓存很可能质量不足
        """
        if _CACHE_BYPASS_RE.search(query):
            logger.info("[Cache] Bypass: creative/long-form query detected")
            return False
        return True

    def _passes_quality_gate(self, query: str, response_text: str) -> bool:
        """写入前质量检查，防止缓存低质量/错误回复。

        借鉴 Krites 的质量验证思想，在写入侧过滤：
        - 创意写作类请求（每次应生成不同内容）
        - 错误/拒绝回复
        - 回复长度与请求预期严重不符
        - 长查询配短回复（可疑的不完整回复）
        """
        # Rule 1: 不缓存创意写作类请求的回复
        if not self.should_use_cache(query):
            return False

        # Rule 2: 不缓存错误/拒绝回复
        stripped = response_text.strip()
        if any(stripped.startswith(p) for p in _ERROR_PREFIXES):
            return False

        # Rule 2.5: 不缓存中间状态（工具确认请求、不可逆操作提示）
        # 这些是待用户确认的交互中间态，缓存会导致永远无法执行
        if _INTERMEDIATE_RE.search(response_text):
            logger.info("[Cache] Bypass: intermediate state (tool confirmation)")
            return False

        # Rule 3: 字数要求 vs 实际回复长度
        #   "写3000字" → 提取 3000，回复 < 900字(30%) → 拒绝
        m = re.search(r"(\d{3,})\s*字", query)
        if m:
            expected = int(m.group(1))
            if len(response_text) < expected * 0.3:
                return False

        # Rule 4: 长查询(>100字) 配 短回复(<50字) → 可疑的不完整回复
        return not (len(query) > 100 and len(response_text) < 50)

    @staticmethod
    def _query_hash(query: str) -> str:
        """Compute a deterministic hash for exact-match lookup."""
        return hashlib.sha256(query.strip().encode("utf-8")).hexdigest()

    def _ttl_cutoff(self) -> str:
        """Return an ISO-8601 timestamp for the TTL boundary."""
        cutoff = datetime.now(UTC) - timedelta(hours=self.ttl_hours)
        return cutoff.isoformat()

    @staticmethod
    def _is_stale_response(text: str) -> bool:
        """Check if cached text is a stale intermediate state that should not be served."""
        return bool(_INTERMEDIATE_RE.search(text))

    async def get_cache(self, query: str, user_id: str) -> str | None:
        """
        Check if a similar query exists in the cache.

        Lookup order:
        1. Query classification check (bypass creative/long-form queries)
        2. Redis hot-cache (exact hash, fastest — ~1ms)
        3. DB exact hash match (fast, no embedding needed)
        4. Semantic similarity via vector search (requires embedding)

        Only entries within the TTL window are considered.
        Returns the cached response if found, otherwise None.
        """
        from app.core.ai_metrics import record_cache_hit, record_cache_miss

        if not supabase or not settings.OPENAI_API_KEY:
            return None

        # Classification-aware bypass
        if not self.should_use_cache(query):
            return None

        cutoff = self._ttl_cutoff()
        query_hash = self._query_hash(query)

        try:
            # --- Fastest path: Redis hot-cache (exact hash) ---
            r = await self._get_redis()
            if r:
                try:
                    cached_val = await r.get(_redis_cache_key(query_hash, user_id))
                    if cached_val:
                        if self._is_stale_response(cached_val):
                            logger.info(
                                "[Cache] Skipping stale intermediate state from Redis"
                            )
                        else:
                            logger.info(
                                f"Semantic Cache Redis-Hit: query='{query[:30]}...'"
                            )
                            record_cache_hit()
                            self._hits += 1
                            return cached_val
                except Exception:
                    pass  # Redis failure is non-fatal

            # --- Fast path: exact hash match in DB (skip embedding generation) ---
            hash_res = (
                await supabase.table("semantic_cache")
                .select("id, response_text")
                .eq("query_hash", query_hash)
                .eq("user_id", user_id)
                .gt("created_at", cutoff)
                .limit(1)
                .maybe_single()
                .execute()
            )

            if hash_res and hash_res.data:
                resp_text = hash_res.data["response_text"]
                if self._is_stale_response(resp_text):
                    logger.info(
                        "[Cache] Skipping stale intermediate state from DB hash"
                    )
                else:
                    logger.info(f"Semantic Cache Hash-Hit: query='{query[:30]}...'")
                    import asyncio

                    asyncio.create_task(self._update_hit_count(hash_res.data["id"]))
                    # Backfill Redis hot-cache
                    if r:
                        with contextlib.suppress(Exception):
                            await r.setex(
                                _redis_cache_key(query_hash, user_id),
                                _REDIS_HOT_CACHE_TTL,
                                resp_text,
                            )
                    record_cache_hit()
                    self._hits += 1
                    return resp_text

            # --- Slow path: vector similarity search ---
            # 1. Resolve embedding model and get embedding for the new query
            await self._resolve_embedding_model()
            response = await self.openai_client.embeddings.create(
                input=query, model=self._embedding_model, dimensions=1536
            )
            query_embedding = response.data[0].embedding

            # 2. Match in Supabase via RPC (TTL-filtered)
            res = await supabase.rpc(
                "match_semantic_cache",
                {
                    "p_query_embedding": query_embedding,
                    "p_match_threshold": self.threshold,
                    "p_user_id": user_id,
                    "p_created_after": cutoff,
                },
            ).execute()

            if res.data and len(res.data) > 0:
                match = res.data[0]
                resp_text = match["response_text"]
                if self._is_stale_response(resp_text):
                    logger.info(
                        "[Cache] Skipping stale intermediate state from semantic match"
                    )
                else:
                    logger.info(
                        f"Semantic Cache Hit: query='{query[:30]}...', similarity={match['similarity']:.4f}"
                    )

                    # Update hit count (Async, don't wait)
                    import asyncio

                    asyncio.create_task(self._update_hit_count(match["id"]))

                    # Backfill Redis hot-cache for this query hash
                    if r:
                        with contextlib.suppress(Exception):
                            await r.setex(
                                _redis_cache_key(query_hash, user_id),
                                _REDIS_HOT_CACHE_TTL,
                                resp_text,
                            )
                    record_cache_hit()
                    self._hits += 1
                    return resp_text

            record_cache_miss()
            self._misses += 1
            return None
        except Exception as e:
            logger.warning(f"Semantic cache lookup failed: {e}")
            record_cache_miss()
            self._misses += 1
            return None

    async def set_cache(self, query: str, response_text: str, user_id: str):
        """
        Store a new query-response pair in the semantic cache.
        Includes a query_hash column for fast exact-match lookups.
        Applies quality gate to prevent caching low-quality/error responses.
        """
        if not supabase or not settings.OPENAI_API_KEY or not response_text:
            return

        # Quality gate: reject low-quality, error, or creative-writing responses
        if not self._passes_quality_gate(query, response_text):
            logger.info("[Cache] Response failed quality gate, skipping cache write")
            return

        query_hash = self._query_hash(query)

        try:
            # 1. Resolve embedding model and get embedding
            await self._resolve_embedding_model()
            response = await self.openai_client.embeddings.create(
                input=query, model=self._embedding_model, dimensions=1536
            )
            embedding = response.data[0].embedding

            # 2. Get org_id for multi-tenancy
            u_res = (
                await supabase.table("users")
                .select("organization_id")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
            org_id = u_res.data.get("organization_id") if u_res and u_res.data else None

            # 3. Upsert into cache (on conflict with query_hash, update response)
            await (
                supabase.table("semantic_cache")
                .upsert(
                    {
                        "query_text": query,
                        "query_hash": query_hash,
                        "response_text": response_text,
                        "embedding": embedding,
                        "user_id": user_id,
                        "org_id": org_id,
                    },
                    on_conflict="query_hash",
                )
                .execute()
            )

            # 4. Write-through to Redis hot-cache
            r = await self._get_redis()
            if r:
                try:
                    await r.setex(
                        _redis_cache_key(query_hash, user_id),
                        _REDIS_HOT_CACHE_TTL,
                        response_text,
                    )
                except Exception:
                    pass  # Redis failure is non-fatal

        except Exception as e:
            logger.warning(f"Failed to set semantic cache: {e}")

    async def _update_hit_count(self, cache_id: int):
        """Atomically increment the hit counter via RPC.

        Uses a server-side RPC function (``increment_cache_hit``) that
        performs ``SET hit_count = hit_count + 1`` in a single SQL
        statement, avoiding the read-then-write race condition.

        If the RPC is unavailable we log a warning rather than falling
        back to a non-atomic read/write cycle.
        """
        try:
            await supabase.rpc(
                "increment_cache_hit", {"p_cache_id": cache_id}
            ).execute()
        except Exception as e:
            # NOTE: We intentionally do NOT fall back to a read-then-write
            # pattern here because that introduces a race condition when
            # multiple requests hit the same cache entry concurrently.
            # If the RPC function does not exist yet, create it in Supabase:
            #
            #   CREATE OR REPLACE FUNCTION increment_cache_hit(p_cache_id BIGINT)
            #   RETURNS VOID AS $$
            #   BEGIN
            #       UPDATE semantic_cache
            #       SET hit_count = hit_count + 1,
            #           last_hit_at = now()
            #       WHERE id = p_cache_id;
            #   END;
            #   $$ LANGUAGE plpgsql;
            logger.warning(f"Failed to atomically update cache hit count: {e}")

    # ── Event-driven cache invalidation ──

    async def invalidate_by_org(self, org_id: str) -> int:
        """按 org_id 批量删除语义缓存条目（文档/业务数据变更时调用）。

        Returns:
            删除的缓存条目数量
        """
        if not supabase or not org_id:
            return 0

        deleted = 0
        try:
            # 1. 查出该 org 下的缓存条目（需要 user_ids 来清 Redis）
            rows = (
                await supabase.table("semantic_cache")
                .select("id, query_text, user_id")
                .eq("org_id", org_id)
                .execute()
            )
            entries = rows.data or []
            if not entries:
                return 0

            # 2. 批量删除 DB 中该 org 的所有缓存
            await supabase.table("semantic_cache").delete().eq(
                "org_id", org_id
            ).execute()
            deleted = len(entries)

            # 3. 清除 Redis 热缓存
            r = await self._get_redis()
            if r:
                try:
                    keys_to_del = []
                    for entry in entries:
                        uid = entry.get("user_id")
                        qt = entry.get("query_text")
                        if uid and qt:
                            qh = self._query_hash(qt)
                            keys_to_del.append(_redis_cache_key(qh, uid))
                    if keys_to_del:
                        await r.delete(*keys_to_del)
                except Exception:
                    pass  # Redis failure is non-fatal

            logger.info(
                f"[SemanticCache] Invalidated {deleted} entries for org={org_id}"
            )

        except Exception as e:
            logger.warning(f"Failed to invalidate semantic cache for org={org_id}: {e}")

        return deleted

    async def invalidate_by_keywords(self, org_id: str, keywords: list[str]) -> int:
        """按关键词靶向清理：删除 query_text 包含指定关键词的缓存条目。

        用于特定业务实体变更（如合同金额更新）时精准失效相关查询。

        Returns:
            删除的缓存条目数量
        """
        if not supabase or not org_id or not keywords:
            return 0

        deleted = 0
        try:
            # 查出该 org 的缓存并在 Python 端过滤关键词
            rows = (
                await supabase.table("semantic_cache")
                .select("id, query_text, user_id")
                .eq("org_id", org_id)
                .execute()
            )
            entries = rows.data or []
            if not entries:
                return 0

            # 筛选包含任意关键词的条目
            kw_lower = [k.lower() for k in keywords]
            matched = [
                e
                for e in entries
                if any(k in (e.get("query_text") or "").lower() for k in kw_lower)
            ]
            if not matched:
                return 0

            # 逐条删除匹配的缓存
            matched_ids = [e["id"] for e in matched]
            await supabase.table("semantic_cache").delete().in_(
                "id", matched_ids
            ).execute()
            deleted = len(matched_ids)

            # 清除 Redis 热缓存
            r = await self._get_redis()
            if r:
                try:
                    keys_to_del = []
                    for entry in matched:
                        uid = entry.get("user_id")
                        qt = entry.get("query_text")
                        if uid and qt:
                            keys_to_del.append(
                                _redis_cache_key(self._query_hash(qt), uid)
                            )
                    if keys_to_del:
                        await r.delete(*keys_to_del)
                except Exception:
                    pass

            logger.info(
                f"[SemanticCache] Keyword-invalidated {deleted} entries "
                f"for org={org_id}, keywords={keywords[:3]}"
            )

        except Exception as e:
            logger.warning(f"Failed to keyword-invalidate cache: {e}")

        return deleted

    # ── Observability: cache stats ──

    def get_stats(self) -> dict:
        """Return in-memory cache hit/miss stats for monitoring."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": round(self._hits / total, 4) if total > 0 else 0.0,
            "ttl_hours": self.ttl_hours,
            "threshold": self.threshold,
        }

    # ── Maintenance: TTL-based expired entry cleanup ──

    async def cleanup_expired(self) -> int:
        """Delete cache entries older than TTL. Returns count of deleted rows.

        Call periodically (e.g. daily via scheduled task) to prevent unbounded
        table growth. Redis entries expire automatically via TTL.
        """
        if not supabase:
            return 0
        cutoff = self._ttl_cutoff()
        try:
            # Fetch expired entry count first for logging
            rows = (
                await supabase.table("semantic_cache")
                .select("id", count="exact")
                .lt("created_at", cutoff)
                .execute()
            )
            count = rows.count or 0
            if count == 0:
                return 0
            # Delete expired entries
            await supabase.table("semantic_cache").delete().lt(
                "created_at", cutoff
            ).execute()
            logger.info(
                f"[SemanticCache] Cleaned up {count} expired entries (TTL={self.ttl_hours}h)"
            )
            return count
        except Exception as e:
            logger.warning(f"Failed to cleanup expired cache entries: {e}")
            return 0

    # ── Cache warmup ────────────────────────────────────────────────────

    # Common queries that most organizations will ask frequently.
    # Pre-computing embeddings for these avoids cold-start latency.
    _COMMON_QUERY_TEMPLATES = [
        "本月销售额",
        "本月业绩",
        "待审批数量",
        "今日待办",
        "客户总数",
        "本周新增客户",
        "合同到期提醒",
        "本月报销总额",
        "团队业绩排名",
        "项目进度汇总",
    ]

    async def warmup_common_queries(self, org_id: str | None = None):
        """Pre-warm embedding cache for common high-frequency queries.

        This only pre-computes and stores embeddings so that the first real
        query gets a fast vector-similarity lookup instead of a cold miss.
        It does NOT generate fake responses.
        """
        warmed = 0
        for query in self._COMMON_QUERY_TEMPLATES:
            try:
                embedding = await self._get_embedding(query)
                if embedding:
                    cache_key = self._make_cache_key(query, org_id)
                    if self.redis:
                        await self.redis.set(
                            f"emb:{cache_key}", str(embedding), ex=86400
                        )
                    warmed += 1
            except Exception as e:
                logger.debug(f"[SemanticCache] Warmup skip '{query}': {e}")
        org_label = (org_id[:8] + "...") if org_id else "global"
        logger.info(
            f"[SemanticCache] Warmed {warmed}/{len(self._COMMON_QUERY_TEMPLATES)} common queries for org={org_label}"
        )

    async def auto_warmup_from_history(
        self, org_id: str | None = None, min_hits: int = 3
    ):
        """Auto-warm cache from historically popular queries.

        Queries with hit_count >= min_hits are considered popular and worth pre-warming.
        """
        if not org_id:
            return

        try:
            result = (
                await supabase.table("semantic_cache")
                .select("query_text")
                .gte("hit_count", min_hits)
                .eq("org_id", org_id)
                .limit(20)
                .execute()
            )

            if not result.data:
                return

            warmed = 0
            for row in result.data:
                query = row.get("query_text", "")
                if not query:
                    continue
                try:
                    embedding = await self._get_embedding(query)
                    if embedding and self.redis:
                        cache_key = self._make_cache_key(query, org_id)
                        await self.redis.set(
                            f"emb:{cache_key}", str(embedding), ex=86400
                        )
                        warmed += 1
                except Exception:
                    pass

            logger.info(
                f"[SemanticCache] Auto-warmed {warmed} popular queries (min_hits={min_hits}) for org={org_id[:8]}..."
            )
        except Exception as e:
            logger.warning(f"[SemanticCache] Auto-warmup failed: {e}")


semantic_cache_service = SemanticCacheService()
