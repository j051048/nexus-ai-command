"""
记忆重要性评分系统 — 艾宾浩斯遗忘曲线 + 强化学习 + 静态因子

设计原则：
1. 时间衰减：基于艾宾浩斯遗忘曲线，未被访问的记忆逐渐衰减
2. 间隔重复：每次被检索命中，强化记忆保持度（模拟间隔重复效应）
3. 静态因子：用户标记、引用频率、业务关键词仍然作为基础分
4. 最低保持：防止有价值的旧记忆（如合同、客户关系）完全消失
"""

import logging
import math
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# 艾宾浩斯衰减参数
_DECAY_HALF_LIFE_DAYS = 14.0  # 14 天半衰期（ln2 / decay_rate）
_MIN_RETENTION = 0.15  # 最低保持 15%，防止有价值旧记忆完全消失
_REINFORCEMENT_PER_ACCESS = 0.05  # 每次被检索命中强化 5%
_MAX_REINFORCEMENT = 0.20  # 强化上限 20%

# 业务关键词（用于静态评分）
_BUSINESS_KEYWORDS = [
    "合同",
    "付款",
    "客户",
    "订单",
    "审批",
    "重要",
    "紧急",
    "关键",
    "必须",
    "deadline",
    "签约",
    "预算",
    "报价",
    "招标",
]

# 高价值分类（这些分类的记忆衰减更慢）
_HIGH_VALUE_CATEGORIES = {"completed_task", "tool_correction", "user_preference", "skill"}
_HIGH_VALUE_HALF_LIFE_MULTIPLIER = 2.0  # 高价值记忆半衰期翻倍


class MemoryImportanceScorer:
    """记忆重要性评分 — 融合时间衰减 + 静态因子 + 间隔强化"""

    async def score(self, memory: dict) -> float:
        """综合评分 0-1，融合静态基础分、时间衰减和强化加成"""
        base = self._static_score(memory)
        decay = self._time_decay(memory)
        reinforcement = self._reinforcement_bonus(memory)
        final = base * decay + reinforcement
        return round(min(max(final, 0.0), 1.0), 4)

    def _static_score(self, memory: dict) -> float:
        """静态基础分（不考虑时间）"""
        score = 0.0
        content = str(memory.get("content", "") or memory.get("value", ""))

        # 1. 用户显式标记 (+0.4)
        if memory.get("user_marked_important"):
            score += 0.4

        # 2. 引用频率 (+0.3)
        ref_count = memory.get("reference_count", 0) or memory.get("access_count", 0) or 0
        score += min(ref_count / 10, 0.3)

        # 3. 业务关键词 (+0.3)
        keyword_count = sum(1 for kw in _BUSINESS_KEYWORDS if kw in content)
        score += min(keyword_count * 0.1, 0.3)

        # 4. 原始 importance 字段（如果有，作为锚点）
        original_importance = memory.get("importance")
        if isinstance(original_importance, int | float) and original_importance > 0:
            # 将原始 importance 与计算值加权融合
            score = 0.4 * original_importance + 0.6 * score

        return min(score, 1.0)

    def _time_decay(self, memory: dict) -> float:
        """艾宾浩斯遗忘曲线：retention = e^(-t/S)

        - S（稳定性）= half_life * 1.44（换算为自然衰减常数）
        - 高价值分类的半衰期翻倍
        - 最低不低于 _MIN_RETENTION
        """
        # 优先使用 last_accessed_at（表示"最近一次被回忆"）
        last_ts = memory.get("last_accessed_at") or memory.get("updated_at") or memory.get("created_at")
        if not last_ts:
            return 1.0

        try:
            last_dt = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=UTC)
            days_elapsed = (datetime.now(UTC) - last_dt).total_seconds() / 86400.0

            # 高价值分类半衰期翻倍
            half_life = _DECAY_HALF_LIFE_DAYS
            category = memory.get("category", "")
            if category in _HIGH_VALUE_CATEGORIES:
                half_life *= _HIGH_VALUE_HALF_LIFE_MULTIPLIER

            # 用户标记重要的记忆半衰期也翻倍
            if memory.get("user_marked_important"):
                half_life *= _HIGH_VALUE_HALF_LIFE_MULTIPLIER

            # e^(-t / (half_life * 1.44))  → 1.44 = 1/ln(2)
            stability = half_life * 1.4427  # 1/ln(2) ≈ 1.4427
            decay = math.exp(-days_elapsed / stability)
            return max(decay, _MIN_RETENTION)
        except Exception:
            return 1.0

    def _reinforcement_bonus(self, memory: dict) -> float:
        """间隔重复效应：每次被检索命中，额外加分

        模拟 Spaced Repetition：被多次"回忆"的记忆更不容易遗忘
        """
        access_count = memory.get("access_count", 0) or 0
        return min(access_count * _REINFORCEMENT_PER_ACCESS, _MAX_REINFORCEMENT)

    async def prioritize_memories(self, memories: list[dict]) -> list[dict]:
        """按重要性排序（融合衰减后的动态分数）"""
        for mem in memories:
            mem["effective_importance"] = await self.score(mem)

        return sorted(
            memories,
            key=lambda x: x.get("effective_importance", 0),
            reverse=True,
        )

    async def should_forget(self, memory: dict, threshold: float = 0.08) -> bool:
        """判断一条记忆是否应该被遗忘（低于阈值）

        用于 memory_lifecycle 的定期清理。
        用户显式标记的记忆永远不会被建议遗忘。
        """
        if memory.get("user_marked_important"):
            return False
        score = await self.score(memory)
        return score < threshold


# 全局实例
memory_scorer = MemoryImportanceScorer()
