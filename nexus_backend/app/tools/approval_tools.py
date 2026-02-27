"""
P0 Security: Approval Tools with Human Confirmation
Critical security fix #1: AI cannot directly execute irreversible operations
All approval/reject operations now require explicit confirmation.
P0 Enhancement: Uses advance_step for chain-based approvals.
"""

import logging
from datetime import datetime
from typing import Any

from app.core.database import supabase

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


# AI Assistant 固定 UUID
AI_ASSISTANT_ID = "00000000-0000-0000-0000-000000000001"

# P0 Security Fix #1: Maximum batch size for approvals
MAX_BATCH_SIZE = 10


class SubmitApprovalOnBehalfTool(BaseTool):
    """AI助手代员工提交审批申请 - 自动使用当前登录用户的身份"""

    name = "submit_approval_on_behalf"
    description = "代表当前用户提交审批申请（出差、请假、报销等）。无需传入员工ID，系统会自动使用当前登录用户的身份。"
    required_role = "ai_assistant"  # 允许通过 AI 调用

    parameters = {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["travel", "leave", "expense", "purchase"],
                "description": "审批类型：travel=出差, leave=请假, expense=报销, purchase=采购",
            },
            "amount": {"type": "number", "description": "金额（如适用，默认0）"},
            "description": {"type": "string", "description": "详细说明申请事由"},
            "start_date": {"type": "string", "description": "开始日期（如适用）"},
            "end_date": {"type": "string", "description": "结束日期（如适用）"},
        },
        "required": ["type", "description"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        # 使用当前登录用户的 ID（从 JWT 解析出来的）
        employee_id = user_id
        approval_type = args.get("type")
        amount = args.get("amount", 0)
        description = args.get("description")
        start_date = args.get("start_date", "")
        end_date = args.get("end_date", "")

        logger.info(f"[AI审批] 当前用户ID: {user_id}, 申请类型: {approval_type}")

        # 验证员工存在
        employee_check = await client.table("users").select("id, name, role").eq("id", employee_id).single().execute()
        if not employee_check.data:
            return f"错误：找不到您的用户信息（ID: {employee_id}）"

        actual_employee = employee_check.data
        employee_name = actual_employee.get("name", "未知")

        if actual_employee.get("role") == "founder":
            return "错误：老板无需通过AI提交审批申请，您可以直接审批"

        # 构建详情
        full_details = description
        if start_date or end_date:
            full_details += f"\n日期：{start_date} 至 {end_date}"

        # 插入审批记录 - 关键：submitted_by 是员工ID，不是AI的ID
        try:
            insert_data = {
                "submitted_by": employee_id,  # 归属于员工
                "on_behalf_of": employee_id,
                "submitted_via": "ai_assistant",
                "type": approval_type,
                "amount": amount,
                "description": full_details,
                "status": "pending",
                "ai_reason": f"由AI助手豆豆代{actual_employee.get('name', employee_name)}提交",
            }
            logger.debug(f"[AI审批] 准备插入数据: {insert_data}")

            result = await client.table("approval_requests").insert(insert_data).execute()
            logger.debug("[AI审批] 插入结果成功")
        except Exception as e:
            logger.exception(f"[AI审批] 插入失败: {e}")
            return f"提交失败：数据库错误 - {str(e)}"

        if result.data:
            req_id = result.data[0].get("id")
            # 记录审计日志
            await client.table("audit_logs").insert(
                {
                    "action": "approval_submitted_via_ai",
                    "actor_user_id": AI_ASSISTANT_ID,
                    "target_id": req_id,
                    "target_table": "approval_requests",
                    "details_json": {
                        "employee_id": employee_id,
                        "employee_name": actual_employee.get("name"),
                        "type": approval_type,
                        "amount": amount,
                    },
                }
            ).execute()

            return f"已成功为您（{employee_name}）提交{approval_type}申请（单号：{req_id[:8]}...）。老板会在审批中心看到这个申请，申请人显示为您的名字。"

        return "提交失败，请稍后重试。"


class GetEmployeeInfoTool(BaseTool):
    """AI助手查询员工信息"""

    name = "get_employee_info"
    description = "根据员工姓名查询其ID和基本信息，用于后续代理操作"
    required_role = "ai_assistant"

    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "员工姓名关键词"},
            "employee_name": {"type": "string", "description": "员工姓名（query的别名）"},
        },
        "required": ["query"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        name = args.get("query") or args.get("employee_name")
        if not name:
            return "请提供员工姓名关键词"
        client = _get_client(config)
        result = await client.table("users").select("id, name, department, role").ilike("name", f"%{name}%").execute()

        if not result.data:
            return f"找不到名为 '{name}' 的员工。"

        employees = []
        for emp in result.data:
            if emp.get("role") != "founder":  # 不返回老板信息
                employees.append(f"- {emp['name']}（ID: {emp['id']}, 部门: {emp.get('department', '未知')}）")

        if not employees:
            return f"找不到名为 '{name}' 的普通员工。"

        return "找到以下员工：\n" + "\n".join(employees)


class GetEmployeeApprovalHistoryTool(BaseTool):
    """AI助手查询员工的审批历史"""

    name = "get_employee_approval_history"
    description = "查询指定员工的审批申请历史记录"
    required_role = "ai_assistant"

    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {"type": "string", "description": "员工ID"},
            "limit": {"type": "integer", "description": "返回记录数量，默认5条"},
        },
        "required": ["employee_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        employee_id = args.get("employee_id")
        limit = args.get("limit", 5)

        client = _get_client(config)
        result = (
            await client.table("approval_requests")
            .select("*")
            .eq("submitted_by", employee_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        if not result.data:
            return "该员工暂无审批记录。"

        records = []
        for item in result.data:
            via = "(AI代提交)" if item.get("submitted_via") == "ai_assistant" else ""
            records.append(
                f"- [{item['status']}] {item['type']} ¥{item.get('amount', 0)} {via}\n  {item.get('description', '')[:50]}..."
            )

        return f"最近{len(records)}条审批记录：\n" + "\n".join(records)


class ApprovalTool(BaseTool):
    """
    P0 Security Fix #1: Approval with mandatory confirmation

    This tool now operates in two modes:
    1. Preview mode (default): Shows what will be approved, requires user confirmation
    2. Execute mode: Actually performs the approval after user confirms

    P0 Enhancement: When the approval request has a chain_id, uses advance_step
    to properly route through the approval chain instead of direct status update.
    """

    name = "approve_request"
    description = """批准一个待处理的审批申请。
首次调用时会返回待审批信息的预览，需要用户确认后再次调用并传入 confirm=true 才会真正执行。
这是一个不可逆操作，需要人工确认。"""
    required_role = "manager"
    is_irreversible = True
    confirmation_message = "审批操作不可逆。请确认后设置 confirm=true 再执行。"

    parameters = {
        "type": "object",
        "properties": {
            "request_id": {"type": "string", "description": "审批单的唯一ID"},
            "reason": {"type": "string", "description": "批准的原因（可选）"},
            "confirm": {
                "type": "boolean",
                "description": "是否确认执行？首次调用请设为false获取预览，确认后设为true执行",
            },
        },
        "required": ["request_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        req_id = args.get("request_id")
        reason = args.get("reason", "")
        confirm = args.get("confirm", False)

        client = _get_client(config)

        # Manager approval limit check
        user_role_res = await client.table("users").select("role").eq("id", user_id).maybe_single().execute()
        user_role = user_role_res.data.get("role", "employee") if user_role_res.data else "employee"

        if user_role == "manager":
            # Check if approval amount exceeds manager limit (5000)
            manager_approval_limit = 5000
            request_res = (
                await client.table("approval_requests").select("amount").eq("id", req_id).maybe_single().execute()
            )
            if request_res.data and float(request_res.data.get("amount", 0)) > manager_approval_limit:
                return f"权限不足：部门经理审批上限为 ¥{manager_approval_limit:,}，该申请金额超出限额，需要更高级别审批。"

        # Step 1: Fetch the request details first
        fetch_result = (
            await client.table("approval_requests")
            .select("*, users:submitted_by(name, department)")
            .eq("id", req_id)
            .single()
            .execute()
        )

        if not fetch_result.data:
            return f"找不到审批单 {req_id}，请检查ID是否正确。"

        request_data = fetch_result.data

        # P0 Security: Check if already processed (idempotency)
        if request_data.get("status") != "pending":
            current_status = request_data.get("status")
            return f"该审批单已被处理，当前状态为: {current_status}。无法重复操作。"

        submitter = request_data.get("users", {})
        submitter_name = submitter.get("name", "未知") if isinstance(submitter, dict) else "未知"

        # P0 Security Fix #1: Return preview if not confirmed
        if not confirm:
            chain_info = ""
            if request_data.get("chain_id"):
                step = request_data.get("current_step", 0)
                level = request_data.get("approval_level", "")
                chain_info = f"\n• 审批链步骤: 第{step + 1}步 ({level})"

            return f"""**审批预览** - 请确认后执行

**申请信息**
- 单号: {req_id[:8]}...
- 申请人: {submitter_name}
- 类型: {request_data.get('type', '未知')}
- 金额: ¥{request_data.get('amount', 0):,.2f}
- 说明: {request_data.get('description', '无')[:100]}
- 提交时间: {request_data.get('created_at', '未知')[:10]}{chain_info}

**这是一个不可逆操作**
如确认批准，请说「确认批准」或重新调用工具并设置 confirm=true"""

        # Step 2: Execute with idempotency check
        logger.info(f"[P0 Security] User {user_id} confirmed approval of {req_id}")

        # P0 Enhancement: Use advance_step for chain-based approvals
        chain_id = request_data.get("chain_id")
        if chain_id:
            try:
                from app.services.approval_chain import approval_chain_service

                updated = await approval_chain_service.advance_step(
                    request_id=req_id,
                    decision="approved",
                    approver_id=user_id,
                    comment=reason or "已批准",
                    db=client,
                )

                new_status = updated.get("status", "pending")
                current_step = updated.get("current_step", 0)
                approval_level = updated.get("approval_level", "")

                # Record audit log
                await client.table("audit_logs").insert(
                    {
                        "action": "approval_advanced",
                        "actor_user_id": user_id,
                        "target_id": req_id,
                        "target_table": "approval_requests",
                        "details_json": {
                            "amount": request_data.get("amount"),
                            "type": request_data.get("type"),
                            "submitter": submitter_name,
                            "chain_id": chain_id,
                            "new_step": current_step,
                            "new_status": new_status,
                        },
                    }
                ).execute()

                if new_status == "approved":
                    # Send final approval notification
                    await self._send_approval_notification(client, request_data, submitter_name)
                    return (
                        f"已批准审批单 {req_id[:8]}...（{submitter_name} 的 "
                        f"{request_data.get('type')} 申请，¥{request_data.get('amount', 0):,.2f}）"
                        f"\n审批链已全部通过。"
                    )
                else:
                    return (
                        f"已批准审批单 {req_id[:8]}... 当前步骤。"
                        f"\n审批已推进到第 {current_step + 1} 步（{approval_level}），等待下一级审批。"
                    )

            except RuntimeError as e:
                logger.warning(f"Chain advance failed for {req_id}: {e}")
                return f"审批推进失败: {str(e)}"

        # Fallback: Direct status update for non-chain approvals (backward compatible)
        result = (
            await client.table("approval_requests")
            .update(
                {
                    "status": "approved",
                    "approved_by": user_id,
                    "approved_at": datetime.now().isoformat(),
                    "approval_comment": reason or "已批准",
                }
            )
            .eq("id", req_id)
            .eq("status", "pending")
            .execute()
        )  # Only update if still pending

        if result.data:
            # Record audit log
            await client.table("audit_logs").insert(
                {
                    "action": "approval_approved",
                    "actor_user_id": user_id,
                    "target_id": req_id,
                    "target_table": "approval_requests",
                    "details_json": {
                        "amount": request_data.get("amount"),
                        "type": request_data.get("type"),
                        "submitter": submitter_name,
                    },
                }
            ).execute()

            # Send notification
            await self._send_approval_notification(client, request_data, submitter_name)

            return (
                f"已成功批准审批单 {req_id[:8]}..."
                f"（{submitter_name} 的 {request_data.get('type')} 申请，"
                f"¥{request_data.get('amount', 0):,.2f}）"
            )

        return "批准失败，该单据可能已被他人处理。"

    @staticmethod
    async def _send_approval_notification(client, request_data: dict, submitter_name: str):
        """Send approval notifications (in-app + multi-channel)."""
        try:
            target_user = request_data.get("submitted_by")
            await client.table("notifications").insert(
                {
                    "user_id": target_user,
                    "title": "审批已通过",
                    "content": f"您的{request_data.get('type', '')}申请（¥{request_data.get('amount', 0)}）已被批准。",
                    "type": "success",
                }
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")

        # Multi-channel notification via notification_service
        try:
            from app.services.notification_service import (
                Notification,
                NotificationChannel,
                NotificationPriority,
                notification_service,
            )

            await notification_service.send(
                Notification(
                    title="审批已通过",
                    content=(
                        f"您的{request_data.get('type', '')}申请"
                        f"（¥{request_data.get('amount', 0):,.0f}）已被批准"
                    ),
                    target_user_id=request_data.get("submitted_by"),
                    channel=NotificationChannel.IN_APP,
                    priority=NotificationPriority.HIGH,
                )
            )
        except Exception as e:
            logger.warning(f"Multi-channel approval notification failed: {e}")


class RejectTool(BaseTool):
    """
    P0 Security Fix #1: Rejection with mandatory confirmation.
    P0 Enhancement: Uses advance_step for chain-based rejections.
    """

    name = "reject_request"
    description = """驳回一个待处理的审批申请。
首次调用时会返回待驳回信息的预览，需要用户确认后再次调用并传入 confirm=true 才会真正执行。
这是一个不可逆操作，需要人工确认。"""
    required_role = "manager"
    is_irreversible = True
    confirmation_message = "驳回操作不可逆。请确认后设置 confirm=true 再执行。"

    parameters = {
        "type": "object",
        "properties": {
            "request_id": {"type": "string", "description": "审批单的唯一ID"},
            "reason": {"type": "string", "description": "驳回的原因（必须说明）"},
            "confirm": {
                "type": "boolean",
                "description": "是否确认执行？首次调用请设为false获取预览，确认后设为true执行",
            },
        },
        "required": ["request_id", "reason"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        req_id = args.get("request_id")
        reason = args.get("reason", "未说明原因")
        confirm = args.get("confirm", False)

        client = _get_client(config)

        # Manager approval limit check
        user_role_res = await client.table("users").select("role").eq("id", user_id).maybe_single().execute()
        user_role = user_role_res.data.get("role", "employee") if user_role_res.data else "employee"

        if user_role == "manager":
            # Check if approval amount exceeds manager limit (5000)
            manager_approval_limit = 5000
            request_res = (
                await client.table("approval_requests").select("amount").eq("id", req_id).maybe_single().execute()
            )
            if request_res.data and float(request_res.data.get("amount", 0)) > manager_approval_limit:
                return f"权限不足：部门经理审批上限为 ¥{manager_approval_limit:,}，该申请金额超出限额，需要更高级别审批。"

        # Step 1: Fetch the request details first
        fetch_result = (
            await client.table("approval_requests")
            .select("*, users:submitted_by(name, department)")
            .eq("id", req_id)
            .single()
            .execute()
        )

        if not fetch_result.data:
            return f"找不到审批单 {req_id}，请检查ID是否正确。"

        request_data = fetch_result.data

        # P0 Security: Check if already processed (idempotency)
        if request_data.get("status") != "pending":
            current_status = request_data.get("status")
            return f"该审批单已被处理，当前状态为: {current_status}。无法重复操作。"

        submitter = request_data.get("users", {})
        submitter_name = submitter.get("name", "未知") if isinstance(submitter, dict) else "未知"

        # P0 Security Fix #1: Return preview if not confirmed
        if not confirm:
            return f"""**驳回预览** - 请确认后执行

**申请信息**
- 单号: {req_id[:8]}...
- 申请人: {submitter_name}
- 类型: {request_data.get('type', '未知')}
- 金额: ¥{request_data.get('amount', 0):,.2f}
- 说明: {request_data.get('description', '无')[:100]}

**驳回原因**
{reason}

**这是一个不可逆操作**
如确认驳回，请说「确认驳回」或重新调用工具并设置 confirm=true"""

        # Step 2: Execute with idempotency check
        logger.info(f"[P0 Security] User {user_id} confirmed rejection of {req_id}")

        # P0 Enhancement: Use advance_step for chain-based rejections
        chain_id = request_data.get("chain_id")
        if chain_id:
            try:
                from app.services.approval_chain import approval_chain_service

                updated = await approval_chain_service.advance_step(
                    request_id=req_id,
                    decision="rejected",
                    approver_id=user_id,
                    comment=reason,
                    db=client,
                )

                # Record audit log
                await client.table("audit_logs").insert(
                    {
                        "action": "approval_rejected",
                        "actor_user_id": user_id,
                        "target_id": req_id,
                        "target_table": "approval_requests",
                        "details_json": {
                            "amount": request_data.get("amount"),
                            "type": request_data.get("type"),
                            "submitter": submitter_name,
                            "reason": reason,
                            "chain_id": chain_id,
                        },
                    }
                ).execute()

                # Send rejection notification
                await self._send_rejection_notification(client, request_data, reason)

                return f"已驳回审批单 {req_id[:8]}...。驳回原因：{reason}"

            except RuntimeError as e:
                logger.warning(f"Chain advance (reject) failed for {req_id}: {e}")
                return f"驳回失败: {str(e)}"

        # Fallback: Direct status update for non-chain rejections (backward compatible)
        result = (
            await client.table("approval_requests")
            .update(
                {
                    "status": "rejected",
                    "approved_by": user_id,
                    "approved_at": datetime.now().isoformat(),
                    "approval_comment": reason,
                }
            )
            .eq("id", req_id)
            .eq("status", "pending")
            .execute()
        )  # Only update if still pending

        if result.data:
            # Record audit log
            await client.table("audit_logs").insert(
                {
                    "action": "approval_rejected",
                    "actor_user_id": user_id,
                    "target_id": req_id,
                    "target_table": "approval_requests",
                    "details_json": {
                        "amount": request_data.get("amount"),
                        "type": request_data.get("type"),
                        "submitter": submitter_name,
                        "reason": reason,
                    },
                }
            ).execute()

            # Send rejection notification
            await self._send_rejection_notification(client, request_data, reason)

            return f"已驳回审批单 {req_id[:8]}...。驳回原因：{reason}"

        return "驳回失败，该单据可能已被他人处理。"

    @staticmethod
    async def _send_rejection_notification(client, request_data: dict, reason: str):
        """Send rejection notifications (in-app + multi-channel)."""
        try:
            target_user = request_data.get("submitted_by")
            await client.table("notifications").insert(
                {
                    "user_id": target_user,
                    "title": "审批已驳回",
                    "content": f"您的{request_data.get('type', '')}申请已被驳回。原因：{reason}",
                    "type": "error",
                }
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")

        # Multi-channel notification via notification_service
        try:
            from app.services.notification_service import (
                Notification,
                NotificationChannel,
                NotificationPriority,
                notification_service,
            )

            await notification_service.send(
                Notification(
                    title="审批已驳回",
                    content=f"您的{request_data.get('type', '')}申请已被驳回。原因：{reason}",
                    target_user_id=request_data.get("submitted_by"),
                    channel=NotificationChannel.IN_APP,
                    priority=NotificationPriority.HIGH,
                )
            )
        except Exception as e:
            logger.warning(f"Multi-channel rejection notification failed: {e}")


class PendingApprovalsTool(BaseTool):
    name = "get_pending_approvals"
    description = "获取当前所有待处理的异常审批列表"

    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        result = (
            await client.table("approval_requests")
            .select("*, users:submitted_by(name)")
            .eq("status", "pending")
            .execute()
        )
        if not result.data:
            return "当前没有任何待处理的审批。"
        items = []
        for item in result.data:
            user_name = item.get("users", {}).get("name", "未知用户")
            chain_info = ""
            if item.get("chain_id"):
                step = item.get("current_step", 0)
                level = item.get("approval_level", "")
                chain_info = f" [步骤{step + 1}/{level}]"
            items.append(
                f"ID: {item['id']}, 申请人: {user_name}, 类型: {item['type']}, "
                f"金额: ¥{item['amount']}, 描述: {item['description']}{chain_info}"
            )
        return "待处理清单：\n" + "\n".join(items)
