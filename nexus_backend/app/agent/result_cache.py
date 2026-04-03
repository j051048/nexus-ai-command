"""Agent result caching for identical queries."""

import hashlib
import json
import logging

from app.core.cache import cache

logger = logging.getLogger(__name__)


def _generate_cache_key(user_id: str, query: str, org_id: str = None) -> str:
    """Generate cache key from user query."""
    key_parts = [user_id, query.strip().lower()]
    if org_id:
        key_parts.append(org_id)
    key_str = ":".join(key_parts)
    return f"agent_result:{hashlib.md5(key_str.encode()).hexdigest()}"


@cache(ttl=1800)
async def get_cached_agent_result(user_id: str, query: str, org_id: str = None) -> dict | None:
    """Get cached agent result. Returns None if not cached."""
    return None


async def cache_agent_result(user_id: str, query: str, result: dict, org_id: str = None):
    """Cache agent result for 30 minutes."""
    from app.core.cache import redis_client

    try:
        cache_key = _generate_cache_key(user_id, query, org_id)
        redis_client.setex(
            cache_key,
            1800,
            json.dumps(result, ensure_ascii=False)
        )
    except Exception as e:
        logger.warning(f"Failed to cache agent result: {e}")
