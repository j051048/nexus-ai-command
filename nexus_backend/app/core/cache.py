"""
Redis 缓存装饰器
放在 nexus_backend/app/core/cache.py
"""
import functools
import json
import hashlib
from typing import Any, Callable
import redis
import os

redis_client = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    decode_responses=True
)


def cache(ttl: int = 300):
    """
    缓存函数结果到 Redis

    用法:
    @cache(ttl=60)  # 缓存 60 秒
    async def get_user(user_id: str):
        return await db.query(...)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # 生成缓存 key
            key_data = f"{func.__name__}:{args}:{kwargs}"
            cache_key = f"cache:{hashlib.md5(key_data.encode()).hexdigest()}"

            # 尝试从缓存获取
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # 执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            redis_client.setex(
                cache_key,
                ttl,
                json.dumps(result, ensure_ascii=False)
            )

            return result
        return wrapper
    return decorator


# 使用示例:
# from app.core.cache import cache
#
# @cache(ttl=300)  # 缓存 5 分钟
# async def get_org_info(org_id: str):
#     return await supabase.table("organizations").select("*").eq("id", org_id).execute()
