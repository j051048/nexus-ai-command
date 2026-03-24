"""
用户自定义定时任务工具
允许用户通过 AI 对话创建、查看、删除自定义定时任务。
例如："每天下午4点提醒我检查客户回复"
"""

import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from app.core.database import supabase

from .base_tool import BaseTool
from ._shared import _get_client

logger = logging.getLogger(__name__)

# Day name mapping
_DAY_NAMES = {
    0: "周一",
    1: "周二",
    2: "周三",
    3: "周四",
    4: "周五",
    5: "周六",
    6: "周日",
}
_DAY_NAMES_REVERSE = {
    "周一": 0,
    "周二": 1,
    "周三": 2,
    "周四": 3,
    "周五": 4,
    "周六": 5,
    "周日": 6,
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
    "星期一": 0,
    "星期二": 1,
    "星期三": 2,
    "星期四": 3,
    "星期五": 4,
    "星期六": 5,
    "星期日": 6,
    "星期天": 6,
}


def _compute_next_execution(
    schedule_type: str,
    hour: int | None,
    minute: int,
    day_of_week: int | None,
    interval_minutes: int | None,
    execute_at: str | None,
) -> str | None:
    """Compute the next execution time based on schedule parameters.

    Uses UTC+8 (Asia/Shanghai) since users input hours in local time,
    then converts result back to UTC for storage.
    """
    CN_TZ = timezone(timedelta(hours=8))
    now = datetime.now(CN_TZ)

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
        "创建定时任务或提醒，支持每天、每周、一次性和固定间隔四种调度类型。"
        "当用户说'每天X点提醒我'、'每周一帮我'、'定时执行'、'设个提醒'、'X分钟后提醒我'时调用。"
        "\n【重要】当用户说'X分钟后'、'半小时后'、'一小时后'等相对时间时，"
        "请使用 schedule_type='once' + delay_minutes 参数，不要自己计算 hour/minute。"
    )
    required_role = "all"
    domain = "schedule"
    examples = [
        {"input": {"name": "检查客户回复", "prompt": "检查最近的客户跟进情况并提醒我需要回复的客户", "schedule_type": "daily", "hour": 16, "minute": 0}, "output_summary": "创建每天16:00执行的定时任务"},
        {"input": {"name": "周报提醒", "prompt": "提醒我准备本周工作总结", "schedule_type": "weekly", "hour": 17, "minute": 0, "day_of_week": 4}, "output_summary": "创建每周五17:00执行的定时任务"},
        {"input": {"name": "会议提醒", "prompt": "提醒我参加产品评审会议", "schedule_type": "once", "delay_minutes": 30}, "output_summary": "创建30分钟后执行的一次性提醒"},
    ]
    related_tools = ["list_scheduled_tasks", "delete_scheduled_task"]
    gotchas = "每个用户最多20个活跃任务；相对时间（如'半小时后'）必须用 delay_minutes 而非手动算 hour/minute；hour 使用北京时间（0-23）。"

    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "任务名称，简短描述（如'检查客户回复'、'生成日报'）",
                "maxLength": 200,
            },
            "prompt": {
                "type": "string",
                "description": "AI 执行此任务时使用的提示词。描述需要 AI 做什么，如'检查最近的客户跟进情况并提醒我需要回复的客户'",
                "maxLength": 2000,
            },
            "schedule_type": {
                "type": "string",
                "enum": ["daily", "weekly", "once", "interval"],
                "description": "调度类型: daily(每天), weekly(每周), once(一次性), interval(固定间隔)",
            },
            "hour": {
                "type": "integer",
                "minimum": 0,
                "maximum": 23,
                "description": "执行时间的小时（0-23），如下午4点=16",
            },
            "minute": {
                "type": "integer",
                "minimum": 0,
                "maximum": 59,
                "description": "执行时间的分钟（0-59），默认0",
            },
            "day_of_week": {
                "type": "integer",
                "minimum": 0,
                "maximum": 6,
                "description": "星期几执行（0=周一, 6=周日），仅 weekly 类型需要",
            },
            "interval_minutes": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10080,
                "description": "间隔分钟数（1-10080），仅 interval 类型需要",
            },
            "delay_minutes": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10080,
                "description": "延迟分钟数，仅 once 类型使用。用户说'X分钟后'、'半小时后'(30)、'一小时后'(60)时使用此参数，系统自动计算目标时间，无需手动填 hour/minute。",
            },
        },
        "required": ["name", "prompt", "schedule_type"],
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
        delay_minutes = args.get("delay_minutes")
        org_id = config.get("org_id") if config else None

        # Defensive input validation (defense-in-depth)
        if not name or not prompt:
            return "请提供任务名称和执行提示词。"
        if schedule_type not in ("daily", "weekly", "once", "interval"):
            return f"不支持的调度类型: {schedule_type}"
        if hour is not None and not (0 <= int(hour) <= 23):
            return "小时数必须在 0-23 之间。"
        if not (0 <= int(minute) <= 59):
            return "分钟数必须在 0-59 之间。"
        if day_of_week is not None and not (0 <= int(day_of_week) <= 6):
            return "星期几必须在 0-6 之间（0=周一, 6=周日）。"
        if interval_minutes is not None and not (1 <= int(interval_minutes) <= 10080):
            return "间隔分钟数必须在 1-10080 之间。"
        # Clamp to int to prevent overflow
        hour = int(hour) if hour is not None else None
        minute = int(minute)
        if day_of_week is not None:
            day_of_week = int(day_of_week)
        if interval_minutes is not None:
            interval_minutes = int(interval_minutes)
        if delay_minutes is not None:
            delay_minutes = int(delay_minutes)
            if not (1 <= delay_minutes <= 10080):
                return "延迟分钟数必须在 1-10080 之间。"

        # Truncate to prevent oversized DB writes
        name = name[:200]
        prompt = prompt[:2000]

        # Validation
        if schedule_type == "weekly" and day_of_week is None:
            return "每周任务需要指定星期几（day_of_week: 0=周一 到 6=周日）"
        if schedule_type == "interval" and not interval_minutes:
            return "间隔任务需要指定间隔分钟数（interval_minutes）"

        # Handle delay_minutes for once-type tasks (e.g. "3分钟后提醒我")
        execute_at = None
        if schedule_type == "once" and delay_minutes:
            CN_TZ = timezone(timedelta(hours=8))
            target_time = datetime.now(CN_TZ) + timedelta(minutes=delay_minutes)
            execute_at = target_time.isoformat()
            # Backfill hour/minute for display and DB storage
            hour = target_time.hour
            minute = target_time.minute

        # For non-delay once/daily/weekly, hour is required
        if hour is None and execute_at is None:
            return "请提供执行时间的小时数（hour），或使用 delay_minutes 指定延迟。"

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

        next_exec = _compute_next_execution(schedule_type, hour, minute, day_of_week, interval_minutes, execute_at)

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
- 下次执行: {next_exec[:16] if next_exec else "待计算"}

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
    description = "查询当前用户的定时任务列表，支持筛选是否包含已停用任务。当用户说'我的定时任务'、'查看提醒'、'有哪些定时任务'时调用。"
    required_role = "all"
    domain = "schedule"
    examples = [
        {"input": {}, "output_summary": "返回当前用户所有活跃定时任务列表"},
        {"input": {"include_inactive": True}, "output_summary": "返回包含已停用任务在内的全部定时任务列表"},
    ]
    related_tools = ["create_scheduled_task", "delete_scheduled_task"]
    gotchas = "默认只返回活跃任务，最多返回20条；如需查看已停用任务需显式传 include_inactive=true。"

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
        client = _get_client(config)
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
    description = "删除、停用或启用指定的定时任务，支持按名称模糊匹配或按任务编号精确匹配。当用户说'删除定时任务'、'取消提醒'、'停止定时任务'时调用。"
    required_role = "all"
    domain = "schedule"
    is_irreversible = True
    confirmation_message = "确认要删除此定时任务吗？删除后不可恢复。"
    examples = [
        {"input": {"task_name": "检查客户回复", "action": "delete"}, "output_summary": "按名称模糊匹配并永久删除该定时任务"},
        {"input": {"task_id": "abcd1234", "action": "disable"}, "output_summary": "按任务编号停用该定时任务，可后续重新启用"},
    ]
    related_tools = ["list_scheduled_tasks", "create_scheduled_task"]
    gotchas = "删除操作不可逆，需用户确认；停用和启用可反复切换；建议先调用 list_scheduled_tasks 获取任务名称或编号再操作。"

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
        client = _get_client(config)
        if not client:
            return "数据库连接不可用"

        task_id = args.get("task_id")
        task_name = args.get("task_name")
        action = args.get("action", "delete")

        if not task_id and not task_name:
            return "请提供任务名称或任务ID。您可以先说'查看我的定时任务'获取列表。"

        # Validate action enum
        if action not in ("delete", "disable", "enable"):
            return f"不支持的操作: {action}，请使用 delete/disable/enable。"

        # Find the task
        if task_id:
            # Sanitize: strip LIKE wildcards from task_id
            safe_id = task_id.replace("%", "").replace("_", "")[:36]
            if not safe_id:
                return "任务ID无效。"
            # Use filter with text cast to avoid UUID ilike operator error (42883)
            result = (
                await client.table("user_scheduled_tasks")
                .select("*")
                .eq("user_id", user_id)
                .filter("id::text", "ilike", f"{safe_id}%")
                .limit(1)
                .execute()
            )
        else:
            # Sanitize: strip LIKE wildcards from task_name
            safe_name = task_name.replace("%", "").replace("_", "")[:200] if task_name else ""
            if not safe_name:
                return "任务名称无效。"
            result = (
                await client.table("user_scheduled_tasks")
                .select("*")
                .eq("user_id", user_id)
                .ilike("name", f"%{safe_name}%")
                .limit(1)
                .execute()
            )

        if not result.data:
            return "未找到匹配的定时任务。请确认名称或ID是否正确。"

        task = result.data[0]

        if action == "delete":
            del_res = await client.table("user_scheduled_tasks").delete().eq("id", task["id"]).execute()
            if not del_res.data:
                return f"❌ 删除定时任务「{task['name']}」失败，请稍后重试。"
            # 清理该任务产生的推送消息，防止登录/刷新时重复显示
            try:
                await (
                    client.table("chat_messages")
                    .delete()
                    .eq("user_id", user_id)
                    .filter("metadata->>task_id", "eq", task["id"])
                    .execute()
                )
            except Exception:
                pass  # 非关键路径，静默失败
            return f"已删除定时任务「{task['name']}」。"
        elif action == "disable":
            dis_res = await client.table("user_scheduled_tasks").update({"is_active": False}).eq("id", task["id"]).execute()
            if not dis_res.data:
                return f"❌ 停用定时任务「{task['name']}」失败，请稍后重试。"
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
            en_res = await (
                client.table("user_scheduled_tasks")
                .update({"is_active": True, "next_execution_at": next_exec})
                .eq("id", task["id"])
                .execute()
            )
            if not en_res.data:
                return f"❌ 启用定时任务「{task['name']}」失败，请稍后重试。"
            return f"已启用定时任务「{task['name']}」，下次执行时间: {next_exec[:16] if next_exec else '待计算'}。"

        return "未知操作"
