"""每日简报工具 - AI 主动汇报"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.ai_service import AIService

from ..base_tool import BaseTool
from ..boss_shared import _get_client

logger = logging.getLogger(__name__)


class DailyBriefingTool(BaseTool):
    """每日简报工具 - AI 主动汇报"""

    name = "get_daily_briefing"
    description = "获取每日工作简报，包含待审批事项、经营数据和风险预警。当领导说'今天有什么事'、'汇报一下'时调用。"
    required_role = "boss"
    domain = "schedule"
    examples = [
        {
            "input": {"briefing_type": "full"},
            "output_summary": "返回完整的每日简报（审批、业绩、预警）",
        },
        {
            "input": {"briefing_type": "approvals_only"},
            "output_summary": "仅返回待审批事项列表及AI建议",
        },
    ]
    related_tools = ["smart_approve", "get_business_dashboard", "get_team_insight"]
    gotchas = "金额大于5000的审批项会调用大模型生成建议，响应可能稍慢。"

    parameters = {
        "type": "object",
        "properties": {
            "briefing_type": {
                "type": "string",
                "enum": ["full", "approvals_only", "alerts_only", "performance"],
                "description": "简报类型: full(完整), approvals_only(仅审批), alerts_only(仅预警), performance(业绩)",
            }
        },
        "required": [],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = config.get("org_id") if config else None
        # 获取待审批数量
        pending_res = (
            await client.table("approval_requests")
            .select("*, users:submitted_by(name)")
            .eq("status", "pending")
            .order("amount", desc=True)
            .limit(5)
            .execute()
        )

        pending_list = pending_res.data or []
        pending_count = len(pending_list)

        # 获取已自动处理数量（今日已审批的）
        try:
            today_start = (
                datetime.now(UTC).replace(hour=0, minute=0, second=0).isoformat()
            )
            auto_res = (
                await client.table("approval_requests")
                .select("count", count="exact")
                .eq("status", "approved")
                .gte("updated_at", today_start)
                .execute()
            )
            auto_processed = auto_res.count or 0
        except Exception:
            auto_processed = 0

        # 获取团队绩效
        team_query = (
            client.table("users")
            .select("name, score, total_bonus")
            .order("score", desc=True)
            .limit(3)
        )
        if org_id:
            team_query = team_query.eq("organization_id", org_id)
        team_res = await team_query.execute()
        top_performers = team_res.data or []

        # 计算总奖金
        total_bonus = sum(float(p.get("total_bonus", 0)) for p in top_performers)

        now = datetime.now()
        greeting = (
            "早上好" if now.hour < 12 else "下午好" if now.hour < 18 else "晚上好"
        )

        response = f"""☀️ **{greeting}，老板！**
📅 {now.strftime("%Y年%m月%d日 %A")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        if auto_processed > 0:
            response += f"""✅ **今日已处理** {auto_processed} 件事务

"""
        else:
            response += """ℹ️ **今日暂无已处理事务**

"""

        if pending_count > 0:
            response += f"""⏳ **需您决策** {pending_count} 件

"""
            type_icons = {"expense": "💰", "leave": "🏖️", "purchase": "🛒"}

            for i, req in enumerate(pending_list, 1):
                icon = type_icons.get(req.get("type"), "📋")
                user_name = (
                    req.get("users", {}).get("name", "员工")
                    if isinstance(req.get("users"), dict)
                    else "员工"
                )
                amount = float(req.get("amount", 0))
                req_type = req.get("type", "申请")

                # AI 建议
                if amount > 5000 and i <= 2:
                    try:
                        suggestion = await AIService.call_llm(
                            f"审批请求: {req.get('description', req_type)}, 金额: ¥{amount:,.2f}, 申请人: {user_name}",
                            "你是企业财务审核专家。简短给出审批建议（1句话），以emoji开头。",
                        )
                        suggestion = f"🤖 {suggestion}"
                    except Exception:
                        suggestion = (
                            "⚠️ 建议详细审核（金额较大）"
                            if amount > 20000
                            else "✅ 建议批准"
                        )
                elif amount < 5000:
                    suggestion = "✅ 建议批准（金额合理）"
                elif amount > 20000:
                    suggestion = "⚠️ 建议详细审核（金额较大）"
                else:
                    suggestion = "✅ 建议批准"

                response += f"""**{i}️⃣ {icon} {user_name} - {req_type}**
   金额: ¥{amount:,.2f}
   AI建议: {suggestion}

"""

            response += """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 **快捷操作**
- 说「全部批了」→ 一键批准全部
- 说「第1个批，第2个不批」→ 分别处理
- 说「金额小于5000的都批」→ 条件审批
- 说「委托给张三」→ 委托审批

"""
        else:
            response += """🎉 **太棒了！当前没有待处理事项**

"""

        # 添加经营数据 - 查询真实数据 (从 customers 表)
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%dT00:00:00")
        org_id = config.get("org_id") if config else None

        # 查询本周新增客户/商机
        try:
            query = (
                client.table("customers")
                .select("*", count="exact")
                .gte("created_at", week_start)
            )
            if org_id:
                query = query.eq("organization_id", org_id)
            leads_res = await query.execute()
            new_leads = leads_res.count or len(leads_res.data or [])
        except Exception:
            new_leads = 0

        # 查询本周成交客户
        try:
            query = (
                client.table("customers")
                .select("estimated_value")
                .eq("stage", "customer")
                .gte("updated_at", week_start)
            )
            if org_id:
                query = query.eq("organization_id", org_id)
            won_res = await query.execute()
            won_count = len(won_res.data or [])
            won_amount = sum(
                float(d.get("estimated_value", 0)) for d in (won_res.data or [])
            )
        except Exception:
            won_count = 0
            won_amount = 0

        response += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **经营快报**

**本周业绩**
- 新增商机: {new_leads} 个
- 成交订单: {won_count} 个（¥{won_amount:,.0f}）
- 团队激励: ¥{total_bonus:,.0f}

**Top 3 员工**
"""

        medals = ["🥇", "🥈", "🥉"]
        for i, p in enumerate(top_performers):
            response += f"{medals[i]} {p.get('name', '员工')}: {p.get('score', 0)}分\n"

        # 查询真实风险预警 (从 customers 表)
        risk_alerts = []
        try:
            thirty_days_ago = (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
            query = (
                client.table("customers")
                .select("name, company, updated_at")
                .lt("updated_at", thirty_days_ago)
                .in_("stage", ["prospect", "opportunity"])
                .limit(3)
            )
            if org_id:
                query = query.eq("organization_id", org_id)
            stale_res = await query.execute()
            for cust in stale_res.data or []:
                updated = datetime.fromisoformat(cust["updated_at"][:19])
                days_stale = (now - updated).days
                display_name = cust.get("company") or cust.get("name", "未知客户")
                risk_alerts.append(f"- {display_name}：{days_stale}天未推进，建议跟进")
        except Exception as e:
            logger.debug("客户跟进风险查询失败: %s", e)

        try:
            expiring_res = (
                await client.table("contracts")
                .select("title, end_date")
                .gte("end_date", now.strftime("%Y-%m-%d"))
                .lte("end_date", (now + timedelta(days=7)).strftime("%Y-%m-%d"))
                .limit(3)
                .execute()
            )
            for c in expiring_res.data or []:
                days_left = (
                    datetime.strptime(c["end_date"][:10], "%Y-%m-%d") - now
                ).days
                risk_alerts.append(f"- {c['title']}：合同即将到期（剩{days_left}天）")
        except Exception as e:
            logger.debug("合同到期风险查询失败: %s", e)

        if risk_alerts:
            response += "\n**⚠️ 风险预警**\n"
            response += "\n".join(risk_alerts)
        else:
            response += "\n✅ **当前无风险预警**"

        response += """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 有什么需要我帮您处理的吗？
"""

        return response
