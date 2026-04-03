"""
统一工具执行包装器 - 提供错误处理、超时控制和日志记录
"""
import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


async def execute_tool_safely(
    tool_func: Callable,
    params: dict[str, Any],
    timeout: int = 30,
    tool_name: str = None
) -> dict[str, Any]:
    """
    统一的工具执行包装器

    Args:
        tool_func: 工具函数
        params: 工具参数
        timeout: 超时时间（秒）
        tool_name: 工具名称（用于日志）

    Returns:
        {'success': bool, 'data': Any, 'error': str}
    """
    name = tool_name or tool_func.__name__

    try:
        # 执行工具（带超时控制）
        result = await asyncio.wait_for(
            tool_func(**params),
            timeout=timeout
        )

        logger.info(f"Tool '{name}' executed successfully")
        return {
            'success': True,
            'data': result
        }

    except TimeoutError:
        error_msg = f"工具执行超时（{timeout}秒），请稍后重试"
        logger.error(f"Tool '{name}' timeout after {timeout}s")
        return {
            'success': False,
            'error': error_msg
        }

    except Exception as e:
        error_msg = f"执行失败: {str(e)}"
        logger.error(f"Tool '{name}' failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': error_msg
        }


def safe_tool(timeout: int = 30):
    """
    装饰器：将普通工具函数包装为安全执行

    用法:
        @safe_tool(timeout=60)
        async def my_tool(param1, param2):
            return result
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await execute_tool_safely(
                func,
                kwargs,
                timeout=timeout,
                tool_name=func.__name__
            )
        return wrapper
    return decorator
