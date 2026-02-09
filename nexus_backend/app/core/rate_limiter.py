"""
P0 Security: Rate Limiting Middleware
Prevents abuse and DDoS attacks by limiting request rates per IP/user.
"""
import time
from collections import defaultdict
from typing import Dict, Tuple, Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings


class RateLimiter:
    """
    Token bucket rate limiter implementation.
    Thread-safe for async environments.
    """
    def __init__(self, rate: int = 60, burst: int = 10):
        self.rate = rate  # requests per minute
        self.burst = burst  # max burst size
        self.tokens: Dict[str, float] = defaultdict(lambda: float(burst))
        self.last_update: Dict[str, float] = defaultdict(time.time)
    
    def _get_key(self, request: Request, user_id: Optional[str] = None) -> str:
        """Generate rate limit key from user_id or IP"""
        if user_id:
            return f"user:{user_id}"
        # Fallback to IP
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"
    
    def is_allowed(self, request: Request, user_id: Optional[str] = None) -> Tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.
        Returns (is_allowed, metadata)
        """
        key = self._get_key(request, user_id)
        now = time.time()
        
        # Refill tokens based on time passed
        time_passed = now - self.last_update[key]
        self.tokens[key] = min(
            self.burst,
            self.tokens[key] + time_passed * (self.rate / 60.0)
        )
        self.last_update[key] = now
        
        # Check if we have tokens available
        if self.tokens[key] >= 1:
            self.tokens[key] -= 1
            return True, {
                "remaining": int(self.tokens[key]),
                "limit": self.rate,
                "reset": int(60 - (now % 60))
            }
        
        return False, {
            "remaining": 0,
            "limit": self.rate,
            "reset": int(60 - (now % 60)),
            "retry_after": int((1 - self.tokens[key]) * 60 / self.rate)
        }
    
    def reset(self, request: Request, user_id: Optional[str] = None):
        """Reset rate limit for a key (useful for testing)"""
        key = self._get_key(request, user_id)
        self.tokens[key] = float(self.burst)


# Global rate limiter instance
rate_limiter = RateLimiter(
    rate=settings.RATE_LIMIT_PER_MINUTE,
    burst=settings.RATE_LIMIT_BURST
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.
    Applies to all routes except health checks.
    """
    
    # Endpoints exempt from rate limiting
    EXEMPT_PATHS = {"/", "/health", "/favicon.ico", "/docs", "/openapi.json", "/redoc"}
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        # Extract user_id from authorization header if available
        user_id = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                import jwt
                token = auth_header.split(" ")[1]
                payload = jwt.decode(token, options={"verify_signature": False})
                user_id = payload.get("sub")
            except:
                pass
        
        # Check rate limit
        allowed, metadata = rate_limiter.is_allowed(request, user_id)
        
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": "请求过于频繁，请稍后再试",
                    "retry_after": metadata.get("retry_after", 60)
                },
                headers={
                    "X-RateLimit-Limit": str(metadata["limit"]),
                    "X-RateLimit-Remaining": str(metadata["remaining"]),
                    "X-RateLimit-Reset": str(metadata["reset"]),
                    "Retry-After": str(metadata.get("retry_after", 60))
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(metadata["limit"])
        response.headers["X-RateLimit-Remaining"] = str(metadata["remaining"])
        response.headers["X-RateLimit-Reset"] = str(metadata["reset"])
        
        return response


# Decorator for endpoint-specific rate limiting
def rate_limit(calls: int = 10, period: int = 60):
    """
    Decorator for custom rate limits on specific endpoints.
    
    Usage:
        @router.post("/expensive-operation")
        @rate_limit(calls=5, period=60)  # 5 calls per minute
        async def expensive_operation():
            ...
    """
    limiter = RateLimiter(rate=calls, burst=min(calls, 5))
    
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            allowed, metadata = limiter.is_allowed(request)
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Retry after {metadata.get('retry_after', 60)} seconds"
                )
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator