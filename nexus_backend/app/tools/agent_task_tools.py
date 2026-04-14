"""
Agent Task Tools — External persistent task system (P1a).

Provides create_task / update_task / list_tasks tools so the agent can
track multi-step work independently of conversation context.  Tasks
survive context compression and give the agent a persistent "TODO board".
"""

import logging
from typing import Any

from app.tools._shared import _get_client, safe_tool_error
from app.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------


class CreateTaskTool(BaseTool):
    name = "create_task"
    description = "创建持久化任务用于跟踪多步骤工作进度"
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "任务标题（简洁描述要做什么）",
            },
            "description": {
                "type": "string",
                "description": "任务详细描述（可选）",
                "default": "",
            },
            "depends_on": {
                "type": "array",
                "items": {"type": "string"},
                "description": "依赖的任务ID列表（可选，这些任务完成后才能开始本任务）",
                "default": [],
            },
        },
        "required": ["title"],
    }
    category = "system"
    domain = "schedule"
    examples = [
        {
            "input": {
                "title": "分析本月销售数据",
                "description": "汇总各区域销售额并生成报告",
            },
            "output_summary": "创建一个待办任务并返回任务编号",
        },
        {
            "input": {"title": "更新客户资料", "depends_on": ["abc12345"]},
            "output_summary": "创建依赖于指定任务的新任务",
        },
    ]
    gotchas = "标题不能为空。创建后状态默认为待办。任务跨会话持久化保存。"
    related_tools = ["list_tasks", "update_task"]

    async def execute(
        self, arguments: dict[str, Any], context: dict[str, Any] | None = None
    ) -> str:
        ctx = context or {}
        user_id = ctx.get("user_id", "")
        session_id = ctx.get("session_id", "default")
        org_id = ctx.get("org_id")

        title = arguments.get("title", "").strip()
        if not title:
            return "错误：任务标题不能为空"

        description = arguments.get("description", "")
        depends_on = arguments.get("depends_on", [])

        try:
            client = _get_client(ctx)
            result = (
                await client.table("agent_tasks")
                .insert(
                    {
                        "conversation_id": session_id,
                        "tenant_id": org_id,
                        "user_id": user_id,
                        "title": title,
                        "description": description,
                        "depends_on": depends_on,
                        "status": "pending",
                    }
                )
                .execute()
            )

            if result.data:
                task = result.data[0]
                task_id = task["id"]
                return self.format_result(data={}, summary=f"任务已创建: [{task_id[:8]}] {title}")
            return "任务创建失败"
        except Exception as e:
            logger.error(f"[CreateTask] Failed: {e}", exc_info=True)
            return safe_tool_error(e, "创建任务")

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        return await self.execute(args, {"user_id": user_id, **(config or {})})


# ---------------------------------------------------------------------------
# update_task
# ---------------------------------------------------------------------------


class UpdateTaskTool(BaseTool):
    name = "update_task"
    description = "更新任务的状态或执行结果摘要"
    examples = [
        {
            "input": {
                "task_id": "abc12345",
                "status": "done",
                "context_summary": "已完成数据分析",
            },
            "output_summary": "将任务标记为已完成并记录结果摘要",
        },
        {
            "input": {"task_id": "abc12345", "status": "blocked"},
            "output_summary": "将任务标记为阻塞状态",
        },
    ]
    gotchas = "任务编号至少提供前8位。至少需要提供状态或结果摘要中的一项。"
    related_tools = ["create_task", "list_tasks"]
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "任务ID（create_task 返回的ID，至少前8位）",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "done", "blocked"],
                "description": "新状态",
            },
            "context_summary": {
                "type": "string",
                "description": "执行结果摘要（可选，记录关键发现或结论）",
            },
        },
        "required": ["task_id"],
    }
    category = "system"
    domain = "schedule"

    async def execute(
        self, arguments: dict[str, Any], context: dict[str, Any] | None = None
    ) -> str:
        ctx = context or {}
        user_id = ctx.get("user_id", "")

        task_id = arguments.get("task_id", "").strip()
        if not task_id:
            return "错误：task_id 不能为空"

        update_data: dict[str, Any] = {}
        if "status" in arguments:
            update_data["status"] = arguments["status"]
        if "context_summary" in arguments:
            update_data["context_summary"] = arguments["context_summary"]

        if not update_data:
            return "错误：至少需要提供 status 或 context_summary"

        try:
            client = _get_client(ctx)
            # Support partial ID matching (first 8 chars)
            query = client.table("agent_tasks").update(update_data).eq("user_id", user_id)
            query = (
                query.ilike("id", f"{task_id}%")
                if len(task_id) < 36
                else query.eq("id", task_id)
            )

            result = await query.execute()

            if result.data:
                task = result.data[0]
                return self.format_result(data={}, summary=f"任务已更新: [{task['id'][:8]}] {task.get('title', '')} → {task.get('status', '')}")
            return f"未找到任务: {task_id}"
        except Exception as e:
            logger.error(f"[UpdateTask] Failed: {e}", exc_info=True)
            return safe_tool_error(e, "更新任务")

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        return await self.execute(args, {"user_id": user_id, **(config or {})})


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------


class ListTasksTool(BaseTool):
    name = "list_tasks"
    description = "列出当前会话的所有任务及其状态"
    examples = [
        {"input": {}, "output_summary": "返回当前会话全部任务的状态面板"},
        {
            "input": {"status_filter": "pending"},
            "output_summary": "仅返回待办状态的任务列表",
        },
    ]
    gotchas = "仅返回当前会话的任务，最多20条。默认显示所有状态。"
    related_tools = ["create_task", "update_task"]
    parameters = {
        "type": "object",
        "properties": {
            "status_filter": {
                "type": "string",
                "enum": ["all", "pending", "in_progress", "blocked"],
                "description": "按状态筛选（默认 all）",
                "default": "all",
            },
        },
        "required": [],
    }
    category = "system"
    domain = "schedule"

    async def execute(
        self, arguments: dict[str, Any], context: dict[str, Any] | None = None
    ) -> str:
        ctx = context or {}
        user_id = ctx.get("user_id", "")
        session_id = ctx.get("session_id", "default")

        status_filter = arguments.get("status_filter", "all")

        try:
            client = _get_client(ctx)
            query = (
                client.table("agent_tasks")
                .select("id, title, status, depends_on, context_summary, sort_order")
                .eq("user_id", user_id)
                .eq("conversation_id", session_id)
                .order("sort_order")
                .order("created_at")
            )

            if status_filter != "all":
                query = query.eq("status", status_filter)

            result = await query.limit(20).execute()
            tasks = result.data or []

            if not tasks:
                return "当前会话没有任务。"

            # Build compact task board view
            status_icons = {
                "pending": "⬜",
                "in_progress": "🔄",
                "done": "✅",
                "blocked": "🚫",
            }
            lines = [f"📋 任务板 ({len(tasks)} 个任务):"]
            for t in tasks:
                icon = status_icons.get(t["status"], "❓")
                tid = t["id"][:8]
                title = t["title"]
                line = f"  {icon} [{tid}] {title}"
                if t.get("depends_on"):
                    deps = ", ".join(d[:8] for d in t["depends_on"])
                    line += f" (依赖: {deps})"
                if t.get("context_summary"):
                    summary = t["context_summary"][:60]
                    line += f"\n      → {summary}"
                lines.append(line)

            # Summary counts
            counts = {}
            for t in tasks:
                s = t["status"]
                counts[s] = counts.get(s, 0) + 1
            summary_parts = [
                f"{status_icons.get(s, '?')}{c}" for s, c in counts.items()
            ]
            lines.append(f"\n状态: {' '.join(summary_parts)}")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"[ListTasks] Failed: {e}", exc_info=True)
            return safe_tool_error(e, "获取任务列表")

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        return await self.execute(args, {"user_id": user_id, **(config or {})})
