"""
Context micro-compaction (Claude Code Best Practice)
Remove old tool outputs without calling LLM API - zero cost optimization
"""

from datetime import datetime, timedelta
from langchain_core.messages import BaseMessage, ToolMessage


class MicroCompressor:
    """微压缩：移除旧工具输出，零成本优化"""

    def __init__(self, retention_minutes: int = 5):
        self.retention_minutes = retention_minutes

    def compress(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        """移除 N 分钟前的工具输出"""
        cutoff_time = datetime.now() - timedelta(minutes=self.retention_minutes)

        compressed = []
        for msg in messages:
            # 保留非工具消息
            if not isinstance(msg, ToolMessage):
                compressed.append(msg)
                continue

            # 保留最近的工具输出
            if hasattr(msg, 'timestamp'):
                if msg.timestamp > cutoff_time:
                    compressed.append(msg)
            else:
                # 没有 timestamp 的保留（兼容旧消息）
                compressed.append(msg)

        return compressed
