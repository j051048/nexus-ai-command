"""
P2: 统一日历工具集
提供日程查询、创建、修改/取消功能，统一所有时间相关数据到 calendar_events 表。
"""

import contextlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ._shared import _get_client
from .base_tool import BaseTool

logger = logging.getLogger(__name__)

CN_TZ = timezone(timedelta(hours=8))


class CalendarQueryTool(BaseTool):
    """日程查询工具 — 查看指定日期范围内的所有日程安排"""

    name = "get_calendar"
    description = (
        "查询用户指定日期范围内的日程安排（会议、请假、任务截止、出差等）。"
        "用户说'我的日程'、'这周安排'、'明天有什么事'、'有空吗'时调用。"
    )
    required_role = "all"
    domain = "schedule"
    examples = [
        {
            "input": {"start_date": "2026-03-22", "end_date": "2026-03-28"},
            "output_summary": "返回本周日程列表和空闲时段",
        },
        {
            "input": {"start_date": "2026-03-23", "event_type": "meeting"},
            "output_summary": "返回明天的所有会议",
        },
    ]
    related_tools = ["create_calendar_event", "book_meeting"]

    parameters = {
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": "查询开始日期，YYYY-MM-DD格式。默认今天。",
            },
            "end_date": {
                "type": "string",
                "description": "查询结束日期，YYYY-MM-DD格式。默认start_date+7天。",
            },
            "event_type": {
                "type": "string",
                "enum": [
                    "meeting",
                    "leave",
                    "task_deadline",
                    "scheduled_task",
                    "travel",
                    "custom",
                ],
                "description": "可选，按事件类型过滤",
            },
        },
        "required": [],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        now = datetime.now(CN_TZ)

        start_str = args.get("start_date", now.strftime("%Y-%m-%d"))
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d").replace(tzinfo=CN_TZ)
        except ValueError:
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)

        end_str = args.get("end_date")
        if end_str:
            try:
                end_dt = datetime.strptime(end_str, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=CN_TZ
                )
            except ValueError:
                end_dt = start_dt + timedelta(days=7)
        else:
            end_dt = start_dt + timedelta(days=7)

        query = (
            client.table("calendar_events")
            .select(
                "id, title, event_type, start_time, end_time, all_day, location, attendees, status"
            )
            .eq("user_id", user_id)
            .eq("status", "active")
            .gte("start_time", start_dt.isoformat())
            .lte("start_time", end_dt.isoformat())
            .order("start_time")
            .limit(50)
        )

        event_type = args.get("event_type")
        if event_type:
            query = query.eq("event_type", event_type)

        result = await query.execute()
        events = result.data or []

        if not events:
            return f"📅 {start_str} 至 {end_str or (start_dt + timedelta(days=7)).strftime('%Y-%m-%d')} 没有日程安排，时间完全空闲。"

        # Format events into timeline
        type_icons = {
            "meeting": "🤝",
            "leave": "🏖️",
            "task_deadline": "📋",
            "scheduled_task": "⏰",
            "travel": "✈️",
            "custom": "📌",
        }

        lines = [f"📅 **日程安排** ({start_str} ~ {end_str or ''})"]
        current_date = ""
        for evt in events:
            st = evt.get("start_time", "")
            try:
                dt = datetime.fromisoformat(st.replace("Z", "+00:00")).astimezone(CN_TZ)
                date_str = dt.strftime("%m月%d日 %A")
                time_str = dt.strftime("%H:%M")
            except Exception:
                date_str = "未知日期"
                time_str = ""

            if date_str != current_date:
                current_date = date_str
                lines.append(f"\n**{date_str}**")

            icon = type_icons.get(evt.get("event_type", ""), "📌")
            title = evt.get("title", "无标题")
            et = evt.get("end_time")
            end_time_str = ""
            if et:
                with contextlib.suppress(Exception):
                    end_time_str = f"-{datetime.fromisoformat(et.replace('Z', '+00:00')).astimezone(CN_TZ).strftime('%H:%M')}"

            location = f" | 📍{evt['location']}" if evt.get("location") else ""
            attendees = evt.get("attendees") or []
            att_str = f" | 👥{','.join(attendees[:3])}" if attendees else ""
            lines.append(
                f"  {icon} {time_str}{end_time_str} {title}{location}{att_str}"
            )

        lines.append(f"\n共 {len(events)} 个日程")
        return "\n".join(lines)


class CalendarCreateTool(BaseTool):
    """日程创建工具 — 创建日历事件，自动冲突检测"""

    name = "create_calendar_event"
    description = (
        "创建日程事件（会议、任务截止、出差、自定义事件等），自动检测日程冲突。"
        "用户说'安排一个会议'、'添加日程'、'记一下明天要做X'时调用。"
    )
    required_role = "all"
    domain = "schedule"
    examples = [
        {
            "input": {
                "title": "产品评审会",
                "event_type": "meeting",
                "start_time": "2026-03-25T14:00:00+08:00",
                "duration_minutes": 60,
                "attendees": ["张三", "李四"],
            },
            "output_summary": "创建会议事件并检测冲突",
        },
    ]
    related_tools = ["get_calendar", "book_meeting", "update_calendar_event"]
    gotchas = (
        "start_time 必须是 ISO 8601 格式。用户说'明天下午3点'时请转换为具体日期时间。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "事件标题"},
            "event_type": {
                "type": "string",
                "enum": ["meeting", "task_deadline", "travel", "custom"],
                "description": "事件类型。leave 类型请使用 create_leave_request 工具。",
            },
            "start_time": {
                "type": "string",
                "description": "事件开始时间，ISO 8601格式(如 2026-03-23T14:00:00+08:00)。用户说'明天下午3点'时请转换为具体日期时间。",
            },
            "end_time": {
                "type": "string",
                "description": "事件结束时间，ISO 8601格式。与 duration_minutes 二选一。",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "事件时长（分钟），默认60。当未指定 end_time 时使用。",
            },
            "all_day": {
                "type": "boolean",
                "description": "是否全天事件，默认false",
            },
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "参会人/参与人姓名列表",
            },
            "location": {"type": "string", "description": "地点"},
            "description": {"type": "string", "description": "事件描述"},
        },
        "required": ["title", "event_type", "start_time"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)

        title = args["title"]
        event_type = args["event_type"]
        start_time_str = args["start_time"]

        # Parse start time
        try:
            start_dt = datetime.fromisoformat(start_time_str)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=CN_TZ)
        except ValueError:
            return f"❌ 无法解析开始时间: {start_time_str}，请使用 ISO 8601 格式（如 2026-03-23T14:00:00+08:00）"

        # Determine end time
        end_time_str = args.get("end_time")
        duration = args.get("duration_minutes", 60)
        is_all_day = args.get("all_day", False)

        if end_time_str:
            try:
                end_dt = datetime.fromisoformat(end_time_str)
                if end_dt.tzinfo is None:
                    end_dt = end_dt.replace(tzinfo=CN_TZ)
            except ValueError:
                end_dt = start_dt + timedelta(minutes=duration)
        elif is_all_day:
            end_dt = start_dt.replace(hour=23, minute=59, second=59)
        else:
            end_dt = start_dt + timedelta(minutes=duration)

        # Conflict detection
        conflict_warning = ""
        try:
            conflicts = await client.rpc(
                "check_calendar_conflicts",
                {
                    "p_user_id": user_id,
                    "p_start_time": start_dt.isoformat(),
                    "p_end_time": end_dt.isoformat(),
                },
            ).execute()

            if conflicts.data:
                conflict_lines = ["⚠️ **检测到日程冲突：**"]
                for c in conflicts.data:
                    c_start = c.get("start_time", "")
                    try:
                        c_time = (
                            datetime.fromisoformat(c_start.replace("Z", "+00:00"))
                            .astimezone(CN_TZ)
                            .strftime("%H:%M")
                        )
                    except Exception:
                        c_time = "?"
                    conflict_lines.append(
                        f"  - {c_time} {c['title']} ({c['event_type']})"
                    )
                conflict_warning = "\n".join(conflict_lines) + "\n\n"
        except Exception as e:
            logger.error(f"Calendar conflict check failed (RPC may not exist yet): {e}")

        # Get org_id from user
        org_id = None
        try:
            user_res = (
                await client.table("users")
                .select("organization_id")
                .eq("id", user_id)
                .limit(1)
                .execute()
            )
            if user_res.data:
                org_id = user_res.data[0].get("organization_id")
        except Exception:
            pass

        # Insert event
        event_data = {
            "user_id": user_id,
            "title": title,
            "event_type": event_type,
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "all_day": is_all_day,
            "attendees": args.get("attendees", []),
            "location": args.get("location"),
            "description": args.get("description"),
            "status": "active",
        }
        if org_id:
            event_data["organization_id"] = org_id

        result = await client.table("calendar_events").insert(event_data).execute()

        if not result.data:
            return "❌ 创建日程失败，请稍后重试。"

        start_display = start_dt.astimezone(CN_TZ).strftime("%Y-%m-%d %H:%M")
        end_display = end_dt.astimezone(CN_TZ).strftime("%H:%M")
        attendees = args.get("attendees", [])
        att_str = f"\n- 参与人: {', '.join(attendees)}" if attendees else ""
        loc_str = f"\n- 地点: {args['location']}" if args.get("location") else ""

        return f"""{conflict_warning}✅ 日程已创建

📅 **{title}**
- 时间: {start_display} - {end_display}
- 类型: {event_type}{att_str}{loc_str}"""


class CalendarUpdateTool(BaseTool):
    """日程修改/取消工具"""

    name = "update_calendar_event"
    description = (
        "修改或取消已有的日程事件。"
        "用户说'改会议时间'、'取消明天的会'、'把周三的会推迟'时调用。"
    )
    required_role = "all"
    domain = "schedule"
    confirmation_type = "IRREVERSIBLE"
    examples = [
        {
            "input": {"title": "产品评审会", "action": "cancel"},
            "output_summary": "取消匹配的日程事件",
        },
        {
            "input": {
                "title": "周会",
                "action": "update",
                "new_start_time": "2026-03-26T15:00:00+08:00",
            },
            "output_summary": "将周会改到新时间",
        },
    ]
    related_tools = ["get_calendar", "create_calendar_event"]

    parameters = {
        "type": "object",
        "properties": {
            "event_id": {
                "type": "string",
                "description": "事件ID（优先使用）。如不知道ID，可用 title 模糊匹配。",
            },
            "title": {
                "type": "string",
                "description": "事件标题（模糊匹配，当没有 event_id 时使用）",
            },
            "action": {
                "type": "string",
                "enum": ["update", "cancel"],
                "description": "操作类型: update(修改) 或 cancel(取消)",
            },
            "new_start_time": {
                "type": "string",
                "description": "新的开始时间，ISO 8601格式。仅 action=update 时使用。",
            },
            "new_end_time": {
                "type": "string",
                "description": "新的结束时间，ISO 8601格式。仅 action=update 时使用。",
            },
            "new_title": {
                "type": "string",
                "description": "新标题。仅 action=update 时使用。",
            },
        },
        "required": ["action"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        action = args["action"]

        # Find the event
        event_id = args.get("event_id")
        event = None

        if event_id:
            res = await (
                client.table("calendar_events")
                .select("*")
                .eq("id", event_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if res.data:
                event = res.data[0]
        elif args.get("title"):
            res = await (
                client.table("calendar_events")
                .select("*")
                .eq("user_id", user_id)
                .eq("status", "active")
                .ilike("title", f"%{args['title']}%")
                .order("start_time", desc=True)
                .limit(1)
                .execute()
            )
            if res.data:
                event = res.data[0]

        if not event:
            return "❌ 未找到匹配的日程事件。请检查事件标题或ID是否正确。"

        if action == "cancel":
            cancel_res = await (
                client.table("calendar_events")
                .update(
                    {
                        "status": "cancelled",
                        "updated_at": datetime.now(CN_TZ).isoformat(),
                    }
                )
                .eq("id", event["id"])
                .execute()
            )
            if not cancel_res.data:
                return "❌ 取消日程失败，请稍后重试。"
            return self.format_result(data={}, summary=f"已取消日程: **{event['title']}**")

        # action == "update"
        update_data: dict[str, Any] = {"updated_at": datetime.now(CN_TZ).isoformat()}

        if args.get("new_title"):
            update_data["title"] = args["new_title"]
        if args.get("new_start_time"):
            try:
                new_start = datetime.fromisoformat(args["new_start_time"])
                update_data["start_time"] = new_start.isoformat()
            except ValueError:
                return f"❌ 无法解析新的开始时间: {args['new_start_time']}"
        if args.get("new_end_time"):
            try:
                new_end = datetime.fromisoformat(args["new_end_time"])
                update_data["end_time"] = new_end.isoformat()
            except ValueError:
                return f"❌ 无法解析新的结束时间: {args['new_end_time']}"

        if len(update_data) <= 1:  # only updated_at
            return "❌ 没有指定要修改的内容（new_start_time, new_end_time, new_title）"

        # Conflict check for time changes
        conflict_warning = ""
        if "start_time" in update_data or "end_time" in update_data:
            check_start = update_data.get("start_time", event["start_time"])
            check_end = update_data.get(
                "end_time", event.get("end_time") or check_start
            )
            try:
                conflicts = await client.rpc(
                    "check_calendar_conflicts",
                    {
                        "p_user_id": user_id,
                        "p_start_time": check_start,
                        "p_end_time": check_end,
                        "p_exclude_id": event["id"],
                    },
                ).execute()
                if conflicts.data:
                    conflict_warning = (
                        f"\n⚠️ 注意：新时段与 {len(conflicts.data)} 个日程存在冲突。"
                    )
            except Exception:
                pass

        upd_res = (
            await client.table("calendar_events")
            .update(update_data)
            .eq("id", event["id"])
            .execute()
        )
        if not upd_res.data:
            return "❌ 更新日程失败，请稍后重试。"

        changes = []
        if args.get("new_title"):
            changes.append(f"标题 → {args['new_title']}")
        if args.get("new_start_time"):
            changes.append(f"开始时间 → {args['new_start_time']}")
        if args.get("new_end_time"):
            changes.append(f"结束时间 → {args['new_end_time']}")

        return self.format_result(data={}, summary=f"已更新日程 **{event['title']}**\n修改: {'; '.join(changes)}{conflict_warning}")
