import uuid as _uuid
from typing import Any

from app.core.database import supabase
from app.services.vector_service import vector_service

from .base_tool import BaseTool


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


class PerformanceReportTool(BaseTool):
    name = "get_performance_report"
    description = "获取指定用户的详细绩效报告。当用户说'绩效报告'、'绩效数据'时调用。注意：此工具查个人绩效详情，团队整体用 get_team_insight。"

    parameters = {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "用户UUID，若为空则获取当前用户",
            }
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        target_id = args.get("user_id") or user_id

        # Validate UUID format
        try:
            _uuid.UUID(target_id)
        except (ValueError, TypeError, AttributeError):
            return f"user_id '{target_id}' 不是有效的UUID格式。"

        user_res = await client.table("users").select("*").eq("id", target_id).maybe_single().execute()
        if not user_res.data:
            return f"找不到 ID 为 {target_id} 的用户绩效数据。"

        user = user_res.data
        try:
            metrics_res = (
                await client.table("sales_metrics")
                .select("*")
                .eq("user_id", target_id)
                .order("date", desc=True)
                .limit(30)
                .execute()
            )
        except Exception:
            metrics_res = type("R", (), {"data": []})()

        report = f"用户: {user.get('name', '未知')}\n"
        report += (
            f"当前得分: {user.get('score', 0)} | 排名: {user.get('rank', 0)} | 总奖金: ¥{user.get('total_bonus', 0)}\n"
        )
        if metrics_res.data:
            total_revenue = sum(float(m.get("revenue", 0)) for m in metrics_res.data)
            total_leads = sum(int(m.get("leads_count", 0)) for m in metrics_res.data)
            report += f"近期营收合计: ¥{total_revenue:,.0f} | 线索合计: {total_leads}\n"
        else:
            report += "暂无销售指标数据\n"
        return report


class CompanyStatsTool(BaseTool):
    name = "get_company_stats"
    description = "获取公司整体统计数据，如员工总人数、部门分布概况等。当用户说'公司有多少人'、'员工总数'、'部门人数'时调用。注意：查经营数据（收入利润）用 get_business_dashboard。"

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        import asyncio

        client = _get_client(config)
        org_id = config.get("org_id") if config else None

        # Build org-scoped queries
        count_query = client.table("users").select("id", count="exact")
        dept_query = client.table("users").select("department")
        if org_id:
            count_query = count_query.eq("organization_id", org_id)
            dept_query = dept_query.eq("organization_id", org_id)

        # Parallel execution (eliminates serial wait)
        count_res, dept_res = await asyncio.gather(
            count_query.execute(),
            dept_query.execute(),
        )
        total_users = count_res.count if count_res.count is not None else 0
        depts = {}
        for u in dept_res.data:
            d = u.get("department", "未分配") or "未分配"
            depts[d] = depts.get(d, 0) + 1
        stats = f"公司总人数: {total_users} 人\n分布:\n"
        for d, c in depts.items():
            stats += f"- {d}: {c} 人\n"
        return stats


class KnowledgeBaseTool(BaseTool):
    name = "query_knowledge_base"
    description = "查询企业知识库，检索公司政策、产品手册、业务文档等内容。当用户问公司规定、产品参数、流程制度等事实性问题时调用。"

    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "搜索关键词或问题"}},
        "required": ["query"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        query = args.get("query")
        org_id = config.get("org_id") if config else None
        # P1: Grounding ensured by vector_service.search which now returns citations
        result = await vector_service.search(query, user_id, config=config, org_id=org_id)
        return result


class AwardBadgeTool(BaseTool):
    name = "award_badge"
    description = "为员工颁发荣誉徽章或奖励"

    parameters = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "员工的唯一ID"},
            "badge_name": {
                "type": "string",
                "maxLength": 100,
                "description": "徽章名称，如：销售冠军、拼命三郎",
            },
            "icon": {
                "type": "string",
                "maxLength": 50,
                "description": "图标标识，如：trophy, rocket, fire",
            },
        },
        "required": ["user_id", "badge_name"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        target_id = args.get("user_id")
        badge_name = args.get("badge_name", "")[:100]
        icon = args.get("icon", "sparkles")[:50]

        # Validate UUID format
        try:
            _uuid.UUID(target_id)
        except (ValueError, TypeError, AttributeError):
            return f"user_id '{target_id}' 不是有效的UUID格式，请检查员工ID。"

        client = _get_client(config)
        try:
            await client.table("badges").insert({"user_id": target_id, "name": badge_name, "icon": icon}).execute()
            await (
                client.table("notifications")
                .insert(
                    {
                        "user_id": target_id,
                        "title": "荣获新徽章！",
                        "content": f"老板为你颁发了「{badge_name}」徽章，继续加油！",
                        "type": "success",
                    }
                )
                .execute()
            )
        except Exception as e:
            return f"❌ 颁发徽章失败: {str(e)}"
        return f"成功为用户 {target_id} 颁发徽章: {badge_name}"
