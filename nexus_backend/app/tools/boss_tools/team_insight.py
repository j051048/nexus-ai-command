"""团队洞察工具"""

import logging
from datetime import datetime
from typing import Any

from ..base_tool import BaseTool
from ..boss_shared import _get_client

logger = logging.getLogger(__name__)


class TeamInsightTool(BaseTool):
    """团队洞察工具"""

    name = "get_team_insight"
    description = "获取团队综合洞察报告，包含绩效分布、风险预警和人员排名。当用户说'团队情况'、'团队分析'时调用。"
    required_role = "manager"
    domain = "analytics"
    examples = [
        {
            "input": {"insight_type": "performance"},
            "output_summary": "返回团队绩效分布及排名",
        },
        {
            "input": {"insight_type": "risk"},
            "output_summary": "返回需关注的低绩效人员列表",
        },
    ]
    related_tools = [
        "get_employee_profile",
        "create_performance_review",
        "get_daily_briefing",
    ]
    gotchas = "管理者只能查看本部门数据，老板和创始人可查看全组织。绩效基于 users 表的 score 字段。"

    parameters = {
        "type": "object",
        "properties": {
            "insight_type": {
                "type": "string",
                "enum": ["performance", "risk", "engagement", "growth"],
                "description": "洞察类型",
            }
        },
        "required": [],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = config.get("org_id") if config else None

        # F4: Check if user is manager (not boss) - filter to own department only
        from app.services.chat_service import ChatService

        user_role = (
            await ChatService._get_cached_user_role(user_id, db_client=client)
            if hasattr(ChatService, "_get_cached_user_role")
            else "employee"
        )

        if user_role == "manager":
            # Get manager's department
            dept_res = (
                await client.table("users")
                .select("department")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
            user_dept = dept_res.data.get("department") if dept_res.data else None
            if user_dept:
                # Filter team to same department
                team_query = (
                    client.table("users")
                    .select("id, name, role, department, position, status, score")
                    .eq("department", user_dept)
                )
                if org_id:
                    team_query = team_query.eq("organization_id", org_id)
                team_res = await team_query.execute()
            else:
                team_query = client.table("users").select(
                    "id, name, role, department, position, status, score"
                )
                if org_id:
                    team_query = team_query.eq("organization_id", org_id)
                team_res = await team_query.execute()
        else:
            # Boss/founder sees all within their organization
            team_query = client.table("users").select(
                "id, name, role, department, position, status, score"
            )
            if org_id:
                team_query = team_query.eq("organization_id", org_id)
            team_res = await team_query.execute()

        team = team_res.data or []
        total_count = len(team)

        if total_count == 0:
            return f"""👥 **团队洞察报告**
📅 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

⚠️ **暂无数据** — 系统中暂未录入员工信息。
"""

        # 基于真实数据计算绩效分布
        s_level = [u for u in team if float(u.get("score", 0)) >= 95]
        a_level = [u for u in team if 85 <= float(u.get("score", 0)) < 95]
        b_level = [u for u in team if 70 <= float(u.get("score", 0)) < 85]
        c_level = [u for u in team if float(u.get("score", 0)) < 70]

        def pct(n):
            return f"{n / total_count * 100:.0f}%" if total_count > 0 else "0%"

        def bar(n, total, width=10):
            filled = round(n / total * width) if total > 0 else 0
            return "█" * filled + "░" * (width - filled)

        response = f"""👥 **团队洞察报告**
📅 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**团队规模**: {total_count} 人

📊 **绩效分布**

  S级(95+)  {bar(len(s_level), total_count)}  {pct(len(s_level))} ({len(s_level)}人)  🌟 明星员工
  A级(85-94) {bar(len(a_level), total_count)}  {pct(len(a_level))} ({len(a_level)}人) ✅ 骨干力量
  B级(70-84) {bar(len(b_level), total_count)}  {pct(len(b_level))} ({len(b_level)}人) 📈 待提升
  C级(<70)  {bar(len(c_level), total_count)}  {pct(len(c_level))} ({len(c_level)}人)  ⚠️ 需关注

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        # Top performers (real data)
        sorted_team = sorted(team, key=lambda u: float(u.get("score", 0)), reverse=True)
        top3 = sorted_team[:3]

        if top3:
            response += "\n🌟 **绩效前三**\n\n"
            medals = ["🥇", "🥈", "🥉"]
            for i, p in enumerate(top3):
                response += (
                    f"{medals[i]} {p.get('name', '员工')}: {p.get('score', 0)}分\n"
                )

        # Low performers (real data) — need attention
        if c_level:
            response += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n⚠️ **需关注人员** ({len(c_level)}人)\n\n"
            for u in c_level[:3]:
                response += (
                    f"- **{u.get('name', '员工')}**: 绩效 {u.get('score', 0)} 分\n"
                )
            if len(c_level) > 3:
                response += f"  ... 还有 {len(c_level) - 3} 人\n"

        response += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 需要我帮您安排与某位员工的谈话吗？
"""

        return response
