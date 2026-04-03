"""
Redis 缓存装饰器
放在 nexus_backend/app/core/cache.py
"""

import functools
import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

import redis

logger = logging.getLogger(__name__)

# 延迟初始化 Redis 客户端
redis_client = None
_redis_initialized = False


def _init_redis():
    """延迟初始化 Redis 连接"""
    global redis_client, _redis_initialized
    if _redis_initialized:
        return

    _redis_initialized = True
    try:
        from app.core.config import settings

        _redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
        redis_client = redis.from_url(
            _redis_url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2, retry_on_timeout=True
        )
        # 测试连接
        redis_client.ping()
        # 隐藏密码，只显示 host:port
        _safe_url = _redis_url.split("@")[-1] if "@" in _redis_url else _redis_url
        logger.info(f"Redis 连接成功: {_safe_url}")
    except Exception as e:
        logger.warning(f"Redis 连接失败，缓存功能将降级为直接查询数据库: {e}")
        redis_client = None


def cache(ttl: int = 300, prefix: str = "nexus", exclude_params: list[str] | None = None):
    """
    增强版 Redis 缓存装饰器

    Args:
        ttl: 缓存过期时间（秒）
        prefix: 缓存前缀，建议使用业务模块名，如 "org", "user"
        exclude_params: 不参与缓存 Key 生成的参数名列表（如 db, client, session）

    用法:
    @cache(ttl=60, prefix="org", exclude_params=["db"])
    async def list_departments(self, org_id: str, db=None):
        ...
    """
    if exclude_params is None:
        exclude_params = ["db", "client", "session", "supabase"]

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            _init_redis()  # 确保 Redis 已初始化
            if redis_client is None:
                return await func(*args, **kwargs)

            # 过滤不需要参与 key 生成的参数
            safe_kwargs = {k: v for k, v in kwargs.items() if k not in exclude_params}

            # 生成缓存 key
            # 注意: 如果是实例方法，第一个参数是 self，通常也要排除或者只取其特定属性
            # 这里简单处理，排除第一个参数如果是类实例的情况（简单通过是否有 __dict__ 判断不太严谨，但常用）
            key_args = list(args)
            if (
                key_args
                and hasattr(key_args[0], "__class__")
                and not isinstance(key_args[0], str | int | float | bool | list | dict)
            ):
                key_args = key_args[1:]

            key_data = f"{func.__module__}:{func.__name__}:{key_args}:{safe_kwargs}"
            hash_key = hashlib.md5(key_data.encode()).hexdigest()
            cache_key = f"{prefix}:cache:{hash_key}"

            try:
                # 尝试从缓存获取
                cached = redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache Hit: {cache_key}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"读取缓存出错: {e}")

            # 执行真实函数
            result = await func(*args, **kwargs)

            try:
                # 存入缓存
                if result is not None:
                    redis_client.setex(cache_key, ttl, json.dumps(result, ensure_ascii=False))
                    logger.debug(f"Cache Set: {cache_key} (ttl={ttl})")
            except Exception as e:
                logger.warning(f"设置缓存出错: {e}")

            return result

        return wrapper

    return decorator


def invalidate_cache(pattern: str):
    """根据模式批量清理缓存"""
    _init_redis()  # 确保 Redis 已初始化
    if redis_client is None:
        return
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
            logger.info(f"Invalidated {len(keys)} cache keys matching {pattern}")
    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
