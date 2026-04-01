"""
Semantic cache for reducing LLM latency.

P0 Task: Cache high-frequency queries to reduce latency from 24.5s to <10s.
"""

import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_cache_store = {}


def get_cache_key(query: str, threshold: float = 0.95) -> str:
    """Generate cache key from query."""
    return hashlib.md5(query.encode()).hexdigest()


def get_cached_response(query: str) -> Optional[str]:
    """Get cached response if exists."""
    key = get_cache_key(query)
    if key in _cache_store:
        logger.info(f"[Cache] Hit for query: {query[:50]}")
        return _cache_store[key]
    return None


def set_cached_response(query: str, response: str):
    """Cache response for query."""
    key = get_cache_key(query)
    _cache_store[key] = response
    logger.debug(f"[Cache] Stored for query: {query[:50]}")


def clear_cache():
    """Clear all cached responses."""
    _cache_store.clear()
    logger.info("[Cache] Cleared")
