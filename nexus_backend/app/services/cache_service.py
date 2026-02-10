"""
P1 Optimization: Redis Cache Service
Provides distributed caching for user roles, settings, and frequently accessed data.
Falls back to in-memory cache if Redis is unavailable.
"""
import os
import json
import time
import asyncio
import logging
from typing import Any, Optional, Dict
from functools import wraps

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
        self._cache: Dict[str, tuple] = {}  # key -> (value, expiry_time)
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[bytes]:
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
                return [k.encode() for k in self._cache.keys() if k.startswith(prefix)]
            return [k.encode() for k in self._cache.keys() if k == pattern]
    
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
                self._client = redis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=False
                )
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
    
    async def get(self, key: str) -> Optional[Any]:
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
            if isinstance(value, (dict, list)):
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
            return True # In-memory always healthy
        except Exception:
            return False

    async def get_user_role(self, user_id: str) -> Optional[str]:
        """Get cached user role"""
        return await self.get(f"role:{user_id}")
    
    async def set_user_role(self, user_id: str, role: str) -> bool:
        """Cache user role"""
        return await self.set(f"role:{user_id}", role, ttl=self.TTL_LONG)
    
    async def get_user_settings(self, user_id: str) -> Optional[dict]:
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
    
    async def get_document_metadata(self, doc_id: str) -> Optional[dict]:
        """Get cached document metadata"""
        return await self.get(f"doc:{doc_id}")
    
    async def set_document_metadata(self, doc_id: str, metadata: dict) -> bool:
        """Cache document metadata"""
        return await self.set(f"doc:{doc_id}", metadata, ttl=self.TTL_VERY_LONG)


# Global cache instance
cache_service = CacheService()


def cached(ttl: int = 300, key_prefix: str = ""):
    """
    Decorator for caching function results.
    
    Usage:
        @cached(ttl=60, key_prefix="user_data")
        async def get_user_data(user_id: str):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
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