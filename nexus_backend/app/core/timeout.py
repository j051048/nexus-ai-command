"""
Agent 超时控制装饰器 + 复杂度分级 SLO
"""

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# P1: 延迟 SLO — 按复杂度分级超时 (秒)
COMPLEXITY_TIMEOUT: dict[str, int] = {
    "SIMPLE": 15,
    "MODERATE": 45,
    "COMPLEX": 90,
    "MULTI_AGENT": 120,
}

DEFAULT_TIMEOUT = 60


def get_timeout_for_complexity(complexity: str) -> int:
    return COMPLEXITY_TIMEOUT.get(complexity, DEFAULT_TIMEOUT)


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


def with_complexity_timeout(func: Callable[..., T]) -> Callable[..., T]:
    """
    根据 AgentState 中的 complexity 字段动态选择超时时间。
    用于 AgentGraph.run() — 第二个参数 initial_state 需包含 complexity。
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        initial_state = args[1] if len(args) > 1 else kwargs.get("initial_state", {})
        complexity = initial_state.get("complexity", "MODERATE")
        timeout = get_timeout_for_complexity(complexity)

        try:
            return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
        except TimeoutError:
            logger.error(
                f"Agent 执行超时: complexity={complexity}, timeout={timeout}s",
                extra={"complexity": complexity, "timeout": timeout},
            )
            raise TimeoutError(
                f"Agent 执行超时 ({timeout}秒, 复杂度={complexity})，请简化请求或稍后重试"
            )

    return wrapper
