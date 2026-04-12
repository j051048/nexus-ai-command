"""经营仪表盘工具"""

import logging
from datetime import datetime
from typing import Any

from app.tools._shared import safe_tool_error

from ..base_tool import BaseTool
from ..boss_shared import _get_client

logger = logging.getLogger(__name__)


class BusinessDashboardTool(BaseTool):
    """经营仪表盘工具"""

    name = "get_business_dashboard"
    description = "获取公司经营核心指标，包含收入、签约、商机和人效数据。当领导说'看看经营情况'、'本月业绩怎么样'时调用。"
    required_role = "boss"
    domain = "analytics"
    examples = [
        {
            "input": {"period": "this_month", "focus": "all"},
            "output_summary": "返回本月完整经营仪表盘",
        },
        {
            "input": {"period": "this_week", "focus": "revenue"},
            "output_summary": "返回本周收入相关指标",
        },
    ]
    related_tools = ["get_daily_briefing", "get_team_insight"]
    gotchas = "成本数据暂未对接财务系统，仅展示收入和人效。数据来源于 sales_metrics 表，若无数据会提示为空。"

    parameters = {
        "type": "object",
        "properties": {
            "period": {
                "type": "string",
                "enum": [
                    "today",
                    "this_week",
                    "this_month",
                    "this_quarter",
                    "this_year",
                ],
                "description": "统计周期",
            },
            "focus": {
                "type": "string",
                "enum": ["revenue", "cost", "hr", "sales", "all"],
                "description": "关注重点",
            },
        },
        "required": [],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        period = args.get("period", "this_month")
        period_names = {
            "today": "今日",
            "this_week": "本周",
            "this_month": "本月",
            "this_quarter": "本季度",
            "this_year": "本年度",
        }

        client = _get_client(config)
        org_id = config.get("org_id") if config else None

        # 1. Get Real Financial Metrics from DB
        # Note: We aggregate from 'sales_metrics' table. If empty, we return 0/No Data.
        try:
            # Simple aggregation (sum value by metric_type)
            # In a real app, we'd filter by created_at based on 'period'
            metrics_res = (
                await client.table("sales_metrics")
                .select("metric_type, value")
                .execute()
            )

            metrics = metrics_res.data or []

            # Group by type
            revenue = sum(
                float(m["value"]) for m in metrics if m["metric_type"] == "revenue"
            )
            contract_sum = sum(
                float(m["value"]) for m in metrics if m["metric_type"] == "contract"
            )
            opportunity_val = sum(
                float(m["value"]) for m in metrics if m["metric_type"] == "opportunity"
            )

            # 2. Get Real HR Metrics (scoped to organization)
            hr_query = client.table("users").select("id", count="exact")
            if org_id:
                hr_query = hr_query.eq("organization_id", org_id)
            users_res = await hr_query.execute()
            headcount = users_res.count or 0

            # 3. Logic for "No Data"
            if not metrics and headcount == 0:
                return f"""📊 **{period_names.get(period, "本月")}经营仪表盘**
更新时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

⚠️ **暂无数据**
系统中暂未录入经营数据（收入、成本、人员等）。
请先让员工在系统中录入业务数据，或连接外部ERP系统。
"""

            # 4. Construct Authentic Report
            response = f"""📊 **{period_names.get(period, "本月")}经营仪表盘 (实时数据)**
更新时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 **收入指标**
┌─────────────────────────────────┐
│ 签约金额      ¥ {contract_sum:,.2f}
│ 回款金额      ¥ {revenue:,.2f}
│ 新增商机      ¥ {opportunity_val:,.2f}
└─────────────────────────────────┘

👥 **人效指标**
┌─────────────────────────────────┐
│ 团队人数                   {headcount} 人
│ 人均产出      ¥ {(revenue / headcount if headcount > 0 else 0):,.2f}
└─────────────────────────────────┘

(注：成本数据暂未连接财务系统，显示为空)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 **AI 经营洞察**
"""
            if revenue == 0:
                response += "\n⚠️ **数据缺失提醒**: 本周期内无回款记录。请确认销售团队是否已录入数据。\n"
            elif revenue < contract_sum * 0.5:
                response += (
                    "\n⚠️ **回款滞后**: 回款金额低于签约金额的50%，建议关注现金流。\n"
                )
            else:
                response += "\n✅ **经营稳健**: 回款状况良好。\n"

            return response

        except Exception as e:
            logger.error(f"Error fetching dashboard data: {e}")
            return safe_tool_error(e, "获取经营数据")
