"""
Report caching decorator — wraps ReportService methods with Redis/in-memory cache.

Uses the existing CacheService singleton for storage.
"""

import hashlib
import json
import logging
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


def cached_report(ttl_seconds: int = 300):
    """Decorator to cache report results.

    Cache key format: ``report:{org_id}:{method_name}:{params_hash}``

    The decorated method **must** have ``org_id`` as its first positional arg
    (after ``self``).  All remaining ``*args`` / ``**kwargs`` are hashed into the key.

    Args:
        ttl_seconds: Time-to-live in seconds (default 5 min).
    """

    def decorator(fn):
        @wraps(fn)
        async def wrapper(self, org_id: str, *args, **kwargs):
            from app.services.cache_service import cache_service

            # Build deterministic cache key
            params_blob = json.dumps(
                {"args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in sorted(kwargs.items()) if k != "db"}},
                sort_keys=True,
            )
            params_hash = hashlib.md5(params_blob.encode()).hexdigest()[:12]
            cache_key = f"report:{org_id}:{fn.__name__}:{params_hash}"

            # Try cache hit
            try:
                cached = await cache_service.get(cache_key)
                if cached is not None:
                    logger.debug("Report cache HIT: %s", cache_key)
                    return cached
            except Exception:
                pass  # cache miss or error — just compute

            # Compute fresh result
            result = await fn(self, org_id, *args, **kwargs)

            # Store in cache (best-effort)
            try:
                await cache_service.set(cache_key, result, ttl=ttl_seconds)
                logger.debug("Report cache SET: %s (ttl=%ds)", cache_key, ttl_seconds)
            except Exception as e:
                logger.debug("Report cache SET failed: %s", e)

            return result

        # Expose a manual refresh helper
        wrapper._uncached = fn
        return wrapper

    return decorator


async def invalidate_report(org_id: str, report_type: str) -> bool:
    """Invalidate all cached reports of a given type for an org.

    Since we use hashed params in the key, we need pattern-based deletion.
    Falls back silently if Redis is unavailable.
    """
    from app.services.cache_service import cache_service

    pattern = f"report:{org_id}:{report_type}:*"
    try:
        await cache_service._ensure_initialized()
        if cache_service._use_redis and hasattr(cache_service._client, "keys"):
            keys = await cache_service._client.keys(pattern)
            if keys:
                await cache_service._client.delete(*keys)
                logger.info("Invalidated %d cached reports matching %s", len(keys), pattern)
                return True
    except Exception as e:
        logger.debug("Report cache invalidation failed: %s", e)
    return False
