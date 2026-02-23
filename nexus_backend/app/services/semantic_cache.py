"""
Semantic Cache Service - Cache AI responses for similar queries
"""

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from openai import AsyncOpenAI

from app.core.config import settings
from app.core.database import supabase

logger = logging.getLogger(__name__)

# Default TTL for cache entries: 24 hours
DEFAULT_CACHE_TTL_HOURS = 24


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
        1. Exact hash match (fast, no embedding needed)
        2. Semantic similarity via vector search (requires embedding)

        Only entries within the TTL window are considered.
        Returns the cached response if found, otherwise None.
        """
        if not supabase or not settings.OPENAI_API_KEY:
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
            # 1. Get embedding for the new query
            response = await self.openai_client.embeddings.create(input=query, model="text-embedding-3-small")
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
        """
        # NOTE: Uses global supabase (service key) intentionally for cache writes.
        # Cache entries are scoped by user_id/org_id columns and filtered by RPC on read.
        # Using scoped client here would prevent writing due to RLS insert restrictions.
        if not supabase or not settings.OPENAI_API_KEY or not response_text:
            return

        try:
            # 1. Get embedding
            response = await self.openai_client.embeddings.create(input=query, model="text-embedding-3-small")
            embedding = response.data[0].embedding

            # 2. Get org_id for multi-tenancy
            u_res = await supabase.table("users").select("organization_id").eq("id", user_id).maybe_single().execute()
            org_id = u_res.data.get("organization_id") if u_res and u_res.data else None

            # 3. Insert into cache (with deterministic hash for exact-match)
            await supabase.table("semantic_cache").insert(
                {
                    "query_text": query,
                    "query_hash": self._query_hash(query),
                    "response_text": response_text,
                    "embedding": embedding,
                    "user_id": user_id,
                    "org_id": org_id,
                }
            ).execute()

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
