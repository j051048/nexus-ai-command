import uuid as _uuid
from typing import Any

from app.services.vector_service import vector_service
from app.tools._shared import safe_tool_error

from ._shared import _get_client
from .base_tool import BaseTool


class PerformanceReportTool(BaseTool):
    name = "get_performance_report"
    description = "获取指定用户的详细绩效报告，包括得分、排名、奖金和近期销售指标。当用户说'绩效报告'、'绩效数据'时调用。注意：此工具查个人绩效详情，团队整体用get_team_insight。"
    domain = "analytics"
    examples = [
        {"input": {}, "output_summary": "返回当前用户的绩效报告"},
        {"input": {"user_id": "uuid-xxx"}, "output_summary": "返回指定用户的绩效报告"},
    ]
    related_tools = ["get_team_insight", "get_company_stats", "get_business_dashboard"]
    gotchas = "不传user_id则查当前登录用户。user_id必须是有效的UUID格式。查团队整体绩效请用get_team_insight而非此工具。"

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

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        org_id = config.get("org_id") if config else None
        target_id = args.get("user_id") or user_id

        # Validate UUID format
        try:
            _uuid.UUID(target_id)
        except (ValueError, TypeError, AttributeError):
            return f"user_id '{target_id}' 不是有效的UUID格式。"

        query = client.table("users").select("*").eq("id", target_id)
        if org_id:
            query = query.eq("organization_id", org_id)
        user_res = await query.maybe_single().execute()
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
        report += f"当前得分: {user.get('score', 0)} | 排名: {user.get('rank', 0)} | 总奖金: ¥{user.get('total_bonus', 0)}\n"
        if metrics_res.data:
            total_revenue = sum(float(m.get("revenue", 0)) for m in metrics_res.data)
            total_leads = sum(int(m.get("leads_count", 0)) for m in metrics_res.data)
            report += f"近期营收合计: ¥{total_revenue:,.0f} | 线索合计: {total_leads}\n"
        else:
            report += "暂无销售指标数据\n"
        return report


class CompanyStatsTool(BaseTool):
    name = "get_company_stats"
    description = "获取公司整体统计数据，包括员工总人数和部门分布概况。当用户说'公司有多少人'、'员工总数'、'部门人数'时调用。注意：查经营数据（收入利润）用get_business_dashboard。"
    domain = "analytics"
    examples = [
        {"input": {}, "output_summary": "返回公司总人数和各部门人数分布"},
    ]
    related_tools = [
        "get_performance_report",
        "get_team_insight",
        "get_business_dashboard",
    ]
    gotchas = "只返回人力统计数据，不包含营收等经营数据。查经营数据请用get_business_dashboard。"

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
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
    description = "检索企业知识库中的政策、产品手册和业务文档。当用户问公司规定、产品参数、流程制度等事实性问题时调用。"
    domain = "knowledge"
    examples = [
        {
            "input": {"query": "报销流程"},
            "output_summary": "返回与报销流程相关的知识库内容",
        },
        {
            "input": {"query": "产品A技术参数"},
            "output_summary": "返回产品A的技术参数文档",
        },
    ]
    related_tools = ["get_performance_report", "get_company_stats"]
    gotchas = "基于向量语义搜索，查询词越具体结果越准确。返回结果包含引用来源。"

    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "搜索关键词或问题"}},
        "required": ["query"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        query = args.get("query")
        org_id = config.get("org_id") if config else None
        # P1: Grounding ensured by vector_service.search which now returns citations
        result = await vector_service.search(
            query, user_id, config=config, org_id=org_id
        )
        return result


class AwardBadgeTool(BaseTool):
    name = "award_badge"
    description = "为员工颁发荣誉徽章并发送通知。当用户说'颁发徽章'、'奖励员工'时调用。"
    domain = "hr"
    examples = [
        {
            "input": {"user_id": "uuid-xxx", "badge_name": "销售冠军"},
            "output_summary": "为指定员工颁发销售冠军徽章",
        },
        {
            "input": {"user_id": "uuid-xxx", "badge_name": "拼命三郎", "icon": "fire"},
            "output_summary": "颁发拼命三郎徽章并使用fire图标",
        },
    ]
    related_tools = ["get_performance_report", "get_team_insight"]
    gotchas = "user_id必须是有效的UUID格式。badge_name最长100字符。icon默认为sparkles，可选trophy、rocket、fire等。"

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

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        target_id = args.get("user_id")
        badge_name = args.get("badge_name", "")[:100]
        icon = args.get("icon", "sparkles")[:50]
        org_id = config.get("org_id") if config else None

        # Validate UUID format
        try:
            _uuid.UUID(target_id)
        except (ValueError, TypeError, AttributeError):
            return f"user_id '{target_id}' 不是有效的UUID格式，请检查员工ID。"

        client = _get_client(config)

        # 验证目标用户属于同一组织
        if org_id:
            check = (
                await client.table("users")
                .select("id")
                .eq("id", target_id)
                .eq("organization_id", org_id)
                .maybe_single()
                .execute()
            )
            if not check.data:
                return "❌ 未找到该员工或该员工不属于本组织。"

        try:
            badge_data = {"user_id": target_id, "name": badge_name, "icon": icon}
            if org_id:
                badge_data["organization_id"] = org_id
            await client.table("badges").insert(badge_data).execute()
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
            return safe_tool_error(e, "颁发徽章")
        return f"成功为用户 {target_id} 颁发徽章: {badge_name}"
