"""
P1-3: 记忆重要性评分系统
"""

import logging

logger = logging.getLogger(__name__)


class MemoryImportanceScorer:
    """记忆重要性评分"""

    BUSINESS_KEYWORDS = [
        "合同", "付款", "客户", "订单", "审批",
        "重要", "紧急", "关键", "必须", "deadline"
    ]

    async def score(self, memory: dict) -> float:
        """综合评分 0-1"""
        score = 0.0
        content = memory.get("content", "")

        # 1. 用户显式标记 (+0.4)
        if memory.get("user_marked_important"):
            score += 0.4

        # 2. 引用频率 (+0.3)
        ref_count = memory.get("reference_count", 0)
        score += min(ref_count / 10, 0.3)

        # 3. 业务关键词 (+0.3)
        keyword_count = sum(1 for kw in self.BUSINESS_KEYWORDS if kw in content)
        score += min(keyword_count * 0.1, 0.3)

        return min(score, 1.0)

    async def prioritize_memories(self, memories: list[dict]) -> list[dict]:
        """按重要性排序"""
        for mem in memories:
            mem["importance"] = await self.score(mem)

        return sorted(memories, key=lambda x: x.get("importance", 0), reverse=True)


# 全局实例
memory_scorer = MemoryImportanceScorer()
