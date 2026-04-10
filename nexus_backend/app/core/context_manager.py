"""
简化版上下文管理器 - 保留最近N条消息，删除旧消息
"""

import logging

from app.core.supabase import get_supabase_client

logger = logging.getLogger(__name__)


class SimpleContextManager:
    """简单的上下文管理器 - 只做消息修剪"""

    MAX_MESSAGES = 50  # 保留最近 50 条消息

    def __init__(self):
        self.supabase = None

    async def _get_client(self):
        """获取 Supabase 客户端"""
        if not self.supabase:
            self.supabase = await get_supabase_client()
        return self.supabase

    async def trim_if_needed(self, conversation_id: str) -> bool:
        """
        【已废弃 - 危险操作拦截】
        原逻辑会物理删除早期的用户对话。该行为已被紧急拦截修复！
        现在此方法仅做兼容性保留，不会删除任何数据，始终返回 False。
        请在组装 LLM Prompt 时改为使用 get_recent_messages 进行安全筛选。
        """
        logger.warning(
            f"trim_if_needed was called for {conversation_id} but ignored. Physical deletion of chats is strictly prohibited."
        )
        return False

    async def get_recent_messages(
        self, conversation_id: str, limit: int = None
    ) -> list[dict]:
        """
        安全的上下文滑动窗口：获取最近 N 条消息记录，以组装 Prompt

        Args:
            conversation_id: 对话 ID
            limit: 获取消息的最大条数，默认使用类的 MAX_MESSAGES (50条)

        Returns:
            排好序的最近消息列表（按时间顺序从前往后）
        """
        client = await self._get_client()
        fetch_limit = limit or self.MAX_MESSAGES

        result = (
            await client.table("conversation_memories")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .limit(fetch_limit)
            .execute()
        )

        if not result.data:
            return []

        # 根据 DESC=True 获取的是最新 N 条，需反转以恢复聊天时间顺序
        return sorted(result.data, key=lambda x: x.get("created_at", ""))


# 全局实例
context_manager = SimpleContextManager()
