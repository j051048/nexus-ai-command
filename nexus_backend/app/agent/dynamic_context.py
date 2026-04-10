"""
P0-5: 动态上下文管理器
"""

import logging
import re

from app.agent.state import QueryComplexity
from app.core.database import supabase

logger = logging.getLogger(__name__)


class DynamicContextManager:
    """动态上下文管理器"""

    def calculate_window_size(self, complexity: QueryComplexity) -> int:
        """根据任务复杂度动态调整窗口"""
        return {
            QueryComplexity.SIMPLE: 5,
            QueryComplexity.MODERATE: 10,
            QueryComplexity.COMPLEX: 20,
            QueryComplexity.CRITICAL: 30,
        }.get(complexity, 10)

    async def inject_business_context(
        self, user_id: str, query: str, org_id: str = "default"
    ) -> str:
        """自动注入相关业务数据"""
        context_parts = []

        try:
            # 1. 提取客户名
            customer_match = re.search(r"客户[：:]\s*([^\s，,。.]+)", query)
            if customer_match:
                customer_name = customer_match.group(1)
                result = (
                    await supabase.table("customers")
                    .select("name, stage, last_contact_date")
                    .eq("org_id", org_id)
                    .ilike("name", f"%{customer_name}%")
                    .limit(1)
                    .execute()
                )

                if result.data:
                    c = result.data[0]
                    context_parts.append(
                        f"客户 {c['name']}: 阶段={c.get('stage', '未知')}, "
                        f"最后联系={c.get('last_contact_date', '未知')}"
                    )

            # 2. 提取合同号
            contract_match = re.search(r"合同[号編]?[：:]\s*([A-Z0-9-]+)", query)
            if contract_match:
                contract_no = contract_match.group(1)
                result = (
                    await supabase.table("contracts")
                    .select("contract_number, status, end_date")
                    .eq("org_id", org_id)
                    .eq("contract_number", contract_no)
                    .limit(1)
                    .execute()
                )

                if result.data:
                    c = result.data[0]
                    context_parts.append(
                        f"合同 {c['contract_number']}: 状态={c.get('status', '未知')}, "
                        f"到期={c.get('end_date', '未知')}"
                    )

            return "\n".join(context_parts) if context_parts else ""

        except Exception as e:
            logger.error(f"Business context injection failed: {e}")
            return ""


# 全局实例
context_manager = DynamicContextManager()
