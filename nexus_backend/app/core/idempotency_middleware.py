"""
HTTP Idempotency Key Middleware

Prevents duplicate write operations (POST/PUT/DELETE) by checking
X-Idempotency-Key header against Redis cache.

Flow:
1. Client sends POST /api/chat with header X-Idempotency-Key: <uuid>
2. Middleware checks Redis for key existence
3. If found: return cached response immediately (no re-execution)
4. If not found: execute handler, cache response in Redis with TTL
5. GET/OPTIONS requests are always passed through (reads are safe)
"""

import json
import logging
import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Idempotency key TTL (24 hours by default)
IDEMPOTENCY_TTL = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))

# Only apply to write methods
_WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

# Paths that should be idempotency-protected (write endpoints)
# Other paths are passed through without idempotency check
_PROTECTED_PREFIXES = (
    "/api/chat",
    "/api/mcp/",
    "/api/v1/approval",
    "/api/v1/crm",
    "/api/v1/contracts",
    "/api/v1/vmd/",
)

_memory_cache: dict[str, tuple[float, dict]] = {}
_MAX_MEMORY_CACHE_ITEMS = int(os.getenv("IDEMPOTENCY_MEMORY_FALLBACK_MAX", "1000"))
_MEMORY_FALLBACK_TTL = int(
    os.getenv("IDEMPOTENCY_MEMORY_FALLBACK_TTL_SECONDS", "3600")
)


def _prune_memory_cache(now: float | None = None) -> None:
    """Remove expired entries and keep the process-local fallback bounded."""
    now = now or time.time()
    expired_keys = [
        key for key, (expires_at, _) in _memory_cache.items() if expires_at < now
    ]
    for key in expired_keys:
        _memory_cache.pop(key, None)

    while len(_memory_cache) > _MAX_MEMORY_CACHE_ITEMS:
        oldest_key = next(iter(_memory_cache))
        _memory_cache.pop(oldest_key, None)


def _memory_get(cache_key: str) -> dict | None:
    _prune_memory_cache()
    item = _memory_cache.get(cache_key)
    if not item:
        return None
    expires_at, data = item
    if expires_at < time.time():
        _memory_cache.pop(cache_key, None)
        return None
    return data


def _memory_set(cache_key: str, data: dict, ttl: int) -> None:
    _prune_memory_cache()
    while len(_memory_cache) >= _MAX_MEMORY_CACHE_ITEMS:
        oldest_key = next(iter(_memory_cache))
        _memory_cache.pop(oldest_key, None)
    _memory_cache[cache_key] = (time.time() + ttl, data)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces idempotency for write operations.

    When a request includes an X-Idempotency-Key header:
    - If the key was seen before (within TTL), returns the cached response
    - If the key is new, processes the request and caches the response

    Requests without the header are processed normally (no caching).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only check write methods
        if request.method not in _WRITE_METHODS:
            return await call_next(request)

        # Only check protected paths
        path = request.url.path
        if not any(path.startswith(p) for p in _PROTECTED_PREFIXES):
            return await call_next(request)

        # Get idempotency key from header
        idempotency_key = request.headers.get("X-Idempotency-Key")
        if not idempotency_key:
            # No key provided - proceed normally
            return await call_next(request)

        # Validate key format (should be UUID-like, max 128 chars)
        if len(idempotency_key) > 128:
            return Response(
                content=json.dumps(
                    {
                        "success": False,
                        "error": {
                            "code": "INVALID_IDEMPOTENCY_KEY",
                            "message": "Key too long (max 128 chars)",
                        },
                    }
                ),
                status_code=400,
                media_type="application/json",
            )

        # Build Redis key with path + method for uniqueness
        cache_key = f"idempotency:{request.method}:{path}:{idempotency_key}"

        cache_service = None
        use_memory_fallback = False
        try:
            from app.services.cache_service import cache_service

            # Check if we already have a cached response
            # NOTE: cache_service.get() auto-deserializes JSON, so cached
            # will be a dict (not a string) if the key exists.
            cached = await cache_service.get(cache_key)
            if cached:
                logger.info("Idempotency hit: %s", cache_key)
                # cached is already a dict thanks to cache_service.get() auto-deserialization
                cached_data = cached if isinstance(cached, dict) else json.loads(cached)
                return Response(
                    content=cached_data["body"],
                    status_code=cached_data["status_code"],
                    media_type=cached_data.get("media_type", "application/json"),
                    headers={"X-Idempotency-Replayed": "true"},
                )
        except Exception as e:
            logger.error("Idempotency cache check failed; using memory fallback: %s", e)
            use_memory_fallback = True
            cached_data = _memory_get(cache_key)
            if cached_data:
                return Response(
                    content=cached_data["body"],
                    status_code=cached_data["status_code"],
                    media_type=cached_data.get("media_type", "application/json"),
                    headers={
                        "X-Idempotency-Replayed": "true",
                        "X-Idempotency-Store": "memory",
                    },
                )

        # Execute the actual request
        response = await call_next(request)

        # Cache the response for future duplicate requests
        # Only cache successful responses (2xx) and non-streaming
        if (
            200 <= response.status_code < 300
            and response.media_type != "text/event-stream"
        ):
            body = b""
            try:
                # Read response body
                async for chunk in response.body_iterator:
                    body += chunk if isinstance(chunk, bytes) else chunk.encode()

                cache_data = {
                    "status_code": response.status_code,
                    "body": body.decode("utf-8", errors="replace"),
                    "media_type": response.media_type or "application/json",
                }

                if use_memory_fallback or cache_service is None:
                    _memory_set(
                        cache_key,
                        cache_data,
                        ttl=min(IDEMPOTENCY_TTL, _MEMORY_FALLBACK_TTL),
                    )
                    logger.warning(
                        "Idempotency cached in process-local memory fallback: %s",
                        cache_key,
                    )
                else:
                    await cache_service.set(cache_key, cache_data, ttl=IDEMPOTENCY_TTL)
                logger.debug("Idempotency cached: %s", cache_key)

                # Return a new response with the already-read body
                # P0 Fix: 移除原始 Content-Length，让 Starlette 根据新 body 重新计算
                new_headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() != "content-length"
                }
                return Response(
                    content=body,
                    status_code=response.status_code,
                    media_type=response.media_type,
                    headers=new_headers,
                )
            except Exception as e:
                logger.error("Idempotency cache set failed: %s", e)
                # If caching fails, we need to return the response
                # But we already consumed body_iterator, so return what we have
                new_headers = {
                    k: v
                    for k, v in response.headers.items()
                    if k.lower() != "content-length"
                }
                return Response(
                    content=body,
                    status_code=response.status_code,
                    media_type=response.media_type,
                    headers=new_headers,
                )

        return response
