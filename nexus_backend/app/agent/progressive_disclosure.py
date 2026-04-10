"""
渐进式知识披露系统 (Hermes-inspired Progressive Disclosure)

核心思想：不要一次性把所有知识塞进 context，而是分层按需加载。

三层披露：
  Tier 0 — 分类概览：只列出知识分类和条目数（~100 tokens）
  Tier 1 — 摘要列表：列出每条知识的标题+一句话描述（~500 tokens）
  Tier 2 — 完整内容：按需加载单条知识的完整内容（变长）

使用场景：
  - 组织业务规则（可能有几十条）
  - 知识库文档（可能有上百篇）
  - 工具使用说明（40+ 工具）
  - 审批流程模板
"""

import logging
import re

from app.core.database import supabase

logger = logging.getLogger(__name__)

# Token 预算：注入 context 的最大 token 数
TIER0_MAX_TOKENS = 200
TIER1_MAX_TOKENS = 800
TIER2_MAX_TOKENS = 3000

_CATEGORY_LABELS = {
    "business_rule": "业务规则",
    "policy": "组织准则",
    "knowledge": "知识库",
    "workflow": "审批流程",
    "faq": "常见问题",
    "product": "产品知识",
}


class ProgressiveDisclosure:
    """渐进式知识披露管理器。"""

    def __init__(self):
        self._category_cache: dict[str, list[dict]] = {}

    async def get_tier0_overview(
        self, org_id: str, categories: list[str] | None = None
    ) -> str:
        """Tier 0: 分类概览 — 最小 token 开销。

        返回格式：
        [可用知识分类]
        - 业务规则 (12条)
        - 审批流程 (5条)
        - 产品知识 (23条)
        输入 "展开 <分类名>" 查看详情。
        """
        try:
            # 查询各分类的条目数
            result = await supabase.rpc(
                "count_knowledge_by_category",
                {"p_org_id": org_id},
            ).execute()

            if not result.data:
                # Fallback: 直接查询 conversation_memories 表
                result = (
                    await supabase.table("conversation_memories")
                    .select("category")
                    .eq("org_id", org_id)
                    .execute()
                )
                if not result.data:
                    return ""

                # 手动统计
                counts: dict[str, int] = {}
                for row in result.data:
                    cat = row.get("category", "other")
                    counts[cat] = counts.get(cat, 0) + 1
            else:
                counts = {row["category"]: row["count"] for row in result.data}

            if not counts:
                return ""

            # 过滤指定分类
            if categories:
                counts = {k: v for k, v in counts.items() if k in categories}

            lines = ["[可用知识分类]"]
            for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
                label = _CATEGORY_LABELS.get(cat, cat)
                lines.append(f"- {label} ({count}条)")
            lines.append("如需查看某分类详情，请告诉我分类名。")

            overview = "\n".join(lines)
            logger.info(
                f"[Disclosure] Tier0 for org {org_id}: {len(counts)} categories"
            )
            return overview

        except Exception as e:
            logger.debug(f"[Disclosure] Tier0 failed: {e}")
            return ""

    async def get_tier1_summaries(
        self, org_id: str, category: str, limit: int = 20
    ) -> str:
        """Tier 1: 摘要列表 — 标题 + 一句话描述。

        返回格式：
        [业务规则 — 12条]
        1. 报销审批流程 — 500元以下直接审批，500元以上需部门经理
        2. 请假规则 — 年假需提前3天申请，病假需医院证明
        ...
        输入序号或关键词查看完整内容。
        """
        try:
            result = (
                await supabase.table("conversation_memories")
                .select("id, key, value")
                .eq("org_id", org_id)
                .eq("category", category)
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )

            if not result.data:
                return f"[{category}] 暂无内容"

            label = _CATEGORY_LABELS.get(category, category)
            lines = [f"[{label} — {len(result.data)}条]"]

            for i, row in enumerate(result.data, 1):
                key = row.get("key", "")
                value = row.get("value", "")
                # 截取第一句作为摘要
                summary = value[:80].split("。")[0].split("\n")[0]
                if len(value) > 80:
                    summary += "..."
                lines.append(f"{i}. {key} — {summary}")

            lines.append("输入序号或关键词查看完整内容。")

            text = "\n".join(lines)
            logger.info(f"[Disclosure] Tier1 for {category}: {len(result.data)} items")
            return text

        except Exception as e:
            logger.debug(f"[Disclosure] Tier1 failed: {e}")
            return ""

    async def get_tier2_full_content(self, org_id: str, category: str, key: str) -> str:
        """Tier 2: 完整内容 — 按需加载单条知识。"""
        try:
            result = (
                await supabase.table("conversation_memories")
                .select("key, value, metadata")
                .eq("org_id", org_id)
                .eq("category", category)
                .ilike("key", f"%{key}%")
                .limit(1)
                .execute()
            )

            if not result.data:
                return f"未找到匹配 '{key}' 的内容"

            row = result.data[0]
            content = row.get("value", "")

            # 截断过长内容
            if len(content) > TIER2_MAX_TOKENS * 4:  # ~4 chars per token
                content = content[: TIER2_MAX_TOKENS * 4] + "\n...(内容过长，已截断)"

            return f"[{row.get('key', key)}]\n{content}"

        except Exception as e:
            logger.debug(f"[Disclosure] Tier2 failed: {e}")
            return ""

    def select_tier_for_context(
        self,
        complexity: str,
        category_count: int,
        total_items: int,
    ) -> int:
        """根据查询复杂度和知识量，自动选择合适的披露层级。

        规则：
        - SIMPLE 查询 → Tier 0（只给概览，节省 token）
        - MODERATE + 少量知识(<10条) → Tier 1（直接给摘要）
        - MODERATE + 大量知识(>=10条) → Tier 0（先给概览）
        - COMPLEX/CRITICAL → Tier 1（给摘要，让 agent 按需深入）
        """
        if complexity == "simple":
            return 0
        if complexity == "moderate":
            return 1 if total_items < 10 else 0
        return 1  # complex/critical

    async def build_context_block(
        self,
        org_id: str,
        complexity: str = "moderate",
        relevant_categories: list[str] | None = None,
    ) -> str:
        """构建适合当前查询复杂度的知识上下文块。

        自动选择合适的披露层级，控制 token 预算。
        """
        try:
            # 先获取 Tier 0 概览来了解知识量
            overview = await self.get_tier0_overview(org_id, relevant_categories)
            if not overview:
                return ""

            # 解析条目总数
            total_items = sum(int(m) for m in re.findall(r"\((\d+)条\)", overview))

            tier = self.select_tier_for_context(
                complexity=complexity,
                category_count=overview.count("- "),
                total_items=total_items,
            )

            if tier == 0:
                return overview

            # Tier 1: 为相关分类生成摘要
            if relevant_categories:
                parts = []
                for cat in relevant_categories[:3]:  # 最多展开3个分类
                    summary = await self.get_tier1_summaries(org_id, cat, limit=10)
                    if summary:
                        parts.append(summary)
                return "\n\n".join(parts) if parts else overview

            return overview

        except Exception as e:
            logger.debug(f"[Disclosure] build_context_block failed: {e}")
            return ""


# 全局单例
progressive_disclosure = ProgressiveDisclosure()
