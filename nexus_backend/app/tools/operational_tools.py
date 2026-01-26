from .base_tool import BaseTool
from typing import Dict, Any
from app.core.database import supabase
from app.services.vector_service import vector_service

class PerformanceReportTool(BaseTool):
    name = "get_performance_report"
    description = "获取指定用户的详细绩效报告"

    parameters = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "用户UUID，若为空则获取当前用户"}
        }
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        target_id = args.get("user_id") or user_id
        user_res = supabase.table("users").select("*").eq("id", target_id).maybe_single().execute()
        if not user_res.data:
            return f"找不到 ID 为 {target_id} 的用户绩效数据。"
        
        user = user_res.data
        metrics_res = supabase.table("sales_metrics").select("*").eq("user_id", target_id).execute()
        report = f"用户: {user['name']}\n"
        report += f"当前得分: {user['score']} | 排名: {user['rank']} | 总奖金: ¥{user['total_bonus']}\n"
        report += "关键指标:\n"
        for m in metrics_res.data:
            report += f"- {m['metric_type']}: {m['value']}\n"
        return report

class CompanyStatsTool(BaseTool):
    name = "get_company_stats"
    description = "获取公司整体统计数据，如员工总人数、部门分布概况等"
    
    parameters = {
        "type": "object",
        "properties": {}
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        count_res = supabase.table("users").select("id", count="exact").execute()
        total_users = count_res.count if count_res.count is not None else 0
        dept_res = supabase.table("users").select("department").execute()
        depts = {}
        for u in dept_res.data:
            d = u.get("department", "未分配") or "未分配"
            depts[d] = depts.get(d, 0) + 1
        stats = f"公司总人数: {total_users} 人\n分布:\n"
        for d, c in depts.items(): stats += f"- {d}: {c} 人\n"
        return stats

class KnowledgeBaseTool(BaseTool):
    name = "query_knowledge_base"
    description = "查询企业知识库/向量数据库，获取公司政策、业务流程、文档等非结构化数据环境数据"
    
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词或问题"}
        },
        "required": ["query"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        query = args.get("query")
        return await vector_service.search(query, config=config)

class AwardBadgeTool(BaseTool):
    name = "award_badge"
    description = "为员工颁发荣誉徽章或奖励"
    
    parameters = {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "员工的唯一ID"},
            "badge_name": {"type": "string", "description": "徽章名称，如：销售冠军、拼命三郎"},
            "icon": {"type": "string", "description": "图标标识，如：trophy, rocket, fire"}
        },
        "required": ["user_id", "badge_name"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        target_id = args.get("user_id")
        badge_name = args.get("badge_name")
        icon = args.get("icon", "sparkles")
        supabase.table("badges").insert({"user_id": target_id, "name": badge_name, "icon": icon}).execute()
        supabase.table("notifications").insert({
            "user_id": target_id,
            "title": "荣获新徽章！",
            "content": f"老板为你颁发了「{badge_name}」徽章，继续加油！",
            "type": "success"
        }).execute()
        return f"成功为用户 {target_id} 颁发徽章: {badge_name}"
