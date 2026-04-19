"""
P2: 工具调用缓存 - 提升响应速度

核心功能:
1. 只读工具结果缓存
2. 智能缓存失效
3. 减少重复调用
"""

import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

# 只读工具列表（可安全缓存）
READ_ONLY_TOOLS = {
    "get_customer_info",
    "get_sales_lead",
    "get_contract",
    "search_customers",
    "get_user_info",
    "get_org_structure",
}

CACHE_TTL = 300  # 5 分钟


class ToolCache:
    """工具调用缓存"""

    @staticmethod
    def _cache_key(tool_name: str, args: dict, org_id: str) -> str:
        """生成缓存键 (P0-2: 必须包含 org_id 防止跨租户缓存命中)"""
        args_str = json.dumps(args, sort_keys=True, ensure_ascii=False)
        hash_val = hashlib.md5(args_str.encode()).hexdigest()
        return f"tool_cache:{org_id}:{tool_name}:{hash_val}"

    async def get_or_execute(
        self, tool_name: str, args: dict, executor: Callable, org_id: str = ""
    ) -> Any:
        """获取缓存或执行工具"""
        # 只缓存只读工具
        if tool_name not in READ_ONLY_TOOLS:
            return await executor()

        # P0-2: 无 org_id 时不使用缓存，防止跨租户泄露
        if not org_id:
            return await executor()

        cache_key = self._cache_key(tool_name, args, org_id)

        # 尝试从缓存获取
        cached = await cache_service.get(cache_key)
        if cached is not None:
            logger.debug(f"Tool cache hit: {tool_name}")
            return cached

        # 执行工具
        result = await executor()

        # 缓存结果
        await cache_service.set(cache_key, result, ttl=CACHE_TTL)

        return result


# 全局实例
tool_cache = ToolCache()
