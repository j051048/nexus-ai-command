"""
P0 Security: Rate Limiting Middleware
Prevents abuse and DDoS attacks by limiting request rates per IP/user.

P1 Security Fix #5: Support Redis for distributed deployments
P1 Security Fix #7: Removed verify_signature=False vulnerability
"""

import time
import os
import logging
from collections import defaultdict
from typing import Dict, Tuple, Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings

logger = logging.getLogger(__name__)

# Check for Redis availability for distributed rate limiting
REDIS_URL = os.getenv("REDIS_URL")
redis_client = None

if REDIS_URL:
    try:
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
        logger.info("[RateLimiter] Redis backend enabled for distributed rate limiting")
    except ImportError:
        logger.warning(
            "[RateLimiter] redis package not installed, falling back to in-memory"
        )
    except Exception as e:
        logger.warning(
            f"[RateLimiter] Redis connection failed: {e}, falling back to in-memory"
        )


class RateLimiter:
    """
    Token bucket rate limiter implementation.

    P1 Security Fix #5:
    - Uses Redis when available for multi-instance deployments
    - Falls back to in-memory for single-instance/dev
    - Logs warnings in production if Redis is not configured
    """

    def __init__(self, rate: int = 60, burst: int = 10, prefix: str = "rl"):
        self.rate = rate  # requests per minute
        self.burst = burst  # max burst size
        self.prefix = prefix

        # In-memory fallback (single instance only)
        self.tokens: Dict[str, float] = defaultdict(lambda: float(burst))
        self.last_update: Dict[str, float] = defaultdict(time.time)

        # Production warning
        if settings.ENV == "production" and not redis_client:
            logger.warning(
                "[P1 Security] Rate limiter using in-memory storage in production! "
                "Set REDIS_URL for proper distributed rate limiting."
            )

    def _get_key(self, request: Request, user_id: Optional[str] = None) -> str:
        """Generate rate limit key from user_id or IP"""
        if user_id:
            return f"{self.prefix}:user:{user_id}"
        # Fallback to IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return f"{self.prefix}:ip:{ip}"

    async def is_allowed(
        self, request: Request, user_id: Optional[str] = None
    ) -> Tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.
        Returns (is_allowed, metadata)
        """
        key = self._get_key(request, user_id)

        # Use Redis if available
        if redis_client:
            return await self._check_redis(key)
        else:
            return self._check_memory(key)

    async def _check_redis(self, key: str) -> Tuple[bool, dict]:
        """Redis-backed rate limiting (distributed)"""
        try:
            now = time.time()
            pipe = redis_client.pipeline()

            # Get current state
            tokens_key = f"{key}:tokens"
            time_key = f"{key}:time"

            pipe.get(tokens_key)
            pipe.get(time_key)
            results = await pipe.execute()

            current_tokens = float(results[0]) if results[0] else float(self.burst)
            last_update = float(results[1]) if results[1] else now

            # Refill tokens
            time_passed = now - last_update
            new_tokens = min(
                self.burst, current_tokens + time_passed * (self.rate / 60.0)
            )

            if new_tokens >= 1:
                new_tokens -= 1

                # Update Redis with TTL
                pipe = redis_client.pipeline()
                pipe.set(tokens_key, new_tokens, ex=120)  # 2 minute TTL
                pipe.set(time_key, now, ex=120)
                await pipe.execute()

                return True, {
                    "remaining": int(new_tokens),
                    "limit": self.rate,
                    "reset": int(60 - (now % 60)),
                }

            return False, {
                "remaining": 0,
                "limit": self.rate,
                "reset": int(60 - (now % 60)),
                "retry_after": int((1 - new_tokens) * 60 / self.rate),
            }

        except Exception as e:
            logger.error(f"[RateLimiter] Redis error: {e}, falling back to in-memory")
            # P0 Fix: Fail-closed — fallback to in-memory instead of allowing all
            return self._check_memory(key)

    def _check_memory(self, key: str) -> Tuple[bool, dict]:
        """In-memory rate limiting (single instance)"""
        now = time.time()

        # Refill tokens based on time passed
        time_passed = now - self.last_update[key]
        self.tokens[key] = min(
            self.burst, self.tokens[key] + time_passed * (self.rate / 60.0)
        )
        self.last_update[key] = now

        # Check if we have tokens available
        if self.tokens[key] >= 1:
            self.tokens[key] -= 1
            return True, {
                "remaining": int(self.tokens[key]),
                "limit": self.rate,
                "reset": int(60 - (now % 60)),
            }

        return False, {
            "remaining": 0,
            "limit": self.rate,
            "reset": int(60 - (now % 60)),
            "retry_after": int((1 - self.tokens[key]) * 60 / self.rate),
        }

    def reset(self, request: Request, user_id: Optional[str] = None):
        """Reset rate limit for a key (useful for testing)"""
        key = self._get_key(request, user_id)
        self.tokens[key] = float(self.burst)


# Global rate limiter instance
rate_limiter = RateLimiter(
    rate=settings.RATE_LIMIT_PER_MINUTE, burst=settings.RATE_LIMIT_BURST
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    P1 Security Fix #7: Removed JWT decoding with verify_signature=False
    Now uses IP-based limiting only in middleware layer.
    User-based limiting should be done at endpoint level after proper auth.
    """

    # Endpoints exempt from rate limiting
    EXEMPT_PATHS = {"/", "/health", "/favicon.ico", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # P1 Security Fix #7:
        # NO LONGER extract user_id from JWT without signature verification!
        # That was a security vulnerability (algorithm confusion, token manipulation)
        #
        # Rate limiting at middleware level now uses IP only.
        # For user-specific rate limiting, use @rate_limit decorator on
        # endpoints AFTER proper authentication.
        user_id = None  # IP-based only at middleware level

        # Check rate limit
        allowed, metadata = await rate_limiter.is_allowed(request, user_id)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": "请求过于频繁，请稍后再试",
                    "retry_after": metadata.get("retry_after", 60),
                },
                headers={
                    "X-RateLimit-Limit": str(metadata["limit"]),
                    "X-RateLimit-Remaining": str(metadata["remaining"]),
                    "X-RateLimit-Reset": str(metadata["reset"]),
                    "Retry-After": str(metadata.get("retry_after", 60)),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(metadata["limit"])
        response.headers["X-RateLimit-Remaining"] = str(metadata["remaining"])
        response.headers["X-RateLimit-Reset"] = str(metadata["reset"])

        return response


# Decorator for endpoint-specific rate limiting (use AFTER authentication)
def rate_limit(calls: int = 10, period: int = 60):
    """
    Decorator for custom rate limits on specific endpoints.

    P1 Security: Use this AFTER proper authentication for user-based limiting.

    Usage:
        @router.post("/expensive-operation")
        @rate_limit(calls=5, period=60)  # 5 calls per minute
        async def expensive_operation(user_id: str = Depends(get_current_user_id)):
            ...
    """
    limiter = RateLimiter(rate=calls, burst=min(calls, 5), prefix="ep")

    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            allowed, metadata = await limiter.is_allowed(request)
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Retry after {metadata.get('retry_after', 60)} seconds",
                )
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator
