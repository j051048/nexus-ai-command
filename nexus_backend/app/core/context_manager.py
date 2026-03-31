"""
简化版上下文管理器 - 保留最近N条消息，删除旧消息
"""
import logging
from typing import List, Dict
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
        检查并修剪消息（如果超过限制）

        Args:
            conversation_id: 对话 ID

        Returns:
            是否执行了修剪
        """
        client = await self._get_client()

        # 1. 获取消息总数
        result = await client.table('conversation_memories') \
            .select('id', count='exact') \
            .eq('conversation_id', conversation_id) \
            .execute()

        total_count = result.count

        if total_count <= self.MAX_MESSAGES:
            return False  # 无需修剪

        # 2. 获取要删除的旧消息 ID
        messages_to_delete = total_count - self.MAX_MESSAGES

        old_messages = await client.table('conversation_memories') \
            .select('id') \
            .eq('conversation_id', conversation_id) \
            .order('created_at', desc=False) \
            .limit(messages_to_delete) \
            .execute()

        if not old_messages.data:
            return False

        # 3. 删除旧消息
        old_ids = [msg['id'] for msg in old_messages.data]

        await client.table('conversation_memories') \
            .delete() \
            .in_('id', old_ids) \
            .execute()

        logger.info(
            f"Trimmed {len(old_ids)} old messages from conversation {conversation_id}, "
            f"kept recent {self.MAX_MESSAGES}"
        )

        return True


# 全局实例
context_manager = SimpleContextManager()
