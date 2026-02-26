"""
用户自定义定时任务工具
允许用户通过 AI 对话创建、查看、删除自定义定时任务。
例如："每天下午4点提醒我检查客户回复"
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import supabase

from .base_tool import BaseTool

logger = logging.getLogger(__name__)

# Day name mapping
_DAY_NAMES = {
    0: "周一", 1: "周二", 2: "周三", 3: "周四",
    4: "周五", 5: "周六", 6: "周日",
}
_DAY_NAMES_REVERSE = {
    "周一": 0, "周二": 1, "周三": 2, "周四": 3,
    "周五": 4, "周六": 5, "周日": 6,
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "星期一": 0, "星期二": 1, "星期三": 2, "星期四": 3,
    "星期五": 4, "星期六": 5, "星期日": 6, "星期天": 6,
}


def _compute_next_execution(
    schedule_type: str,
    hour: int | None,
    minute: int,
    day_of_week: int | None,
    interval_minutes: int | None,
    execute_at: str | None,
) -> str | None:
    """Compute the next execution time based on schedule parameters."""
    now = datetime.now(UTC)

    if schedule_type == "once" and execute_at:
        return execute_at

    if schedule_type == "interval" and interval_minutes:
        return (now + timedelta(minutes=interval_minutes)).isoformat()

    if hour is None:
        return None

    # Build today's target time
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if schedule_type == "daily":
        if target <= now:
            target += timedelta(days=1)
        return target.isoformat()

    if schedule_type == "weekly" and day_of_week is not None:
        # Current weekday (Monday=0)
        current_dow = now.weekday()
        days_ahead = day_of_week - current_dow
        if days_ahead < 0 or (days_ahead == 0 and target <= now):
            days_ahead += 7
        target += timedelta(days=days_ahead)
        return target.isoformat()

    return target.isoformat()


class CreateScheduledTaskTool(BaseTool):
    """创建用户自定义定时任务"""

    name = "create_scheduled_task"
    description = (
        "创建定时任务/提醒。当用户说'每天X点提醒我...'、'每周一帮我...'、"
        "'定时执行...'、'设个提醒...'、'帮我定时...'时调用此工具。"
    )
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "任务名称，简短描述（如'检查客户回复'、'生成日报'）",
            },
            "prompt": {
                "type": "string",
                "description": "AI 执行此任务时使用的提示词。描述需要 AI 做什么，如'检查最近的客户跟进情况并提醒我需要回复的客户'",
            },
            "schedule_type": {
                "type": "string",
                "enum": ["daily", "weekly", "once", "interval"],
                "description": "调度类型: daily(每天), weekly(每周), once(一次性), interval(固定间隔)",
            },
            "hour": {
                "type": "integer",
                "description": "执行时间的小时（0-23），如下午4点=16",
            },
            "minute": {
                "type": "integer",
                "description": "执行时间的分钟（0-59），默认0",
            },
            "day_of_week": {
                "type": "integer",
                "description": "星期几执行（0=周一, 6=周日），仅 weekly 类型需要",
            },
            "interval_minutes": {
                "type": "integer",
                "description": "间隔分钟数，仅 interval 类型需要",
            },
        },
        "required": ["name", "prompt", "schedule_type", "hour"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = supabase
        if not client:
            return "数据库连接不可用"

        name = args.get("name", "")
        prompt = args.get("prompt", "")
        schedule_type = args.get("schedule_type", "daily")
        hour = args.get("hour")
        minute = args.get("minute", 0)
        day_of_week = args.get("day_of_week")
        interval_minutes = args.get("interval_minutes")
        org_id = config.get("org_id") if config else None

        # Validation
        if schedule_type == "weekly" and day_of_week is None:
            return "每周任务需要指定星期几（day_of_week: 0=周一 到 6=周日）"
        if schedule_type == "interval" and not interval_minutes:
            return "间隔任务需要指定间隔分钟数（interval_minutes）"

        # Check user task limit (max 20 active tasks per user)
        existing = (
            await client.table("user_scheduled_tasks")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .execute()
        )
        if existing.count and existing.count >= 20:
            return "您的活跃定时任务已达上限（20个）。请先删除不需要的任务。"

        next_exec = _compute_next_execution(
            schedule_type, hour, minute, day_of_week, interval_minutes, None
        )

        task_data = {
            "user_id": user_id,
            "organization_id": org_id,
            "name": name,
            "prompt": prompt,
            "schedule_type": schedule_type,
            "hour": hour,
            "minute": minute,
            "day_of_week": day_of_week,
            "interval_minutes": interval_minutes,
            "is_active": True,
            "next_execution_at": next_exec,
            "notify_method": "notification",
        }

        result = await client.table("user_scheduled_tasks").insert(task_data).execute()
        if not result.data:
            return "创建定时任务失败，请稍后重试。"

        # Format schedule description
        schedule_desc = self._format_schedule(schedule_type, hour, minute, day_of_week, interval_minutes)

        return f"""已创建定时任务！

**任务详情**
- 名称: {name}
- 执行计划: {schedule_desc}
- AI 将执行: {prompt}
- 下次执行: {next_exec[:16] if next_exec else '待计算'}

系统会按计划自动执行此任务，并通过通知推送结果给您。
您可以随时说'查看我的定时任务'或'删除定时任务'来管理。"""

    @staticmethod
    def _format_schedule(
        schedule_type: str,
        hour: int | None,
        minute: int,
        day_of_week: int | None,
        interval_minutes: int | None,
    ) -> str:
        time_str = f"{hour:02d}:{minute:02d}" if hour is not None else ""
        if schedule_type == "daily":
            return f"每天 {time_str}"
        if schedule_type == "weekly":
            day = _DAY_NAMES.get(day_of_week, f"第{day_of_week}天")
            return f"每{day} {time_str}"
        if schedule_type == "once":
            return f"一次性执行 {time_str}"
        if schedule_type == "interval":
            return f"每 {interval_minutes} 分钟"
        return schedule_type


class ListScheduledTasksTool(BaseTool):
    """查看用户定时任务列表"""

    name = "list_scheduled_tasks"
    description = (
        "查看当前用户的定时任务列表。当用户说'我的定时任务'、'查看提醒'、"
        "'有哪些定时任务'时调用。"
    )
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "include_inactive": {
                "type": "boolean",
                "description": "是否包含已停用的任务，默认 false",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = supabase
        if not client:
            return "数据库连接不可用"

        include_inactive = args.get("include_inactive", False)

        query = (
            client.table("user_scheduled_tasks")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(20)
        )
        if not include_inactive:
            query = query.eq("is_active", True)

        result = await query.execute()
        tasks = result.data or []

        if not tasks:
            return "您当前没有定时任务。可以说'每天X点提醒我...'来创建一个。"

        lines = ["**您的定时任务列表**\n"]
        for i, task in enumerate(tasks, 1):
            status = "启用" if task["is_active"] else "已停用"
            schedule = CreateScheduledTaskTool._format_schedule(
                task["schedule_type"],
                task.get("hour"),
                task.get("minute", 0),
                task.get("day_of_week"),
                task.get("interval_minutes"),
            )
            last_run = task.get("last_executed_at", "")
            last_run_str = f" | 上次: {last_run[:16]}" if last_run else ""
            exec_count = task.get("execution_count", 0)

            lines.append(
                f"{i}. **{task['name']}** [{status}]\n"
                f"   计划: {schedule} | 已执行 {exec_count} 次{last_run_str}\n"
                f"   任务ID: `{task['id'][:8]}...`"
            )

        return "\n".join(lines)


class DeleteScheduledTaskTool(BaseTool):
    """删除或停用用户定时任务"""

    name = "delete_scheduled_task"
    description = (
        "删除或停用定时任务。当用户说'删除定时任务'、'取消提醒'、"
        "'停止定时任务'时调用。支持按名称或ID删除。"
    )
    required_role = "all"
    is_irreversible = True
    confirmation_message = "确认要删除此定时任务吗？删除后不可恢复。"

    parameters = {
        "type": "object",
        "properties": {
            "task_name": {
                "type": "string",
                "description": "要删除的任务名称（模糊匹配）",
            },
            "task_id": {
                "type": "string",
                "description": "要删除的任务ID（精确匹配，优先于名称）",
            },
            "action": {
                "type": "string",
                "enum": ["delete", "disable", "enable"],
                "description": "操作: delete(永久删除), disable(停用), enable(启用)。默认 delete。",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = supabase
        if not client:
            return "数据库连接不可用"

        task_id = args.get("task_id")
        task_name = args.get("task_name")
        action = args.get("action", "delete")

        if not task_id and not task_name:
            return "请提供任务名称或任务ID。您可以先说'查看我的定时任务'获取列表。"

        # Find the task
        if task_id:
            # Support partial ID match
            result = (
                await client.table("user_scheduled_tasks")
                .select("*")
                .eq("user_id", user_id)
                .ilike("id", f"{task_id}%")
                .limit(1)
                .execute()
            )
        else:
            result = (
                await client.table("user_scheduled_tasks")
                .select("*")
                .eq("user_id", user_id)
                .ilike("name", f"%{task_name}%")
                .limit(1)
                .execute()
            )

        if not result.data:
            return "未找到匹配的定时任务。请确认名称或ID是否正确。"

        task = result.data[0]

        if action == "delete":
            await client.table("user_scheduled_tasks").delete().eq("id", task["id"]).execute()
            return f"已删除定时任务「{task['name']}」。"
        elif action == "disable":
            await (
                client.table("user_scheduled_tasks")
                .update({"is_active": False})
                .eq("id", task["id"])
                .execute()
            )
            return f"已停用定时任务「{task['name']}」。可以随时重新启用。"
        elif action == "enable":
            next_exec = _compute_next_execution(
                task["schedule_type"],
                task.get("hour"),
                task.get("minute", 0),
                task.get("day_of_week"),
                task.get("interval_minutes"),
                task.get("execute_at"),
            )
            await (
                client.table("user_scheduled_tasks")
                .update({"is_active": True, "next_execution_at": next_exec})
                .eq("id", task["id"])
                .execute()
            )
            return f"已启用定时任务「{task['name']}」，下次执行时间: {next_exec[:16] if next_exec else '待计算'}。"

        return "未知操作"
