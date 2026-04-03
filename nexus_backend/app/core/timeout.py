"""
Agent 超时控制装饰器
放在 nexus_backend/app/core/timeout.py
"""

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_timeout(seconds: int = 60):
    """
    为异步函数添加超时控制

    用法:
    @with_timeout(seconds=30)
    async def my_agent_function():
        ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except TimeoutError:
                logger.error(
                    f"函数 {func.__name__} 执行超时 ({seconds}秒)",
                    extra={"function": func.__name__, "timeout": seconds},
                )
                raise TimeoutError("操作超时，请稍后重试")

        return wrapper

    return decorator


# 使用示例（在 graph.py 或 nodes.py 中）:
# @with_timeout(seconds=120)  # Agent 最多执行 2 分钟
# async def run_agent(state):
#     ...
