"""
Semantic Cache Service - Cache AI responses for similar queries
"""

import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.database import supabase

logger = logging.getLogger(__name__)

# Default TTL for cache entries: 24 hours
DEFAULT_CACHE_TTL_HOURS = 24
_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# Queries matching these patterns should bypass cache entirely
# (creative writing, long-form content — users expect unique output each time)
_CACHE_BYPASS_RE = re.compile(
    r"\d{3,}\s*字|千字|万字|长文|软文|推广文|写一[篇份]"
    r"|方案书|策划案|创作|编写.{0,10}报告"
)

# Error/rejection prefixes — never cache these responses
_ERROR_PREFIXES = ("❌", "⚠️", "抱歉", "对不起", "很抱歉", "Error")


class SemanticCacheService:
    """
    P2 Optimization (Area 9/6): Semantic Caching for AI responses.
    Reduces LLM API calls and latency for repetitive or highly similar queries.
    """

    def __init__(self):
        self.threshold = settings.SEMANTIC_CACHE_THRESHOLD if hasattr(settings, "SEMANTIC_CACHE_THRESHOLD") else 0.95
        self.ttl_hours = (
            settings.SEMANTIC_CACHE_TTL_HOURS
            if hasattr(settings, "SEMANTIC_CACHE_TTL_HOURS")
            else DEFAULT_CACHE_TTL_HOURS
        )
        # Initialize OpenAI client for embeddings
        self.openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=(settings.AI_BASE_URL.split("/chat/completions")[0].rstrip("/") if settings.AI_BASE_URL else None),
        )
        # Embedding model (will be dynamically resolved on first use)
        self._embedding_model = _DEFAULT_EMBEDDING_MODEL
        self._embedding_resolved = False

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
            logger.debug(f"Semantic cache embedding resolution failed, using default: {e}")
        self._embedding_resolved = True

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

        # Rule 3: 字数要求 vs 实际回复长度
        #   "写3000字" → 提取 3000，回复 < 900字(30%) → 拒绝
        m = re.search(r"(\d{3,})\s*字", query)
        if m:
            expected = int(m.group(1))
            if len(response_text) < expected * 0.3:
                return False

        # Rule 4: 长查询(>100字) 配 短回复(<50字) → 可疑的不完整回复
        if len(query) > 100 and len(response_text) < 50:
            return False

        return True

    @staticmethod
    def _query_hash(query: str) -> str:
        """Compute a deterministic hash for exact-match lookup."""
        return hashlib.sha256(query.strip().encode("utf-8")).hexdigest()

    def _ttl_cutoff(self) -> str:
        """Return an ISO-8601 timestamp for the TTL boundary."""
        cutoff = datetime.now(UTC) - timedelta(hours=self.ttl_hours)
        return cutoff.isoformat()

    async def get_cache(self, query: str, user_id: str) -> str | None:
        """
        Check if a similar query exists in the cache.

        Lookup order:
        1. Query classification check (bypass creative/long-form queries)
        2. Exact hash match (fast, no embedding needed)
        3. Semantic similarity via vector search (requires embedding)

        Only entries within the TTL window are considered.
        Returns the cached response if found, otherwise None.
        """
        if not supabase or not settings.OPENAI_API_KEY:
            return None

        # Classification-aware bypass
        if not self.should_use_cache(query):
            return None

        cutoff = self._ttl_cutoff()
        query_hash = self._query_hash(query)

        try:
            # --- Fast path: exact hash match (skip embedding generation) ---
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
                logger.info(f"Semantic Cache Hash-Hit: query='{query[:30]}...'")
                import asyncio

                asyncio.create_task(self._update_hit_count(hash_res.data["id"]))
                return hash_res.data["response_text"]

            # --- Slow path: vector similarity search ---
            # 1. Resolve embedding model and get embedding for the new query
            await self._resolve_embedding_model()
            response = await self.openai_client.embeddings.create(input=query, model=self._embedding_model, dimensions=1536)
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
                logger.info(f"Semantic Cache Hit: query='{query[:30]}...', similarity={match['similarity']:.4f}")

                # Update hit count (Async, don't wait)
                import asyncio

                asyncio.create_task(self._update_hit_count(match["id"]))

                return match["response_text"]

            return None
        except Exception as e:
            logger.warning(f"Semantic cache lookup failed: {e}")
            return None

    async def set_cache(self, query: str, response_text: str, user_id: str):
        """
        Store a new query-response pair in the semantic cache.
        Includes a query_hash column for fast exact-match lookups.
        Applies quality gate to prevent caching low-quality/error responses.
        """
        # NOTE: Uses global supabase (service key) intentionally for cache writes.
        # Cache entries are scoped by user_id/org_id columns and filtered by RPC on read.
        # Using scoped client here would prevent writing due to RLS insert restrictions.
        if not supabase or not settings.OPENAI_API_KEY or not response_text:
            return

        # Quality gate: reject low-quality, error, or creative-writing responses
        if not self._passes_quality_gate(query, response_text):
            logger.info("[Cache] Response failed quality gate, skipping cache write")
            return

        try:
            # 1. Resolve embedding model and get embedding
            await self._resolve_embedding_model()
            response = await self.openai_client.embeddings.create(input=query, model=self._embedding_model, dimensions=1536)
            embedding = response.data[0].embedding

            # 2. Get org_id for multi-tenancy
            u_res = await supabase.table("users").select("organization_id").eq("id", user_id).maybe_single().execute()
            org_id = u_res.data.get("organization_id") if u_res and u_res.data else None

            # 3. Upsert into cache (on conflict with query_hash, update response)
            await (
                supabase.table("semantic_cache")
                .upsert(
                    {
                        "query_text": query,
                        "query_hash": self._query_hash(query),
                        "response_text": response_text,
                        "embedding": embedding,
                        "user_id": user_id,
                        "org_id": org_id,
                    },
                    on_conflict="query_hash",
                )
                .execute()
            )

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
            await supabase.rpc("increment_cache_hit", {"p_cache_id": cache_id}).execute()
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


semantic_cache_service = SemanticCacheService()
