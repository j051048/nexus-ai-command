"""
API 限流中间件
放在 nexus_backend/app/core/rate_limit.py
"""
from fastapi import Request, HTTPException, status
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio

# 简单的内存限流器（生产环境建议用 Redis）
_rate_limit_store: dict[str, list[datetime]] = defaultdict(list)
_lock = asyncio.Lock()


async def rate_limit_middleware(request: Request, call_next):
    """
    简单的 IP 限流中间件

    规则：
    - 每个 IP 每分钟最多 60 次请求
    - 登录接口每分钟最多 5 次
    """
    # 获取客户端 IP
    client_ip = request.client.host if request.client else "unknown"

    # 登录接口特殊限制
    if "/api/auth/login" in request.url.path:
        max_requests = 5
        window = 60  # 秒
    else:
        max_requests = 60
        window = 60

    async with _lock:
        now = datetime.now()
        key = f"{client_ip}:{request.url.path}"

        # 清理过期记录
        _rate_limit_store[key] = [
            ts for ts in _rate_limit_store[key]
            if now - ts < timedelta(seconds=window)
        ]

        # 检查是否超限
        if len(_rate_limit_store[key]) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试"
            )

        # 记录本次请求
        _rate_limit_store[key].append(now)

    response = await call_next(request)
    return response
