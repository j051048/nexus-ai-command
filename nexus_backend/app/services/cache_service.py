"""
P0 Optimization: Enhanced Cache Service with Semantic Caching

Provides distributed caching for user roles, settings, and frequently accessed data.
Falls back to in-memory cache if Redis is unavailable.

Fixes Issue #36: Semantic Cache for similar query caching to reduce LLM costs.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)

# Try to import redis, fall back to in-memory if unavailable
try:
    import redis.asyncio as redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not installed. Using in-memory cache (not suitable for multi-instance deployment)")


class InMemoryCache:
    """Fallback in-memory cache with TTL support"""

    def __init__(self):
        self._cache: dict[str, tuple] = {}  # key -> (value, expiry_time)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> bytes | None:
        async with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if expiry is None or time.time() < expiry:
                    return value.encode() if isinstance(value, str) else value
                else:
                    del self._cache[key]
        return None

    async def set(self, key: str, value: Any, ex: int = None) -> bool:
        async with self._lock:
            expiry = time.time() + ex if ex else None
            self._cache[key] = (value, expiry)
        return True

    async def setex(self, key: str, seconds: int, value: Any) -> bool:
        return await self.set(key, value, ex=seconds)

    async def delete(self, key: str) -> int:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return 1
        return 0

    async def exists(self, key: str) -> int:
        result = await self.get(key)
        return 1 if result is not None else 0

    async def keys(self, pattern: str) -> list:
        """Simple pattern matching (only supports * at end)"""
        async with self._lock:
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                return [k.encode() for k in self._cache if k.startswith(prefix)]
            return [k.encode() for k in self._cache if k == pattern]

    async def flushdb(self):
        async with self._lock:
            self._cache.clear()

    async def ping(self) -> bool:
        return True


class CacheService:
    """
    Unified cache service with Redis backend and in-memory fallback.
    Supports automatic serialization/deserialization of complex objects.
    """

    # Cache TTL defaults (in seconds)
    TTL_SHORT = 60  # 1 minute
    TTL_MEDIUM = 300  # 5 minutes
    TTL_LONG = 600  # 10 minutes
    TTL_VERY_LONG = 3600  # 1 hour

    def __init__(self):
        self._client = None
        self._initialized = False
        self._use_redis = False

    async def init(self):
        """Initialize cache connection"""
        if self._initialized:
            return

        redis_url = os.getenv("REDIS_URL")

        if redis_url and REDIS_AVAILABLE:
            try:
                self._client = redis.from_url(redis_url, encoding="utf-8", decode_responses=False)
                await self._client.ping()
                self._use_redis = True
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}. Using in-memory cache.")
                self._client = InMemoryCache()
                self._use_redis = False
        else:
            self._client = InMemoryCache()
            self._use_redis = False
            if not redis_url:
                logger.info("REDIS_URL not configured. Using in-memory cache.")

        self._initialized = True

    async def _ensure_initialized(self):
        if not self._initialized:
            await self.init()

    async def get(self, key: str) -> Any | None:
        """Get value from cache"""
        await self._ensure_initialized()
        try:
            value = await self._client.get(key)
            if value:
                # Try to deserialize JSON
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value.decode() if isinstance(value, bytes) else value
        except Exception as e:
            logger.debug(f"Cache get error: {e}")
        return None

    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with optional TTL"""
        await self._ensure_initialized()
        try:
            # Serialize complex objects to JSON
            if isinstance(value, dict | list):
                value = json.dumps(value)

            if ttl:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
            return True
        except Exception as e:
            logger.debug(f"Cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        await self._ensure_initialized()
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.debug(f"Cache delete error: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        await self._ensure_initialized()
        try:
            keys = await self._client.keys(pattern)
            if keys:
                for key in keys:
                    await self._client.delete(key)
                return len(keys)
        except Exception as e:
            logger.debug(f"Cache delete_pattern error: {e}")
        return 0

    # ============== Domain-specific methods ==============

    async def ping(self) -> bool:
        """Health check for cache"""
        await self._ensure_initialized()
        try:
            if self._use_redis:
                return await self._client.ping()
            return True  # In-memory always healthy
        except Exception:
            return False

    async def get_user_role(self, user_id: str) -> str | None:
        """Get cached user role"""
        return await self.get(f"role:{user_id}")

    async def set_user_role(self, user_id: str, role: str) -> bool:
        """Cache user role"""
        return await self.set(f"role:{user_id}", role, ttl=self.TTL_LONG)

    async def get_user_settings(self, user_id: str) -> dict | None:
        """Get cached user AI settings"""
        return await self.get(f"settings:{user_id}")

    async def set_user_settings(self, user_id: str, settings: dict) -> bool:
        """Cache user AI settings"""
        return await self.set(f"settings:{user_id}", settings, ttl=self.TTL_MEDIUM)

    async def invalidate_user_cache(self, user_id: str) -> int:
        """Invalidate all cache entries for a user"""
        count = 0
        count += await self.delete_pattern(f"role:{user_id}*")
        count += await self.delete_pattern(f"settings:{user_id}*")
        return count

    async def get_document_metadata(self, doc_id: str) -> dict | None:
        """Get cached document metadata"""
        return await self.get(f"doc:{doc_id}")

    async def set_document_metadata(self, doc_id: str, metadata: dict) -> bool:
        """Cache document metadata"""
        return await self.set(f"doc:{doc_id}", metadata, ttl=self.TTL_VERY_LONG)


# Global cache instance
cache_service = CacheService()


# ============== Semantic Cache for LLM Responses ==============


@dataclass
class SemanticCacheEntry:
    """Entry in the semantic cache."""

    query: str
    response: str
    embedding: list[float]
    timestamp: float
    ttl: int
    metadata: dict[str, Any] = None

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


class SemanticCache:
    """
    P0 Optimization: Semantic cache for LLM responses.

    Caches similar queries together, reducing LLM API calls.
    Uses embeddings to find semantically similar cached queries.

    Features:
    - Embedding-based similarity matching
    - Configurable similarity threshold
    - TTL-based expiration
    - Memory-efficient storage
    """

    def __init__(self, similarity_threshold: float = 0.95, default_ttl: int = 3600, max_entries: int = 1000):  # 1 hour
        self.similarity_threshold = similarity_threshold
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._cache: dict[str, SemanticCacheEntry] = {}
        self._embedding_cache: dict[str, tuple[list[float], float]] = {}  # P2 Fix: key -> (embedding, timestamp)
        self._embedding_cache_ttl = 7200  # 2 hours TTL for embeddings
        self._embedding_cache_max = 5000
        self._embedding_client = None

    async def _get_embedding(self, text: str) -> list[float] | None:
        """Get embedding for text using OpenAI."""
        # Check cache first (with TTL)
        cache_key = hashlib.sha256(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            cached_embedding, cached_at = self._embedding_cache[cache_key]
            if time.time() - cached_at < self._embedding_cache_ttl:
                return cached_embedding
            else:
                del self._embedding_cache[cache_key]

        # Lazy init embedding client
        if self._embedding_client is None:
            try:
                from openai import AsyncOpenAI

                from app.core.config import settings

                self._embedding_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.AI_BASE_URL)
            except Exception as e:
                logger.warning(f"Failed to init embedding client: {e}")
                return None

        try:
            response = await self._embedding_client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],  # Limit input size
            )
            embedding = response.data[0].embedding

            # Cache embedding with timestamp
            self._embedding_cache[cache_key] = (embedding, time.time())
            # P2 Fix: Evict expired entries when approaching limit
            if len(self._embedding_cache) > self._embedding_cache_max:
                now = time.time()
                expired = [k for k, (_, ts) in self._embedding_cache.items() if now - ts > self._embedding_cache_ttl]
                for k in expired:
                    del self._embedding_cache[k]
                # If still over limit, remove oldest half
                if len(self._embedding_cache) > self._embedding_cache_max:
                    sorted_keys = sorted(self._embedding_cache, key=lambda k: self._embedding_cache[k][1])
                    for k in sorted_keys[: len(sorted_keys) // 2]:
                        del self._embedding_cache[k]

            return embedding
        except Exception as e:
            logger.warning(f"Failed to get embedding: {e}")
            return None

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    async def get(self, query: str, context_hash: str = None) -> tuple[str | None, dict[str, Any]]:
        """
        Get cached response for semantically similar query.

        Returns (response, metadata) if found, (None, {}) otherwise.
        """
        # Get embedding for query
        query_embedding = await self._get_embedding(query)
        if not query_embedding:
            return None, {}

        # Search for similar cached queries
        # P2 Fix: Clean expired entries during search and exit early on perfect match
        best_match = None
        best_similarity = 0.0
        expired_keys = []

        for _key, entry in self._cache.items():
            # Track expired entries for cleanup
            if entry.is_expired():
                expired_keys.append(_key)
                continue

            # Skip if context doesn't match
            if context_hash and entry.metadata and entry.metadata.get("context_hash") != context_hash:
                continue

            # Calculate similarity
            similarity = self._cosine_similarity(query_embedding, entry.embedding)

            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_match = entry
                # Early exit on near-perfect match
                if similarity > 0.99:
                    break

        # Lazy cleanup of expired entries found during search
        for k in expired_keys:
            del self._cache[k]

        if best_match:
            return best_match.response, {
                "similarity": best_similarity,
                "original_query": best_match.query,
                "cache_hit": True,
            }

        return None, {}

    async def set(self, query: str, response: str, ttl: int = None, metadata: dict[str, Any] = None) -> bool:
        """Cache a query-response pair."""
        # Get embedding
        embedding = await self._get_embedding(query)
        if not embedding:
            return False

        # Create entry
        entry = SemanticCacheEntry(
            query=query,
            response=response,
            embedding=embedding,
            timestamp=time.time(),
            ttl=ttl or self.default_ttl,
            metadata=metadata or {},
        )

        # Generate key
        key = hashlib.md5(query.encode()).hexdigest()

        # Store
        self._cache[key] = entry

        # Cleanup if needed
        if len(self._cache) > self.max_entries:
            self._cleanup()

        return True

    def _cleanup(self):
        """Remove expired entries."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._cache[key]

        # If still over limit, remove oldest
        if len(self._cache) > self.max_entries:
            sorted_entries = sorted(self._cache.items(), key=lambda x: x[1].timestamp)
            for key, _ in sorted_entries[: len(self._cache) - self.max_entries]:
                del self._cache[key]

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = len(self._cache)
        expired = sum(1 for e in self._cache.values() if e.is_expired())

        return {
            "total_entries": total,
            "active_entries": total - expired,
            "expired_entries": expired,
            "max_entries": self.max_entries,
            "similarity_threshold": self.similarity_threshold,
        }


# Global semantic cache instance
semantic_cache = SemanticCache()


def cached(ttl: int = 300, key_prefix: str = "", tenant_key: str | None = None):
    """
    Decorator for caching function results with optional tenant isolation.

    Args:
        ttl: Cache TTL in seconds (default 300).
        key_prefix: Prefix for cache keys.
        tenant_key: Name of a kwarg (e.g. "org_id", "user_id") whose value
                    will be prepended to the cache key, ensuring per-tenant
                    cache isolation.  If the kwarg is missing or None at
                    call-time the cache is skipped (no cross-tenant leakage).

    Usage:
        @cached(ttl=60, key_prefix="user_data", tenant_key="org_id")
        async def get_org_dashboard(org_id: str):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # P2 Fix: Tenant isolation — if tenant_key is configured,
            # extract its value from kwargs and include in cache key.
            tenant_value = ""
            if tenant_key:
                tenant_value = kwargs.get(tenant_key) or ""
                if not tenant_value:
                    # tenant_key required but not provided → skip cache entirely
                    return await func(*args, **kwargs)
                tenant_value = f"{tenant_value}:"

            # P2 Fix: Use hashlib.sha256 instead of hash() for cross-process stability
            raw_key = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()[:16]
            cache_key = f"{key_prefix}:{tenant_value}{key_hash}"

            # Try to get from cache
            result = await cache_service.get(cache_key)
            if result is not None:
                return result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_service.set(cache_key, result, ttl=ttl)
            return result

        return wrapper

    return decorator
