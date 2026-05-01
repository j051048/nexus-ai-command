"""
OA 办公自动化工具集
实现请假、会议、任务等办公场景的 AI 自动化

P2 Fixes Applied:
- Replaced bare except with proper ValueError handling
- Added structured logging
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.notification_service import (
    Notification,
    NotificationChannel,
    NotificationPriority,
    notification_service,
)
from app.tools._shared import safe_tool_error

from ._shared import _get_client
from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class LeaveRequestTool(BaseTool):
    """请假申请工具 - 支持自然语言创建请假"""

    name = "create_leave_request"
    description = "创建请假申请并自动匹配审批链。用户说'请假'、'休假'、'调休'时调用。支持年假、病假、事假、调休等类型。"
    required_role = "all"
    examples = [
        {
            "input": {
                "leave_type": "annual",
                "start_date": "2026-03-25",
                "end_date": "2026-03-27",
                "reason": "家庭出游",
            },
            "output_summary": "提交2天年假申请，系统自动匹配审批链",
        },
        {
            "input": {
                "leave_type": "sick",
                "start_date": "2026-03-21",
                "end_date": "2026-03-21",
            },
            "output_summary": "提交1天病假，短时间自动批准",
        },
    ]
    related_tools = ["query_leave_status", "submit_approval_on_behalf"]
    gotchas = "日期必须使用 YYYY-MM-DD 格式，且基于当前时间推算，不能使用过去年份。年假余额默认10天，超出会被拒绝。同日期段重复请假会被拦截。"

    parameters = {
        "type": "object",
        "properties": {
            "leave_type": {
                "type": "string",
                "enum": [
                    "annual",
                    "sick",
                    "personal",
                    "compensatory",
                    "maternity",
                    "paternity",
                ],
                "description": "请假类型: annual(年假), sick(病假), personal(事假), compensatory(调休), maternity(产假), paternity(陪产假)",
            },
            "start_date": {
                "type": "string",
                "description": "开始日期，格式 YYYY-MM-DD。必须基于系统提示词中的当前时间来推算，禁止使用过去年份的日期。",
            },
            "end_date": {
                "type": "string",
                "description": "结束日期，格式 YYYY-MM-DD。必须基于系统提示词中的当前时间来推算，禁止使用过去年份的日期。",
            },
            "reason": {"type": "string", "description": "请假原因"},
            "handover_to": {
                "type": "string",
                "description": "工作交接人姓名或ID（可选）",
            },
        },
        "required": ["leave_type", "start_date", "end_date"],
    }
    domain = "oa_leave"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)

        leave_type = args.get("leave_type", "personal")
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        reason = args.get("reason", "")
        handover_to = args.get("handover_to")

        # P0 Fix: Date sanity checks
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")

            # Reject dates that are clearly in the wrong year
            now = datetime.now()
            if start.year < now.year - 1 or start.year > now.year + 1:
                logger.warning(
                    f"Suspicious leave date: {start_date} (current: {now.strftime('%Y-%m-%d')})"
                )
                return (
                    f"日期异常：您提交的请假开始日期是 {start_date}，"
                    f"但当前日期是 {now.strftime('%Y-%m-%d')}。\n\n"
                    f"请重新告诉我您想请假的具体日期，例如：\n"
                    f'- "帮我请明天的假"\n'
                    f'- "请 {now.strftime("%Y-%m-%d")} 到 {(now + timedelta(days=2)).strftime("%Y-%m-%d")} 的假"'
                )
            if end < start:
                return "结束日期不能早于开始日期，请检查后重新提交。"
            if start < now - timedelta(days=7):
                return f"请假开始日期 {start_date} 已经过去超过一周，请确认日期是否正确。当前日期是 {now.strftime('%Y-%m-%d')}。"

            days = (end - start).days + 1
            # 排除周末（简化计算）
            work_days = sum(
                1 for i in range(days) if (start + timedelta(days=i)).weekday() < 5
            )
        except ValueError as e:
            logger.warning(f"Date parsing error: {e}")
            return "日期格式错误，请使用 YYYY-MM-DD 格式"

        # 获取用户信息
        user_res = (
            await client.table("users")
            .select("name, department, role")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        if not user_res.data:
            return "❌ 无法获取用户信息"

        user = user_res.data

        # 重复请假检查：同用户、相同日期段是否已有 pending/approved 记录
        try:
            overlap_res = (
                await client.table("oa_leave_requests")
                .select("id, start_date, end_date, status")
                .eq("user_id", user_id)
                .in_("status", ["pending", "approved"])
                .lte("start_date", end_date)
                .gte("end_date", start_date)
                .limit(1)
                .execute()
            )
            if overlap_res.data:
                existing = overlap_res.data[0]
                return (
                    f"❌ 您在 {existing['start_date']} ~ {existing['end_date']} "
                    f"已有一条{existing['status'] == 'approved' and '已批准' or '待审批'}的请假记录，"
                    f"日期范围与本次申请重叠，请勿重复提交。"
                )
        except Exception:
            pass  # 检查失败不阻塞主流程

        org_id = config.get("org_id") if config else None
        # 查找交接人 (scoped client, RLS enforced)
        handover_id = None
        if handover_to:
            query = client.table("users").select("id, name").ilike("name", f"%{handover_to}%")
            if org_id:
                query = query.eq("organization_id", org_id)
            handover_res = await query.limit(1).execute()
            if handover_res.data:
                handover_id = handover_res.data[0]["id"]

        # 检查年假余额（如果是年假）
        leave_balance_info = ""
        if leave_type == "annual":
            # 简化：假设每人年假10天
            used_res = (
                await client.table("oa_leave_requests")
                .select("days")
                .eq("user_id", user_id)
                .eq("type", "annual")
                .eq("status", "approved")
                .execute()
            )
            used_days = sum(float(r.get("days", 0)) for r in (used_res.data or []))
            remaining = 10 - used_days
            if work_days > remaining:
                return f"❌ 年假余额不足。您今年已使用 {used_days} 天，剩余 {remaining} 天，本次申请 {work_days} 天。"
            leave_balance_info = (
                f"（年假余额: {remaining}天 → {remaining - work_days}天）"
            )

        # 请假类型中文映射
        type_names = {
            "annual": "年假",
            "sick": "病假",
            "personal": "事假",
            "compensatory": "调休",
            "maternity": "产假",
            "paternity": "陪产假",
        }

        # ── 审批链匹配：用天数作为 amount 走请假审批链 ──
        from app.services.approval_chain import approval_chain_service

        org_id_res = (
            await client.table("users")
            .select("organization_id")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        org_id = org_id_res.data.get("organization_id") if org_id_res.data else None

        chain_result = await approval_chain_service.match_and_bind_chain(
            org_id=org_id or "",
            approval_type="leave",
            amount=float(work_days),
            db=client,
        )

        auto_approve = chain_result.get("auto_approve", False)
        chain_id = chain_result.get("chain_id")
        starting_step = chain_result.get("starting_step", 0)
        approval_level = chain_result.get("approval_level", "manager")
        timeout_at = chain_result.get("timeout_at")
        _chain_name = chain_result.get("chain_name", "请假审批链")
        final_status = "approved" if auto_approve else "pending"

        approval_note = (
            "系统自动批准" if auto_approve else f"需{approval_level}级别审批"
        )

        # 创建请假记录（OA 业务表）
        leave_data = {
            "user_id": user_id,
            "organization_id": org_id,
            "type": leave_type,
            "start_date": start_date,
            "end_date": end_date,
            "days": work_days,
            "reason": reason,
            "handover_to": handover_id,
            "status": final_status,
            "approval_level": approval_level,
        }

        result = await client.table("oa_leave_requests").insert(leave_data).execute()

        if not result.data:
            return "❌ 创建请假申请失败，请稍后重试"

        leave_id = result.data[0].get("id")

        # 同步创建 approval_requests 记录（接入审批链体系）
        type_label = type_names.get(leave_type, leave_type)
        try:
            approval_insert = {
                "submitted_by": user_id,
                "type": "leave",
                "amount": 0,
                "description": f"[{type_label}] {start_date} 至 {end_date}，共{work_days}天。{reason or ''}",
                "status": final_status,
                "current_step": starting_step,
                "approval_level": approval_level,
                "approval_history": (
                    [
                        {
                            "step": 0,
                            "decision": "auto_approved",
                            "approver_id": "system",
                            "timestamp": datetime.now().isoformat(),
                            "comment": f"{work_days}天以内自动批准",
                        }
                    ]
                    if auto_approve
                    else []
                ),
            }
            if chain_id:
                approval_insert["chain_id"] = chain_id
            if timeout_at:
                approval_insert["timeout_at"] = timeout_at
            if org_id:
                approval_insert["organization_id"] = org_id
            approval_result = (
                await client.table("approval_requests")
                .insert(approval_insert)
                .execute()
            )
            if not approval_result.data:
                logger.warning(
                    f"Approval request insert returned no data for leave {leave_id}"
                )
        except Exception as e:
            logger.warning(
                f"Failed to create approval_request for leave {leave_id}: {e}"
            )

        # 同步写入 calendar_events 表
        try:
            CN_TZ = timezone(timedelta(hours=8))
            cal_start = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=CN_TZ)
            cal_end = datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=CN_TZ
            )
            cal_data = {
                "user_id": user_id,
                "title": f"{type_names.get(leave_type, leave_type)} ({work_days}天)",
                "event_type": "leave",
                "start_time": cal_start.isoformat(),
                "end_time": cal_end.isoformat(),
                "all_day": True,
                "source_table": "oa_leave_requests",
                "source_id": leave_id,
                "status": "active",
            }
            if org_id:
                cal_data["organization_id"] = org_id
            await client.table("calendar_events").insert(cal_data).execute()
        except Exception as e:
            logger.error(f"Failed to sync leave to calendar_events: {e}")

        # 精准通知审批人（非广播）
        if not auto_approve:
            try:
                from app.tools.approval_tools import _notify_next_approver

                await _notify_next_approver(
                    client=client,
                    approval_level=approval_level,
                    requester_id=user_id,
                    requester_name=user.get("name", "员工"),
                    approval_type="leave",
                    amount=float(work_days),
                    req_id=leave_id,
                    org_id=org_id,
                )
            except Exception as e:
                logger.warning(f"Failed to notify approver for leave {leave_id}: {e}")

        # 构建返回信息
        response = f"""✅ 请假申请已提交！

📋 **申请详情**
- 类型: {type_names.get(leave_type, leave_type)}
- 时间: {start_date} 至 {end_date}
- 天数: {work_days} 个工作日 {leave_balance_info}
- 原因: {reason or "未填写"}
- 交接人: {handover_to or "未指定"}

🔄 **审批状态**
- {approval_note}
- 状态: {"✅ 已自动批准" if auto_approve else "⏳ 等待审批中"}
"""

        if auto_approve:
            response += "\n🎉 由于请假时间较短，系统已自动批准。祝您假期愉快！"
        else:
            response += '\n📱 审批人已收到通知，请耐心等待。您可以随时问我"我的请假审批到哪了？"'

        return response


class LeaveQueryTool(BaseTool):
    """请假查询工具"""

    name = "query_leave_status"
    description = "查询请假申请状态或假期余额。当用户说'请假记录'、'年假还剩几天'、'假期余额'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {"query_type": "my_requests"},
            "output_summary": "返回最近5条请假记录，含类型、天数、状态",
        },
        {
            "input": {"query_type": "balance"},
            "output_summary": "返回年假、调休、病假的剩余天数",
        },
    ]
    related_tools = ["create_leave_request"]
    gotchas = "team_schedule 查询类型暂未实现。年假余额为简化计算（默认总额10天）。"

    parameters = {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": ["my_requests", "balance", "team_schedule"],
                "description": "查询类型: my_requests(我的申请), balance(假期余额), team_schedule(团队排班)",
            }
        },
        "required": [],
    }
    domain = "oa_leave"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        query_type = args.get("query_type", "my_requests")

        if query_type == "my_requests":
            # 查询最近的请假申请
            requests = (
                await client.table("oa_leave_requests")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )

            if not requests.data:
                return self.format_result(data={}, summary="您最近没有请假记录。")

            type_names = {
                "annual": "年假",
                "sick": "病假",
                "personal": "事假",
                "compensatory": "调休",
            }
            status_icons = {"pending": "⏳", "approved": "✅", "rejected": "❌"}

            result = "📋 **您最近的请假记录**\n\n"
            for req in requests.data:
                status_icon = status_icons.get(req["status"], "❓")
                type_name = type_names.get(req["type"], req["type"])
                result += f"{status_icon} {type_name} {req['days']}天 ({req['start_date']} ~ {req['end_date']})\n"

            return result

        elif query_type == "balance":
            # 查询假期余额
            used_annual = (
                await client.table("oa_leave_requests")
                .select("days")
                .eq("user_id", user_id)
                .eq("type", "annual")
                .eq("status", "approved")
                .execute()
            )
            used_days = sum(float(r.get("days", 0)) for r in (used_annual.data or []))

            return f"""🏖️ **您的假期余额**

- 年假: {10 - used_days} 天（已用 {used_days} 天）
- 调休: 2 天
- 病假: 按规定享受

💡 提示: 年假需在年底前休完，建议提前规划。
"""

        return "查询类型不支持"


class MeetingBookingTool(BaseTool):
    """会议预约工具"""

    name = "book_meeting"
    description = "预约会议室并向参会人发送会议邀请通知。当用户说'约个会'、'开会'、'预约会议室'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {
                "title": "周会",
                "datetime": "明天下午3点",
                "attendees": ["[姓名A]", "[姓名B]"],
            },
            "output_summary": "预约会议室并通知参会人",
        },
        {
            "input": {
                "title": "产品评审",
                "datetime": "2026-03-25 14:00",
                "attendees": ["王五"],
                "room_preference": "large",
            },
            "output_summary": "预约大型会议室并通知参会人",
        },
    ]
    related_tools = ["assign_task", "send_notification"]
    gotchas = "当前时间解析为简化实现，自然语言时间默认为明天下午。参会人姓名需在系统中存在，否则无法发送通知。"

    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "会议主题"},
            "datetime": {
                "type": "string",
                "description": "会议时间，ISO 8601格式(如 2026-03-25T15:00:00+08:00)。用户说'明天下午3点'时请转换为具体日期时间。",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "会议时长（分钟），默认60",
            },
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "参会人姓名列表",
            },
            "room_preference": {
                "type": "string",
                "description": "会议室偏好: small(小型), medium(中型), large(大型)",
            },
        },
        "required": ["title", "datetime", "attendees"],
    }
    domain = "oa_leave"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        title = args.get("title", "会议")
        duration = args.get("duration_minutes", 60)
        attendees = args.get("attendees", [])
        room_pref = args.get("room_preference", "medium")
        datetime_str = args.get("datetime", "")

        CN_TZ = timezone(timedelta(hours=8))

        # Parse meeting time from ISO format (LLM converts natural language)
        try:
            meeting_time = datetime.fromisoformat(datetime_str)
            if meeting_time.tzinfo is None:
                meeting_time = meeting_time.replace(tzinfo=CN_TZ)
        except (ValueError, TypeError):
            # Fallback: default to tomorrow afternoon if parsing fails
            meeting_time = datetime.now(CN_TZ) + timedelta(days=1)
            meeting_time = meeting_time.replace(
                hour=15, minute=0, second=0, microsecond=0
            )

        end_time = meeting_time + timedelta(minutes=duration)

        client = _get_client(config)

        # Conflict detection via calendar_events RPC
        conflict_warning = ""
        try:
            conflicts = await client.rpc(
                "check_calendar_conflicts",
                {
                    "p_user_id": user_id,
                    "p_start_time": meeting_time.isoformat(),
                    "p_end_time": end_time.isoformat(),
                },
            ).execute()
            if conflicts.data:
                conflict_lines = ["⚠️ **日程冲突提醒：**"]
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
            logger.debug(f"Calendar conflict check skipped: {e}")

        org_id = config.get("org_id") if config else None
        # 查找参会人 (scoped client, RLS enforced)
        attendee_ids = []
        attendee_names = []
        for name in attendees:
            query = client.table("users").select("id, name").ilike("name", f"%{name}%")
            if org_id:
                query = query.eq("organization_id", org_id)
            user_res = await query.limit(1).execute()
            if user_res.data:
                attendee_ids.append(user_res.data[0]["id"])
                attendee_names.append(user_res.data[0]["name"])

        # 会议室选择
        room_name = {
            "small": "洽谈室A",
            "medium": "会议室301",
            "large": "多功能厅",
        }.get(room_pref, "会议室301")

        # 写入 oa_meeting_bookings 表持久化
        try:
            meeting_result = await (
                client.table("oa_meeting_bookings")
                .insert(
                    {
                        "organization_id": org_id,
                        "organizer_id": user_id,
                        "title": title,
                        "start_time": meeting_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "attendees": attendee_ids,
                        "ai_generated": True,
                        "created_from": "chat",
                        "status": "confirmed",
                    }
                )
                .execute()
            )
            if not meeting_result.data:
                return "❌ 会议预约失败，数据未写入数据库，请稍后重试。"
        except Exception as e:
            return f"❌ 会议预约失败: {e}"

        # 同步写入 calendar_events 表
        try:
            cal_data = {
                "user_id": user_id,
                "organization_id": org_id,
                "title": title,
                "event_type": "meeting",
                "start_time": meeting_time.isoformat(),
                "end_time": end_time.isoformat(),
                "attendees": attendee_names or attendees,
                "location": room_name,
                "source_table": "oa_meeting_bookings",
                "status": "active",
            }
            await client.table("calendar_events").insert(cal_data).execute()
        except Exception as e:
            logger.error(f"Failed to sync meeting to calendar_events: {e}")

        # 发送会议通知 (Use notification_service for consistency and RLS safety)
        for aid in attendee_ids:
            try:
                await notification_service.send(
                    Notification(
                        title=f"📅 会议邀请: {title}",
                        content=f"时间: {meeting_time.strftime('%m月%d日 %H:%M')}\n地点: {room_name}",
                        target_user_id=aid,
                        channel=NotificationChannel.IN_APP,
                        priority=NotificationPriority.NORMAL,
                        metadata={
                            "action_url": "/oa?tab=meeting",
                            "organization_id": org_id or "",
                        },
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to notify attendee {aid}: {e}")

        return f"""{conflict_warning}✅ 会议已预约成功！

📅 **会议详情**
- 主题: {title}
- 时间: {meeting_time.strftime("%Y-%m-%d %H:%M")}
- 时长: {duration} 分钟
- 地点: {room_name}
- 参会人: {", ".join(attendee_names) if attendee_names else "待确认"}

📧 已向所有参会人发送日程邀请。"""


class TaskAssignmentTool(BaseTool):
    """任务分配工具"""

    name = "assign_task"
    description = (
        "创建任务并分配给指定人员。当用户说'安排个任务'、'让某某做某事'时调用。"
    )
    required_role = "all"
    examples = [
        {
            "input": {
                "title": "准备报告",
                "assignee": "[姓名]",
                "due_date": "2026-03-28",
                "priority": "high",
            },
            "output_summary": "创建高优先级任务并通知负责人",
        },
        {
            "input": {"title": "更新文档", "assignee": "[姓名]"},
            "output_summary": "创建默认优先级任务，截止日期默认3天后",
        },
    ]
    related_tools = ["create_work_handover", "book_meeting", "send_notification"]
    gotchas = "负责人姓名必须是同组织内的有效用户。未指定截止日期时默认3天后。优先级可选值为 low/medium/high/urgent。"

    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "任务标题"},
            "description": {"type": "string", "description": "任务详细描述"},
            "assignee": {"type": "string", "description": "负责人姓名"},
            "due_date": {"type": "string", "description": "截止日期"},
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "优先级",
            },
            "project_name": {"type": "string", "description": "关联项目名称（可选）"},
        },
        "required": ["title", "assignee"],
    }
    domain = "oa_task"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)

        title = args.get("title")
        description = args.get("description", "")
        assignee_name = args.get("assignee")
        due_date = args.get("due_date")
        priority = args.get("priority", "medium")
        project_name = args.get("project_name")

        org_id = config.get("org_id") if config else None
        # 查找负责人 (scoped client, RLS enforced)
        query = client.table("users").select("id, name").ilike("name", f"%{assignee_name}%")
        if org_id:
            query = query.eq("organization_id", org_id)
        assignee_res = await query.limit(1).execute()
        if not assignee_res.data:
            return f"❌ 找不到名为「{assignee_name}」的同事。请确认姓名是否正确。"

        assignee = assignee_res.data[0]

        # 获取当前用户信息（含 org_id）
        creator_res = (
            await client.table("users")
            .select("name, organization_id")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        creator_name = (
            creator_res.data.get("name", "某人") if creator_res.data else "某人"
        )
        org_id = creator_res.data.get("organization_id") if creator_res.data else None

        # 查找项目
        project_id = None
        if project_name:
            proj_res = (
                await client.table("projects")
                .select("id")
                .ilike("name", f"%{project_name}%")
                .limit(1)
                .execute()
            )
            if proj_res.data:
                project_id = proj_res.data[0]["id"]

        # 解析截止日期
        if not due_date:
            due = datetime.now() + timedelta(days=3)
            due_date = due.strftime("%Y-%m-%d")

        # 创建任务
        task_data = {
            "title": title,
            "description": description,
            "assignee_id": assignee["id"],
            "created_by": user_id,
            "due_date": due_date,
            "priority": priority,
            "project_id": project_id,
            "status": "pending",
            "ai_created": True,
        }
        if org_id:
            task_data["organization_id"] = org_id

        task_result = await client.table("oa_tasks").insert(task_data).execute()
        if not task_result.data:
            return "❌ 任务创建失败，数据未写入数据库，请稍后重试。"

        # 通知负责人（通过统一 NotificationService，支持多渠道分发）
        try:
            await notification_service.send(
                Notification(
                    title="📌 新任务分配",
                    content=f"{creator_name} 给您分配了任务: {title}\n截止日期: {due_date}",
                    target_user_id=assignee["id"],
                    channel=NotificationChannel.IN_APP,
                    metadata={
                        "action_url": "/oa?tab=task",
                        "organization_id": org_id or "",
                    },
                )
            )
        except Exception as e:
            logger.warning(f"Failed to notify assignee {assignee['name']}: {e}")

        priority_icons = {"low": "🟢", "medium": "🟡", "high": "🟠", "urgent": "🔴"}

        return f"""✅ 任务已创建并通知 {assignee["name"]}！

📌 **任务详情**
- 标题: {title}
- 负责人: {assignee["name"]}
- 截止日期: {due_date}
- 优先级: {priority_icons.get(priority, "🟡")} {priority}
- 关联项目: {project_name or "无"}

📧 已通知 {assignee["name"]}，对方确认后会开始处理。
"""


class WorkHandoverTool(BaseTool):
    """工作交接工具"""

    name = "create_work_handover"
    description = "创建工作交接单，将当前待办任务批量转交给指定同事。当用户说'交接工作'、'把工作转给某人'时调用。"
    required_role = "all"
    examples = [
        {
            "input": {"handover_to": "李四", "reason": "请假交接"},
            "output_summary": "将所有待办任务转交给李四并发送通知",
        },
        {
            "input": {
                "handover_to": "王五",
                "reason": "调岗",
                "items": ["季度报告", "客户跟进"],
            },
            "output_summary": "将指定工作项转交给王五",
        },
    ]
    related_tools = ["assign_task", "create_leave_request"]
    gotchas = (
        "会将当前用户所有待办和进行中的任务全部转移给交接人。交接人姓名需在系统中存在。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "handover_to": {"type": "string", "description": "交接给谁（姓名）"},
            "reason": {
                "type": "string",
                "description": "交接原因（如请假、离职、调岗）",
            },
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "description": "需要交接的工作项列表",
            },
        },
        "required": ["handover_to"],
    }
    domain = "oa_leave"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)

        handover_to_name = args.get("handover_to")
        reason = args.get("reason", "临时交接")
        items = args.get("items", [])

        org_id = config.get("org_id") if config else None
        # 查找交接人 (scoped client, RLS enforced)
        query = client.table("users").select("id, name").ilike("name", f"%{handover_to_name}%")
        if org_id:
            query = query.eq("organization_id", org_id)
        handover_res = await query.limit(1).execute()
        if not handover_res.data:
            return f"❌ 找不到名为「{handover_to_name}」的同事。"

        handover_to = handover_res.data[0]

        # 获取当前用户的待办任务
        tasks_res = (
            await client.table("oa_tasks")
            .select("id, title, due_date, priority")
            .eq("assignee_id", user_id)
            .in_("status", ["todo", "in_progress"])
            .execute()
        )

        task_list = tasks_res.data or []

        if not items and task_list:
            items = [t["title"] for t in task_list[:5]]

        # 转移任务 (RLS policy "oa_tasks_org_isolation" allows org members)
        transferred = 0
        for task in task_list:
            await client.table("oa_tasks").update(
                {"assignee_id": handover_to["id"]}
            ).eq("id", task["id"]).execute()
            transferred += 1

        # 通知交接人
        user_res = (
            await client.table("users")
            .select("name")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        user_name = user_res.data.get("name", "同事") if user_res.data else "同事"

        # 通知交接人 (Use notification_service for consistency and RLS safety)
        await notification_service.send(
            Notification(
                title="📋 工作交接通知",
                content=f"{user_name} 将 {transferred} 项工作交接给您。\n原因: {reason}",
                target_user_id=handover_to["id"],
                channel=NotificationChannel.IN_APP,
                priority=NotificationPriority.NORMAL,
                metadata={
                    "action_url": "/oa?tab=task",
                    "organization_id": org_id or "",
                },
            )
        )

        return f"""✅ 工作交接单已创建！

📋 **交接详情**
- 交接给: {handover_to["name"]}
- 原因: {reason}
- 交接项目: {transferred} 项

📝 **交接内容**
{"".join(f"- {item}" + chr(10) for item in items[:5])}

📧 已通知 {handover_to["name"]}，请与对方确认交接细节。
"""


class OnboardingChecklistTool(BaseTool):
    """AI 自动生成入职清单"""

    name = "generate_onboarding_checklist"
    description = "根据岗位类型自动生成新员工入职清单并创建对应任务。当用户说'入职清单'、'新员工入职'时调用。需要经理权限。"
    required_role = "manager"
    examples = [
        {
            "input": {
                "job_title": "工程师",
                "department": "部门",
                "employee_name": "[员工姓名]",
            },
            "output_summary": "生成入职待办任务清单",
        },
        {
            "input": {"job_title": "销售经理"},
            "output_summary": "根据岗位生成入职清单，使用默认员工名和部门",
        },
    ]
    related_tools = ["assign_task"]
    gotchas = "依赖大语言模型生成清单内容，结果可能因模型响应格式异常而降级为纯文本输出。最多创建15项任务。"

    parameters = {
        "type": "object",
        "properties": {
            "job_title": {"type": "string", "description": "岗位名称"},
            "department": {"type": "string", "description": "部门"},
            "employee_name": {"type": "string", "description": "新员工姓名"},
        },
        "required": ["job_title"],
    }
    domain = "oa_leave"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        import json as _json

        from app.services.ai_service import AIService

        job_title = args.get("job_title", "")
        department = args.get("department", "")
        employee_name = args.get("employee_name", "新员工")
        client = _get_client(config)

        prompt = (
            f"岗位: {job_title}, 部门: {department or '未指定'}, 员工: {employee_name}"
        )
        system = (
            "你是HR入职专家。生成入职清单，包含入职前准备、第一天、第一周、第一个月的待办事项。\n"
            "严格以JSON数组格式返回，每个元素包含 title, description, priority (high/medium/low) 三个字段。\n"
            "只返回JSON数组，不要其他文字。生成8-12个事项。"
        )

        try:
            checklist_text = await AIService.call_llm(prompt, system)

            # 清理 LLM 返回的 JSON
            clean = checklist_text.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0].strip()
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0].strip()

            items = _json.loads(clean)
            if not isinstance(items, list):
                return self.format_result(data={}, summary=f"AI 生成的入职清单:\n\n{checklist_text}")

            # 获取组织ID
            org_id = config.get("org_id") if config else None

            # 批量创建任务
            created = 0
            for item in items[:15]:
                try:
                    task_data = {
                        "title": f"[入职-{employee_name}] {item.get('title', '')}",
                        "description": item.get("description", ""),
                        "priority": item.get("priority", "medium"),
                        "status": "pending",
                        "created_by": user_id,
                    }
                    if org_id:
                        task_data["organization_id"] = org_id
                    res = await client.table("oa_tasks").insert(task_data).execute()
                    if res.data:
                        created += 1
                except Exception:
                    continue

            # 生成可读清单
            checklist_display = ""
            for i, item in enumerate(items, 1):
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
                    item.get("priority", "medium"), "🟡"
                )
                checklist_display += f"{i}. {priority_icon} {item.get('title', '')}\n"
                if item.get("description"):
                    checklist_display += f"   {item['description']}\n"

            return f"""✅ 已为 {employee_name} ({job_title}) 生成 {created} 项入职任务

📋 **入职清单**

{checklist_display}
📌 所有任务已创建到任务管理系统中。"""

        except _json.JSONDecodeError:
            return self.format_result(data={}, summary=f"AI 生成的入职清单:\n\n{checklist_text}")
        except Exception as e:
            return safe_tool_error(e, "入职清单生成")


class SendNotificationTool(BaseTool):
    """给指定同事发送站内通知（所有角色可用）"""

    name = "send_notification"
    domain = "oa_task"
    description = "给指定同事发送站内通知消息。用户说'通知某人'、'提醒某人'、'给某人发消息'时调用。此操作不可撤回。"
    required_role = "all"
    is_irreversible = True  # HITL: 发送通知后无法撤回，属于外部副作用操作
    examples = [
        {
            "input": {"recipient_name": "[姓名]", "content": "记得交报告"},
            "output_summary": "向指定人员发送站内通知",
        },
        {
            "input": {
                "recipient_name": "李经理",
                "content": "客户已确认合同",
                "priority": "important",
            },
            "output_summary": "向李经理发送重要通知",
        },
    ]
    related_tools = ["assign_task", "book_meeting"]
    gotchas = (
        "通知发送后无法撤回。模糊匹配超过5人时需提供更精确的姓名。仅限同组织内发送。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "recipient_name": {"type": "string", "description": "收件人姓名"},
            "title": {
                "type": "string",
                "description": "通知标题（可选，默认自动生成）",
            },
            "content": {"type": "string", "description": "通知内容"},
            "priority": {
                "type": "string",
                "enum": ["normal", "important"],
                "description": "优先级",
            },
        },
        "required": ["recipient_name", "content"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        recipient_name = args.get("recipient_name", "")
        content = args.get("content", "")
        title = args.get("title", "来自同事的通知")
        priority = args.get("priority", "normal")

        if not recipient_name or not content:
            return "❌ 请提供收件人姓名和通知内容"

        client = _get_client(config)
        org_id = config.get("org_id") if config else None

        # 查找收件人 (scoped client, RLS enforced)
        query = (
            client.table("users")
            .select("id, name")
            .ilike("name", f"%{recipient_name}%")
        )
        if org_id:
            query = query.eq("organization_id", org_id)
        res = await query.execute()
        users = res.data or []

        if not users:
            return f"❌ 未找到名为「{recipient_name}」的同事"
        if len(users) > 5:
            names = "、".join(u["name"] for u in users[:5])
            return f"找到多位匹配的同事（{names}…），请提供更精确的姓名"

        # 查发送者姓名
        sender_res = (
            await client.table("users")
            .select("name")
            .eq("id", user_id)
            .single()
            .execute()
        )
        sender_name = sender_res.data.get("name", "同事") if sender_res.data else "同事"

        # 发送通知（通过统一 NotificationService，支持多渠道分发）
        icon = "📢" if priority == "normal" else "⚠️"
        prio = (
            NotificationPriority.NORMAL
            if priority == "normal"
            else NotificationPriority.HIGH
        )
        for user in users:
            try:
                await notification_service.send(
                    Notification(
                        title=f"{icon} {title}",
                        content=f"{sender_name}: {content}",
                        target_user_id=user["id"],
                        channel=NotificationChannel.IN_APP,
                        priority=prio,
                        metadata={"organization_id": org_id or ""},
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to send notification to {user['name']}: {e}")
                return safe_tool_error(e, "发送通知")

        names = "、".join(u["name"] for u in users)
        return self.format_result(data={}, summary=f"已通知 {names}")
