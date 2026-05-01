import logging
from datetime import datetime, timedelta
from typing import Any

from app.services.llm_gateway import llm_gateway
from app.tools._shared import _get_client, _validate_uuid, safe_tool_error

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class ProjectListTool(BaseTool):
    name = "get_projects"
    domain = "project"
    description = "查询当前所有未归档项目列表，返回项目名称、状态和进度"
    examples = [
        {
            "input": {},
            "output_summary": "返回所有未归档项目的ID、名称、状态、进度百分比",
        },
    ]
    gotchas = "默认只返回未归档项目，无法筛选已归档项目。结果按数据库默认排序返回。"
    related_tools = ["create_project", "generate_weekly_report", "create_project_event"]

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        try:
            client = _get_client(config)
            org_id = config.get("org_id") if config else None
            query = (
                client.table("projects")
                .select("id, name, stage, progress")
                .neq("stage", "archived")
            )
            if org_id:
                query = query.eq("organization_id", org_id)

            result = await query.execute()
            if not result.data:
                return self.format_result(data=[], summary="暂无进行中的项目。")

            items = [
                f"ID: {p['id']} | 名称: {p['name']} | 状态: {p.get('stage', '未知')} | 进度: {p.get('progress', 0)}%"
                for p in result.data
            ]
            summary = "项目清单：\n" + "\n".join(items)
            return self.format_result(data=result.data, summary=summary)
        except Exception as e:
            return safe_tool_error(e, "查询项目列表")


class CreateProjectTool(BaseTool):
    name = "create_project"
    domain = "project"
    description = "创建新项目立项记录，设置名称、描述和初始状态。当用户说'帮我新建一个项目'时调用。"
    examples = [
        {
            "input": {"name": "智慧园区项目"},
            "output_summary": "创建项目，状态默认为规划中，进度为0%",
        },
        {
            "input": {
                "name": "客户管理系统",
                "description": "搭建CRM系统",
                "status": "in_progress",
            },
            "output_summary": "创建项目并设置初始状态为进行中",
        },
    ]
    related_tools = ["get_projects", "create_project_event"]
    gotchas = "项目名称为必填项。初始状态仅支持规划中和进行中两种。创建后进度默认为0%。"

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

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
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
                return self.format_result(
                    data=res.data[0],
                    summary=f"项目 '{name}' 已成功立项 (ID: {pid})！您可以继续添加项目事件或里程碑。",
                )
            return "创建失败。"
        except Exception as e:
            return safe_tool_error(e, "创建项目")


class CreateEventTool(BaseTool):
    name = "create_project_event"
    domain = "project"
    description = "在指定项目中创建进度事件或关键节点，如里程碑、会议、宴请、任务等"
    examples = [
        {
            "input": {
                "project_id": "uuid",
                "title": "签署合同",
                "content": "与客户正式签约",
                "event_type": "milestone",
            },
            "output_summary": "在项目时间线中创建一条里程碑事件",
        },
        {
            "input": {
                "project_id": "uuid",
                "title": "项目启动会",
                "content": "全员参会讨论分工",
                "event_type": "meeting",
            },
            "output_summary": "创建一条会议类型事件",
        },
    ]
    related_tools = ["get_projects", "create_project", "generate_weekly_report"]
    gotchas = "项目ID必须是有效的UUID格式，可先调用查询项目列表获取。事件类型仅支持里程碑、会议、宴请、任务四种。"

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

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        project_id = args.get("project_id")
        title = args.get("title")
        content = args.get("content")
        event_type = args.get("event_type")

        # Validate UUID format
        uuid_err = _validate_uuid(project_id, "project_id")
        if uuid_err:
            return uuid_err

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
                return self.format_result(
                    data=result.data[0],
                    summary=f"成功在项目中创建了事件: {title}。"
                )
            return "创建失败，请核对项目 ID 是否正确。"
        except Exception as e:
            return safe_tool_error(e, "创建项目事件")


class WeeklyReportTool(BaseTool):
    """AI 周报/日报自动起草"""

    name = "generate_weekly_report"
    domain = "project"
    description = "自动生成工作日报或周报，汇总任务完成情况、项目事件和下期计划。当用户说'帮我写周报'、'生成日报'时调用。"
    examples = [
        {"input": {}, "output_summary": "默认生成本周周报，汇总任务和项目数据"},
        {"input": {"report_type": "daily"}, "output_summary": "生成当日日报"},
        {"input": {"report_type": "weekly"}, "output_summary": "生成本周周报"},
    ]
    related_tools = ["get_projects", "create_project_event", "smart_report"]
    gotchas = "数据为空时会生成模板框架供用户填写。依赖大语言模型生成文本，响应时间较长。日报统计当天数据，周报统计本周一至今的数据。"
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

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        report_type = args.get("report_type", "weekly")
        client = _get_client(config)
        org_id = config.get("org_id") if config else None
        now = datetime.now()

        if report_type == "daily":
            period_start = now.strftime("%Y-%m-%dT00:00:00")
            report_type_name = "日报"
        else:
            period_start = (now - timedelta(days=now.weekday())).strftime(
                "%Y-%m-%dT00:00:00"
            )
            report_type_name = "周报"

        # 聚合数据 (任务、项目事件、当前项目)
        tasks_data = []
        events_data = []
        projects_data = []

        try:
            # 1. 任务数据 (基于 assignee_id)
            tasks_res = (
                await client.table("oa_tasks")
                .select("title, status, priority")
                .eq("assignee_id", user_id)
                .gte("updated_at", period_start)
                .execute()
            )
            tasks_data = tasks_res.data or []

            # 2. 项目事件 (由 RLS 基于项目所属组织进行隔离)
            # 注意：project_timeline 表没有 organization_id 字段，依赖 RLS 自动过滤
            events_res = (
                await client.table("project_timeline")
                .select("title, event_type, content")
                .gte("created_at", period_start)
                .limit(20)
                .execute()
            )
            events_data = events_res.data or []

            # 3. 用户负责的项目
            proj_query = (
                client.table("projects")
                .select("name, stage, progress")
                .eq("user_id", user_id)
                .neq("stage", "archived")
            )
            if org_id:
                proj_query = proj_query.eq("organization_id", org_id)
            proj_res = await proj_query.execute()
            projects_data = proj_res.data or []

        except Exception as e:
            logger.warning("周报数据聚合部分失败: %s", e)

        # 构建 Prompt
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
            # P0: 使用统一的 llm_gateway 代替 AIService
            messages = [{"role": "user", "content": prompt}]
            response = await llm_gateway.chat(
                scene_code="project",
                agent_code="weekly_report",
                user_id=user_id,
                org_id=org_id,
                system_prompt=system,
                messages=messages,
                temperature=0.3
            )
            report = response.content

            return self.format_result(
                data={"report": report, "type": report_type},
                summary=f"📝 AI 生成的{report_type_name}:\n\n{report}"
            )
        except Exception as e:
            return safe_tool_error(e, f"{report_type_name}生成")

