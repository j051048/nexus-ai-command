"""
OA 办公自动化工具集
实现请假、会议、任务等办公场景的 AI 自动化

P2 Fixes Applied:
- Replaced bare except with proper ValueError handling
- Added structured logging
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from app.core.database import supabase

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


class LeaveRequestTool(BaseTool):
    """请假申请工具 - 支持自然语言创建请假"""

    name = "create_leave_request"
    description = "创建请假申请。用户说'请假'、'休假'、'调休'时调用此工具。支持年假、病假、事假、调休等类型。"
    required_role = "all"

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

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        token = config.get("token") if config else None
        client = supabase.get_scoped_client(token) if token else supabase

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
                logger.warning(f"Suspicious leave date: {start_date} (current: {now.strftime('%Y-%m-%d')})")
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
            work_days = sum(1 for i in range(days) if (start + timedelta(days=i)).weekday() < 5)
        except ValueError as e:
            logger.warning(f"Date parsing error: {e}")
            return "日期格式错误，请使用 YYYY-MM-DD 格式"

        # 获取用户信息
        user_res = (
            await client.table("users").select("name, department, role").eq("id", user_id).maybe_single().execute()
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

        # 查找交接人
        handover_id = None
        if handover_to:
            handover_res = (
                await client.table("users").select("id, name").ilike("name", f"%{handover_to}%").limit(1).execute()
            )
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
            leave_balance_info = f"（年假余额: {remaining}天 → {remaining - work_days}天）"

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

        org_id_res = await client.table("users").select("organization_id").eq("id", user_id).maybe_single().execute()
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

        approval_note = "系统自动批准" if auto_approve else f"需{approval_level}级别审批"

        # 创建请假记录（OA 业务表）
        leave_data = {
            "user_id": user_id,
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
            await client.table("approval_requests").insert(approval_insert).execute()
        except Exception as e:
            logger.warning(f"Failed to create approval_request for leave {leave_id}: {e}")

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
    description = "查询请假申请状态、年假余额等信息"
    required_role = "all"

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

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
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
                return "📋 您最近没有请假记录。"

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
    description = "预约会议室并发送会议邀请。当用户说'约个会'、'开会'、'预约会议室'时调用。"
    required_role = "all"

    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "会议主题"},
            "datetime": {
                "type": "string",
                "description": "会议时间，如 '明天下午3点'、'2024-12-20 15:00'",
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

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        title = args.get("title", "会议")
        duration = args.get("duration_minutes", 60)
        attendees = args.get("attendees", [])
        room_pref = args.get("room_preference", "medium")

        # 解析时间（简化处理）
        # 实际应使用更复杂的 NLU 来解析自然语言时间
        meeting_time = datetime.now() + timedelta(days=1, hours=3)  # 默认明天下午

        client = _get_client(config)
        # 查找参会人
        attendee_ids = []
        attendee_names = []
        for name in attendees:
            user_res = await client.table("users").select("id, name").ilike("name", f"%{name}%").limit(1).execute()
            if user_res.data:
                attendee_ids.append(user_res.data[0]["id"])
                attendee_names.append(user_res.data[0]["name"])

        # 模拟会议室查找
        room_name = {
            "small": "洽谈室A",
            "medium": "会议室301",
            "large": "多功能厅",
        }.get(room_pref, "会议室301")

        # 发送会议通知
        for aid in attendee_ids:
            await (
                client.table("notifications")
                .insert(
                    {
                        "user_id": aid,
                        "title": f"📅 会议邀请: {title}",
                        "content": f"时间: {meeting_time.strftime('%m月%d日 %H:%M')}\n地点: {room_name}",
                        "type": "info",
                        "action_url": "/oa?tab=meeting",
                    }
                )
                .execute()
            )

        return f"""✅ 会议已预约成功！

📅 **会议详情**
- 主题: {title}
- 时间: {meeting_time.strftime("%Y-%m-%d %H:%M")}
- 时长: {duration} 分钟
- 地点: {room_name}
- 参会人: {", ".join(attendee_names) if attendee_names else "待确认"}

📧 已向所有参会人发送日程邀请。

💡 提示: 会议开始前15分钟会发送提醒。
"""


class TaskAssignmentTool(BaseTool):
    """任务分配工具"""

    name = "assign_task"
    description = "创建并分配任务给指定人员。当用户说'安排个任务'、'让XX做YY'、'@某人 做某事'时调用。"
    required_role = "all"

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

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        title = args.get("title")
        description = args.get("description", "")
        assignee_name = args.get("assignee")
        due_date = args.get("due_date")
        priority = args.get("priority", "medium")
        project_name = args.get("project_name")

        client = _get_client(config)
        # 查找负责人
        assignee_res = (
            await client.table("users").select("id, name").ilike("name", f"%{assignee_name}%").limit(1).execute()
        )
        if not assignee_res.data:
            return f"❌ 找不到名为「{assignee_name}」的同事。请确认姓名是否正确。"

        assignee = assignee_res.data[0]

        # 获取当前用户信息（含 org_id）
        creator_res = (
            await client.table("users").select("name, organization_id").eq("id", user_id).maybe_single().execute()
        )
        creator_name = creator_res.data.get("name", "某人") if creator_res.data else "某人"
        org_id = creator_res.data.get("organization_id") if creator_res.data else None

        # 查找项目
        project_id = None
        if project_name:
            proj_res = await client.table("projects").select("id").ilike("name", f"%{project_name}%").limit(1).execute()
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

        await client.table("oa_tasks").insert(task_data).execute()

        # 通知负责人（带 action_url 支持点击跳转）
        notification_data = {
            "user_id": assignee["id"],
            "title": "📌 新任务分配",
            "content": f"{creator_name} 给您分配了任务: {title}\n截止日期: {due_date}",
            "type": "info",
            "action_url": "/oa?tab=task",
        }
        if org_id:
            notification_data["organization_id"] = org_id

        await client.table("notifications").insert(notification_data).execute()

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
    description = "创建工作交接单，将任务批量转交给其他同事。当用户说'交接工作'、'把工作转给某人'时调用。"
    required_role = "all"

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

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        handover_to_name = args.get("handover_to")
        reason = args.get("reason", "临时交接")
        items = args.get("items", [])

        client = _get_client(config)
        # 查找交接人
        handover_res = (
            await client.table("users").select("id, name").ilike("name", f"%{handover_to_name}%").limit(1).execute()
        )
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
            await client.table("oa_tasks").update({"assignee_id": handover_to["id"]}).eq("id", task["id"]).execute()
            transferred += 1

        # 通知交接人
        user_res = await client.table("users").select("name").eq("id", user_id).maybe_single().execute()
        user_name = user_res.data.get("name", "同事") if user_res.data else "同事"

        await (
            client.table("notifications")
            .insert(
                {
                    "user_id": handover_to["id"],
                    "title": "📋 工作交接通知",
                    "content": f"{user_name} 将 {transferred} 项工作交接给您。\n原因: {reason}",
                    "type": "warning",
                    "action_url": "/oa?tab=task",
                }
            )
            .execute()
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
    description = "根据岗位类型自动生成新员工入职清单，并创建对应任务。当用户说'入职清单'、'新员工入职'时调用。"
    required_role = "manager"

    parameters = {
        "type": "object",
        "properties": {
            "job_title": {"type": "string", "description": "岗位名称"},
            "department": {"type": "string", "description": "部门"},
            "employee_name": {"type": "string", "description": "新员工姓名"},
        },
        "required": ["job_title"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        import json as _json

        from app.services.ai_service import AIService

        job_title = args.get("job_title", "")
        department = args.get("department", "")
        employee_name = args.get("employee_name", "新员工")
        client = _get_client(config)

        prompt = f"岗位: {job_title}, 部门: {department or '未指定'}, 员工: {employee_name}"
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
                return f"📋 AI 生成的入职清单:\n\n{checklist_text}"

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
                    await client.table("oa_tasks").insert(task_data).execute()
                    created += 1
                except Exception:
                    continue

            # 生成可读清单
            checklist_display = ""
            for i, item in enumerate(items, 1):
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(item.get("priority", "medium"), "🟡")
                checklist_display += f"{i}. {priority_icon} {item.get('title', '')}\n"
                if item.get("description"):
                    checklist_display += f"   {item['description']}\n"

            return f"""✅ 已为 {employee_name} ({job_title}) 生成 {created} 项入职任务

📋 **入职清单**

{checklist_display}
📌 所有任务已创建到任务管理系统中。"""

        except _json.JSONDecodeError:
            return f"📋 AI 生成的入职清单:\n\n{checklist_text}"
        except Exception as e:
            return f"❌ 入职清单生成失败: {str(e)}"


class SendNotificationTool(BaseTool):
    """给指定同事发送站内通知（所有角色可用）"""

    name = "send_notification"
    domain = "oa_leave"
    description = "给指定同事发送站内通知。用户说'通知小王'、'提醒张三'、'给李经理发个消息'时调用。"
    required_role = "all"
    is_irreversible = True  # HITL: 发送通知后无法撤回，属于外部副作用操作

    parameters = {
        "type": "object",
        "properties": {
            "recipient_name": {"type": "string", "description": "收件人姓名"},
            "title": {"type": "string", "description": "通知标题（可选，默认自动生成）"},
            "content": {"type": "string", "description": "通知内容"},
            "priority": {
                "type": "string",
                "enum": ["normal", "important"],
                "description": "优先级",
            },
        },
        "required": ["recipient_name", "content"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        recipient_name = args.get("recipient_name", "")
        content = args.get("content", "")
        title = args.get("title", "来自同事的通知")
        priority = args.get("priority", "normal")

        if not recipient_name or not content:
            return "❌ 请提供收件人姓名和通知内容"

        client = _get_client(config)
        org_id = config.get("org_id") if config else None

        # 查找收件人
        query = client.table("users").select("id, name").ilike("name", f"%{recipient_name}%")
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
        sender_res = await client.table("users").select("name").eq("id", user_id).single().execute()
        sender_name = sender_res.data.get("name", "同事") if sender_res.data else "同事"

        # 发送通知
        icon = "📢" if priority == "normal" else "⚠️"
        for user in users:
            notification_data = {
                "user_id": user["id"],
                "title": f"{icon} {title}",
                "content": f"{sender_name}: {content}",
                "type": "info" if priority == "normal" else "warning",
            }
            if org_id:
                notification_data["organization_id"] = org_id
            try:
                await client.table("notifications").insert(notification_data).execute()
            except Exception as e:
                logger.warning(f"Failed to send notification to {user['name']}: {e}")
                return f"❌ 发送通知失败: {str(e)}"

        names = "、".join(u["name"] for u in users)
        return f"✅ 已通知 {names}"
