"""
P0 Security: Rate Limiting Middleware
Prevents abuse and DDoS attacks by limiting request rates per IP/user.

P1 Security Fix #5: Support Redis for distributed deployments
P1 Security Fix #7: Removed verify_signature=False vulnerability
#37: Enhanced per-user + per-IP + per-endpoint rate limiting with sliding window
"""

import contextlib
import logging
import os
import time
from collections import defaultdict
from functools import wraps

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.responses import UTF8JSONResponse

logger = logging.getLogger(__name__)

# P0 Security: Trusted proxy count to prevent X-Forwarded-For spoofing
# Set to 0 to ignore X-Forwarded-For entirely and always use request.client.host
# Set to N to trust the Nth entry from the right of the X-Forwarded-For list
TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))

# #37: 配置项 - 各维度的默认限速
RATE_LIMIT_PER_USER = int(os.getenv("RATE_LIMIT_PER_USER", "100"))  # 每用户每分钟
RATE_LIMIT_PER_IP = int(os.getenv("RATE_LIMIT_PER_IP", "200"))  # 每IP每分钟

# #37: 敏感端点限速配置 (每分钟请求数)
SENSITIVE_ENDPOINT_LIMITS: dict[str, int] = {
    "/api/auth/login": 20,
    "/api/auth/register": 10,
    "/api/auth/reset-password": 10,
    "/api/chat": 20,
    "/api/chat/send": 20,
    "/api/documents/upload": 15,
    "/api/export": 10,
}

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
        logger.warning(f"[RateLimiter] Redis connection failed: {e}", exc_info=True)
elif settings.ENV == "production":
    logger.critical(
        "[RateLimiter] REDIS_URL not set in production! "
        "Rate limiting will NOT share across workers. "
        "Set REDIS_URL env var for proper distributed rate limiting."
    )


def _extract_client_ip(request: Request) -> str:
    """从请求中提取客户端 IP，考虑反向代理。"""
    ip = request.client.host if request.client else "unknown"
    if TRUSTED_PROXY_COUNT > 0:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",")]
            index = max(0, len(parts) - TRUSTED_PROXY_COUNT)
            ip = parts[index]
    return ip


class SlidingWindowRateLimiter:
    """
    #37: 滑动窗口限速器 (Sliding Window Rate Limiter)

    相比令牌桶算法，滑动窗口更精确地控制时间窗口内的请求数量。
    支持 Redis（分布式部署）和内存（单实例/开发）两种后端。
    """

    def __init__(self, rate: int = 60, window_seconds: int = 60, prefix: str = "sw"):
        self.rate = rate  # 窗口期内最大请求数
        self.window = window_seconds  # 时间窗口（秒）
        self.prefix = prefix

        # 内存回退 (key -> list of timestamps)
        self._memory_store: dict[str, list[float]] = defaultdict(list)

        # Production warning
        if settings.ENV == "production" and not redis_client:
            logger.warning(
                "[P1 Security] Rate limiter using in-memory storage in production! "
                "Set REDIS_URL for proper distributed rate limiting."
            )

    async def is_allowed(self, key: str) -> tuple[bool, dict]:
        """
        检查是否允许请求。
        返回 (is_allowed, metadata)
        """
        if redis_client:
            return await self._check_redis(key)
        return self._check_memory(key)

    async def _check_redis(self, key: str) -> tuple[bool, dict]:
        """基于 Redis 的滑动窗口限速 (使用 sorted set)"""
        try:
            now = time.time()
            window_start = now - self.window
            full_key = f"{self.prefix}:{key}"

            pipe = redis_client.pipeline()
            # 1. 清除窗口外的旧记录
            pipe.zremrangebyscore(full_key, 0, window_start)
            # 2. 获取当前窗口内的请求数
            pipe.zcard(full_key)
            # 3. 添加当前请求
            pipe.zadd(full_key, {f"{now}:{id(pipe)}": now})
            # 4. 设置 key 过期时间
            pipe.expire(full_key, self.window + 10)
            results = await pipe.execute()

            current_count = results[1]  # zcard 结果

            remaining = max(0, self.rate - current_count - 1)
            reset_at = int(now) + self.window

            if current_count < self.rate:
                return True, {
                    "remaining": remaining,
                    "limit": self.rate,
                    "reset": reset_at,
                }

            # 超过限制，移除刚添加的记录
            with contextlib.suppress(Exception):
                await redis_client.zremrangebyscore(full_key, now, now + 1)

            return False, {
                "remaining": 0,
                "limit": self.rate,
                "reset": reset_at,
                "retry_after": self.window,
            }

        except Exception as e:
            logger.error(f"[RateLimiter] Redis sliding window error: {e}")
            return self._check_memory(key)

    def _check_memory(self, key: str) -> tuple[bool, dict]:
        """基于内存的滑动窗口限速"""
        now = time.time()
        window_start = now - self.window
        full_key = f"{self.prefix}:{key}"

        # 清除过期记录
        timestamps = self._memory_store[full_key]
        self._memory_store[full_key] = [ts for ts in timestamps if ts > window_start]

        current_count = len(self._memory_store[full_key])
        remaining = max(0, self.rate - current_count - 1)
        reset_at = int(now) + self.window

        if current_count < self.rate:
            self._memory_store[full_key].append(now)
            return True, {
                "remaining": remaining,
                "limit": self.rate,
                "reset": reset_at,
            }

        # 内存清理：防止过多 key 导致内存泄漏
        if len(self._memory_store) > 50000:
            stale_keys = [
                k
                for k, v in self._memory_store.items()
                if not v or v[-1] < window_start
            ]
            for k in stale_keys:
                del self._memory_store[k]

        return False, {
            "remaining": 0,
            "limit": self.rate,
            "reset": reset_at,
            "retry_after": self.window,
        }


class RateLimiter:
    """
    Token bucket rate limiter implementation (保留向后兼容).

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
        self.tokens: dict[str, float] = defaultdict(lambda: float(burst))
        self.last_update: dict[str, float] = defaultdict(time.time)

        # Production warning
        if settings.ENV == "production" and not redis_client:
            logger.warning(
                "[P1 Security] Rate limiter using in-memory storage in production! "
                "Set REDIS_URL for proper distributed rate limiting."
            )

    def _get_key(self, request: Request, user_id: str | None = None) -> str:
        """Generate rate limit key from user_id or IP"""
        if user_id:
            return f"{self.prefix}:user:{user_id}"
        ip = _extract_client_ip(request)
        return f"{self.prefix}:ip:{ip}"

    async def is_allowed(
        self, request: Request, user_id: str | None = None
    ) -> tuple[bool, dict]:
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

    async def _check_redis(self, key: str) -> tuple[bool, dict]:
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

    def _check_memory(self, key: str) -> tuple[bool, dict]:
        """In-memory rate limiting (single instance)"""
        now = time.time()

        # P0 Fix: Prevent memory leak — evict stale entries when dict grows too large
        if len(self.last_update) > 10000:
            stale_cutoff = now - 3600  # 1 hour
            stale_keys = [k for k, ts in self.last_update.items() if ts < stale_cutoff]
            for k in stale_keys:
                self.tokens.pop(k, None)
                self.last_update.pop(k, None)
            if stale_keys:
                logger.info(
                    f"[RateLimiter] Evicted {len(stale_keys)} stale entries (remaining: {len(self.last_update)})"
                )

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

    def reset(self, request: Request, user_id: str | None = None):
        """Reset rate limit for a key (useful for testing)"""
        key = self._get_key(request, user_id)
        self.tokens[key] = float(self.burst)


# Global rate limiter instances
rate_limiter = RateLimiter(
    rate=settings.RATE_LIMIT_PER_MINUTE, burst=settings.RATE_LIMIT_BURST
)

# #37: 各维度的滑动窗口限速器
_per_user_limiter = SlidingWindowRateLimiter(
    rate=RATE_LIMIT_PER_USER, window_seconds=60, prefix="rl:user"
)
_per_ip_limiter = SlidingWindowRateLimiter(
    rate=RATE_LIMIT_PER_IP, window_seconds=60, prefix="rl:ip"
)
_endpoint_limiters: dict[str, SlidingWindowRateLimiter] = {}

# #35: 租户级别限速器 (per-minute + per-hour)
_per_tenant_minute_limiter = SlidingWindowRateLimiter(
    rate=settings.TENANT_RATE_LIMIT_PER_MINUTE,
    window_seconds=60,
    prefix="rl:tenant:min",
)
_per_tenant_hour_limiter = SlidingWindowRateLimiter(
    rate=settings.TENANT_RATE_LIMIT_PER_HOUR, window_seconds=3600, prefix="rl:tenant:hr"
)


def _get_endpoint_limiter(path: str) -> SlidingWindowRateLimiter | None:
    """获取端点级别限速器（懒加载）。"""
    # 精确匹配
    if path in SENSITIVE_ENDPOINT_LIMITS:
        if path not in _endpoint_limiters:
            _endpoint_limiters[path] = SlidingWindowRateLimiter(
                rate=SENSITIVE_ENDPOINT_LIMITS[path],
                window_seconds=60,
                prefix=f"rl:ep:{path}",
            )
        return _endpoint_limiters[path]

    # 前缀匹配
    for prefix, limit in SENSITIVE_ENDPOINT_LIMITS.items():
        if path.startswith(prefix):
            if prefix not in _endpoint_limiters:
                _endpoint_limiters[prefix] = SlidingWindowRateLimiter(
                    rate=limit, window_seconds=60, prefix=f"rl:ep:{prefix}"
                )
            return _endpoint_limiters[prefix]

    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    #37: 增强的多维度限速:
    Phase 1 (pre-auth): 全局 IP 限速
    Phase 2 (post-auth): 用户级限速 + 端点级限速 + 分层限速

    P1 Security Fix #7: Removed JWT decoding with verify_signature=False
    P1-8: Integrates with tiered rate_limiting_service for per-endpoint limits.
    """

    # Endpoints exempt from rate limiting
    EXEMPT_PATHS = {
        "/",
        "/health",
        "/favicon.ico",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/metrics",
    }

    # P1-8: Endpoint category mapping for tiered limits
    ENDPOINT_CATEGORIES = {
        "/api/chat": "chat",
        "/api/documents/upload": "upload",
        "/api/auth": "auth",
        "/api/export": "export",
    }

    # P1-8: Per-category rate limiter cache (persistent across requests)
    _category_limiters: dict[str, RateLimiter] = {}

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Phase 1: Global IP-based rate limiting (always runs, pre-auth)
        client_ip = _extract_client_ip(request)
        ip_allowed, ip_meta = await _per_ip_limiter.is_allowed(f"ip:{client_ip}")

        if not ip_allowed:
            return UTF8JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "请求过于频繁，请稍后再试",
                        "retry_after": ip_meta.get("retry_after", 60),
                    },
                },
                headers={
                    "X-RateLimit-Limit": str(ip_meta["limit"]),
                    "X-RateLimit-Remaining": str(ip_meta["remaining"]),
                    "X-RateLimit-Reset": str(ip_meta["reset"]),
                    "Retry-After": str(ip_meta.get("retry_after", 60)),
                },
            )

        # Phase 1.5: 端点级限速（敏感端点，pre-auth）
        path = request.url.path
        endpoint_limiter = _get_endpoint_limiter(path)
        if endpoint_limiter:
            ep_key = f"ep:{client_ip}:{path}"
            ep_allowed, ep_meta = await endpoint_limiter.is_allowed(ep_key)
            if not ep_allowed:
                return UTF8JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "ENDPOINT_RATE_LIMIT_EXCEEDED",
                            "message": "该接口请求过于频繁，请稍后再试",
                            "retry_after": ep_meta.get("retry_after", 60),
                        },
                    },
                    headers={
                        "X-RateLimit-Limit": str(ep_meta["limit"]),
                        "X-RateLimit-Remaining": str(ep_meta["remaining"]),
                        "X-RateLimit-Reset": str(ep_meta["reset"]),
                        "Retry-After": str(ep_meta.get("retry_after", 60)),
                    },
                )

        # Process request (auth middleware will set request.state.user_id)
        response = await call_next(request)

        # Phase 2: Post-auth per-user rate check (user_id now available)
        user_id = (
            getattr(request.state, "user_id", None)
            if hasattr(request, "state")
            else None
        )
        tenant_id = (
            getattr(request.state, "org_id", None)
            if hasattr(request, "state")
            else None
        )
        user_meta = ip_meta  # 默认使用 IP 限速的 metadata

        # #35: Tenant-level rate limiting (org_id available after auth)
        if tenant_id:
            # Check per-minute tenant quota
            t_min_allowed, t_min_meta = await _per_tenant_minute_limiter.is_allowed(
                f"tenant:{tenant_id}"
            )
            if not t_min_allowed:
                return UTF8JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "TENANT_RATE_LIMIT_EXCEEDED",
                            "message": "贵组织的请求已达到每分钟配额上限，请稍后再试",
                            "retry_after": t_min_meta.get("retry_after", 60),
                        },
                    },
                    headers={
                        "X-RateLimit-Limit": str(t_min_meta["limit"]),
                        "X-RateLimit-Remaining": str(t_min_meta["remaining"]),
                        "X-RateLimit-Reset": str(t_min_meta["reset"]),
                        "Retry-After": str(t_min_meta.get("retry_after", 60)),
                    },
                )

            # Check per-hour tenant quota
            t_hr_allowed, t_hr_meta = await _per_tenant_hour_limiter.is_allowed(
                f"tenant:{tenant_id}"
            )
            if not t_hr_allowed:
                return UTF8JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "TENANT_HOURLY_LIMIT_EXCEEDED",
                            "message": "贵组织的请求已达到每小时配额上限，请稍后再试",
                            "retry_after": t_hr_meta.get("retry_after", 3600),
                        },
                    },
                    headers={
                        "X-RateLimit-Limit": str(t_hr_meta["limit"]),
                        "X-RateLimit-Remaining": str(t_hr_meta["remaining"]),
                        "X-RateLimit-Reset": str(t_hr_meta["reset"]),
                        "Retry-After": str(t_hr_meta.get("retry_after", 3600)),
                    },
                )

        if user_id:
            user_allowed, user_meta = await _per_user_limiter.is_allowed(
                f"user:{user_id}"
            )
            if not user_allowed:
                return UTF8JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "USER_RATE_LIMIT_EXCEEDED",
                            "message": "您的请求过于频繁，请稍后再试",
                            "retry_after": user_meta.get("retry_after", 60),
                        },
                    },
                    headers={
                        "X-RateLimit-Limit": str(user_meta["limit"]),
                        "X-RateLimit-Remaining": str(user_meta["remaining"]),
                        "X-RateLimit-Reset": str(user_meta["reset"]),
                        "Retry-After": str(user_meta.get("retry_after", 60)),
                    },
                )

        # Phase 3: Tiered rate check (existing per-category logic)
        category = None
        for prefix, cat in self.ENDPOINT_CATEGORIES.items():
            if path.startswith(prefix):
                category = cat
                break

        if category and user_id:
            try:
                from app.services.rate_limiting_service import rate_limiting_service

                tier = await rate_limiting_service.get_user_tier(user_id)
                tier_limit = rate_limiting_service.get_endpoint_limit(tier, category)

                if tier_limit:
                    # Use persistent per-category limiter keyed by tier+category
                    cache_key = f"{tier.value}:{category}"
                    if cache_key not in self._category_limiters:
                        self._category_limiters[cache_key] = RateLimiter(
                            rate=tier_limit,
                            burst=max(tier_limit // 6, 2),
                            prefix=f"tier:{cache_key}",
                        )
                    tier_limiter = self._category_limiters[cache_key]
                    tier_allowed, tier_meta = await tier_limiter.is_allowed(
                        request, user_id
                    )

                    if not tier_allowed:
                        # Return 429 — tier limit exceeded
                        return UTF8JSONResponse(
                            status_code=429,
                            content={
                                "success": False,
                                "error": {
                                    "code": "RATE_LIMIT_EXCEEDED",
                                    "message": "您当前套餐的接口调用频率已达上限，请稍后再试",
                                    "retry_after": tier_meta.get("retry_after", 60),
                                },
                            },
                            headers={
                                "X-RateLimit-Limit": str(tier_meta["limit"]),
                                "X-RateLimit-Remaining": str(tier_meta["remaining"]),
                                "Retry-After": str(tier_meta.get("retry_after", 60)),
                            },
                        )
            except Exception:
                pass  # Tiered limiting is best-effort; global limit already passed

        # #37: 添加标准限速响应头
        best_meta = user_meta if user_id else ip_meta
        response.headers["X-RateLimit-Limit"] = str(best_meta["limit"])
        response.headers["X-RateLimit-Remaining"] = str(best_meta["remaining"])
        response.headers["X-RateLimit-Reset"] = str(best_meta["reset"])

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
        @wraps(func)
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
