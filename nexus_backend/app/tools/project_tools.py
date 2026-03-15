import logging
import uuid as _uuid
from datetime import datetime, timedelta
from typing import Any

from .base_tool import BaseTool
from ._shared import _get_client

logger = logging.getLogger(__name__)


class ProjectListTool(BaseTool):
    name = "get_projects"
    description = "获取当前所有进行中的项目列表，用于关联后续的事件记录"

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        # Check role to filter projects? For now, list all accessible via RLS
        result = await client.table("projects").select("id, name, stage, progress").execute()
        if not result.data:
            return "暂无进行中的项目。"
        items = [
            f"ID: {p['id']} | 名称: {p['name']} | 状态: {p.get('stage', '未知')} | 进度: {p.get('progress', 0)}%"
            for p in result.data
        ]
        return "项目清单：\n" + "\n".join(items)


class CreateProjectTool(BaseTool):
    name = "create_project"
    description = "创建一个新的项目立项。当用户说'帮我新建一个XXX项目'时使用此工具。"

    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "项目名称"},
            "description": {"type": "string", "description": "项目背景描述"},
            "status": {
                "type": "string",
                "description": "初始状态 (planning, in_progress)",
                "default": "planning",
            },
        },
        "required": ["name"],
    }

    required_role = "all"

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        name = args.get("name")
        description = args.get("description", "")
        status = args.get("status", "planning")

        try:
            data = {
                "name": name,
                "description": description,
                "user_id": user_id,
                "stage": status,
                "progress": 0,
            }
            # Include organization_id for RLS org isolation
            org_id = config.get("org_id") if config else None
            if org_id:
                data["organization_id"] = org_id

            client = _get_client(config)
            res = await client.table("projects").insert(data).execute()
            if res.data:
                pid = res.data[0]["id"]
                return f"✅ 项目 '{name}' 已成功立项 (ID: {pid})！您可以继续添加项目事件或里程碑。"
            return "创建失败。"
        except Exception as e:
            return f"系统错误: {str(e)}"


class CreateEventTool(BaseTool):
    name = "create_project_event"
    description = "在指定的项目中创建一个新的进度事件或关键节点（如：请客吃饭、技术突破、签署合同）"

    parameters = {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "string",
                "description": "项目UUID (可先调用 get_projects 获取)",
            },
            "title": {"type": "string", "description": "事件标题，如：庆功晚宴"},
            "content": {
                "type": "string",
                "description": "事件详细描述，包括地点、参与人等",
            },
            "event_type": {
                "type": "string",
                "enum": ["milestone", "meeting", "dinner", "task"],
                "description": "事件类型",
            },
        },
        "required": ["project_id", "title", "content", "event_type"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        project_id = args.get("project_id")
        title = args.get("title")
        content = args.get("content")
        event_type = args.get("event_type")

        # Validate UUID format
        try:
            _uuid.UUID(project_id)
        except (ValueError, TypeError, AttributeError):
            return f"project_id '{project_id}' 不是有效的UUID格式。"

        # Ensure project_timeline table exists (it might be missing in migration, so we should allow fallback or catch error)
        # Assuming table exists or we need to add it to migration.
        # Check migration: I only added `projects` table. I did NOT add `project_timeline`.
        # I MUST add project_timeline table.
        try:
            client = _get_client(config)
            result = (
                await client.table("project_timeline")
                .insert(
                    {
                        "project_id": project_id,
                        "title": title,
                        "content": content,
                        "event_type": event_type,
                    }
                )
                .execute()
            )

            if result.data:
                return f"成功在项目中创建了事件: {title}。"
        except Exception as e:
            return f"创建事件失败: {str(e)}"
        return "创建失败，请核对项目 ID 是否正确。"


class WeeklyReportTool(BaseTool):
    """AI 周报/日报自动起草"""

    name = "generate_weekly_report"
    description = (
        "自动生成本周工作周报或日报，汇总项目进度、完成任务和下周计划。当用户说'帮我写周报'、'生成日报'时调用。"
    )
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "report_type": {
                "type": "string",
                "enum": ["daily", "weekly"],
                "description": "报告类型：日报或周报",
            }
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        from app.services.ai_service import AIService

        report_type = args.get("report_type", "weekly")
        client = _get_client(config)
        now = datetime.now()

        if report_type == "daily":
            period_start = now.strftime("%Y-%m-%dT00:00:00")
            report_type_name = "日报"
        else:
            period_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%dT00:00:00")
            report_type_name = "周报"

        # 聚合任务数据
        tasks_data = []
        try:
            tasks_res = (
                await client.table("oa_tasks")
                .select("title, status, priority")
                .eq("assignee_id", user_id)
                .gte("updated_at", period_start)
                .execute()
            )
            tasks_data = tasks_res.data or []
        except Exception as e:
            logger.debug("任务数据查询失败: %s", e)

        # 聚合项目事件
        events_data = []
        try:
            events_res = (
                await client.table("project_timeline")
                .select("title, event_type, content")
                .gte("created_at", period_start)
                .limit(20)
                .execute()
            )
            events_data = events_res.data or []
        except Exception as e:
            logger.debug("项目事件查询失败: %s", e)

        # 查询用户项目
        projects_data = []
        try:
            proj_res = await client.table("projects").select("name, stage, progress").eq("user_id", user_id).execute()
            projects_data = proj_res.data or []
        except Exception as e:
            logger.debug("用户项目查询失败: %s", e)

        prompt = (
            f"请根据以下工作数据生成{report_type_name}:\n\n"
            f"任务完成情况: {tasks_data}\n"
            f"项目事件: {events_data}\n"
            f"负责项目: {projects_data}\n"
            f"日期范围: {period_start[:10]} 至 {now.strftime('%Y-%m-%d')}"
        )
        system = (
            "你是专业的工作报告撰写助手。用简洁的中文生成工作报告，包含：\n"
            "1. 本期完成的工作\n2. 进行中的工作\n3. 下期计划\n"
            "如果数据为空，根据常见工作场景生成一个合理的模板框架让用户填写。"
        )

        try:
            report = await AIService.call_llm(prompt, system)
            return f"📝 AI 生成的{report_type_name}:\n\n{report}"
        except Exception as e:
            return f"📝 {report_type_name}生成失败: {str(e)}"
