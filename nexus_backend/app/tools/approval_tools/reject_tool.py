import logging
import uuid
from datetime import datetime
from typing import Any

import app.tools.approval_tools as _pkg
from app.tools._shared import safe_tool_error

from ..base_tool import BaseTool

logger = logging.getLogger(__name__)


class RejectTool(BaseTool):
    """
    P0 Security Fix #1: Rejection with mandatory confirmation.
    P0 Enhancement: Uses advance_step for chain-based rejections.
    """

    name = "reject_request"
    description = "驳回一个待处理的审批申请。首次调用返回预览信息，用户确认后再次调用并传入 confirm=true 才会真正执行。此操作不可逆，需要人工确认。"
    required_role = "manager"
    is_irreversible = True
    confirmation_message = "驳回操作不可逆。请在弹出的确认框中确认后执行。"
    examples = [
        {
            "input": {
                "request_id": "a1b2c3d4-...",
                "reason": "金额不合理",
                "confirm": False,
            },
            "output_summary": "返回驳回预览信息，等待用户确认",
        },
        {
            "input": {
                "request_id": "a1b2c3d4-...",
                "reason": "超出预算",
                "confirm": True,
            },
            "output_summary": "执行驳回操作并通知申请人",
        },
    ]
    related_tools = ["approve_request", "get_pending_approvals"]
    gotchas = "reason 为必填参数，必须说明驳回原因。部门经理审批上限为5000元，超额需更高级别处理。已处理的审批单无法重复操作。"

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
    domain = "approval"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        req_id = args.get("request_id")
        reason = args.get("reason", "未说明原因")
        confirm = args.get("confirm", False)

        # Validate UUID format to prevent PostgreSQL 22P02 errors
        try:
            uuid.UUID(req_id)
        except (ValueError, TypeError, AttributeError):
            return self.format_result(data=None, summary=f"request_id '{req_id}' 不是有效的UUID格式，请检查审批单ID")

        client = _pkg._get_client(config)

        # Manager approval limit check
        user_role_res = (
            await client.table("users")
            .select("role")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        user_role = (
            user_role_res.data.get("role", "employee")
            if user_role_res.data
            else "employee"
        )

        if user_role == "manager":
            # Check if approval amount exceeds manager limit (5000)
            manager_approval_limit = 5000
            request_res = (
                await client.table("approval_requests")
                .select("amount")
                .eq("id", req_id)
                .maybe_single()
                .execute()
            )
            if (
                request_res.data
                and float(request_res.data.get("amount", 0)) > manager_approval_limit
            ):
                return self.format_result(data=None, summary=f"权限不足：部门经理审批上限为 ¥{manager_approval_limit:,}，该申请金额超出限额，需要更高级别审批")

        # Step 1: Fetch the request details first
        fetch_result = (
            await client.table("approval_requests")
            .select("*, users:submitted_by(name, department)")
            .eq("id", req_id)
            .single()
            .execute()
        )

        if not fetch_result.data:
            return self.format_result(data=None, summary=f"找不到审批单 {req_id}，请检查ID是否正确")

        request_data = fetch_result.data

        # P0 Security: Check if already processed (idempotency)
        if request_data.get("status") != "pending":
            current_status = request_data.get("status")
            return self.format_result(data=None, summary=f"该审批单已被处理，当前状态为: {current_status}，无法重复操作")

        submitter = request_data.get("users", {})
        submitter_name = (
            submitter.get("name", "未知") if isinstance(submitter, dict) else "未知"
        )

        # P0 Security Fix #1: Return preview if not confirmed
        if not confirm:
            return self.format_result(
                data=request_data,
                summary=f"驳回预览 - {submitter_name} 的 {request_data.get('type')} 申请 ¥{request_data.get('amount', 0):,.2f}，驳回原因: {reason}",
                actions=[{"label": "确认驳回", "tool": "reject_request", "args": {"request_id": req_id, "reason": reason, "confirm": True}}],
            )

        # Step 2: Execute with idempotency check
        logger.info(f"[P0 Security] User {user_id} confirmed rejection of {req_id}")

        # P0 Enhancement: Use advance_step for chain-based rejections
        chain_id = request_data.get("chain_id")
        if chain_id:
            try:
                from app.services.approval_chain import approval_chain_service

                _updated = await approval_chain_service.advance_step(
                    request_id=req_id,
                    decision="rejected",
                    approver_id=user_id,
                    comment=reason,
                    db=client,
                )

                # Record audit log
                await (
                    client.table("audit_logs")
                    .insert(
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
                    )
                    .execute()
                )

                # Send rejection notification
                await self._send_rejection_notification(client, request_data, reason)

                return self.format_result(
                    data={"request_id": req_id, "status": "rejected", "reason": reason},
                    summary=f"已驳回审批单 {req_id[:8]}...，驳回原因：{reason}",
                    actions=[
                        {"label": "查看待审批", "tool": "get_pending_approvals", "args": {}},
                        {"label": "批准申请", "tool": "approve_request", "args": {"request_id": req_id}},
                    ],
                )

            except RuntimeError as e:
                logger.warning(f"Chain advance (reject) failed for {req_id}: {e}")
                return safe_tool_error(e, "驳回")

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
            await (
                client.table("audit_logs")
                .insert(
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
                )
                .execute()
            )

            # Send rejection notification
            await self._send_rejection_notification(client, request_data, reason)

            return self.format_result(
                data={"request_id": req_id, "status": "rejected", "reason": reason},
                summary=f"已驳回审批单 {req_id[:8]}...，驳回原因：{reason}",
                actions=[
                    {"label": "查看待审批", "tool": "get_pending_approvals", "args": {}},
                    {"label": "批准申请", "tool": "approve_request", "args": {"request_id": req_id}},
                ],
            )

        return self.format_result(data=None, summary="驳回失败，该单据可能已被他人处理")

    @staticmethod
    async def _send_rejection_notification(client, request_data: dict, reason: str):
        """Send rejection notifications (in-app + multi-channel)."""
        try:
            target_user = request_data.get("submitted_by")
            await (
                client.table("notifications")
                .insert(
                    {
                        "user_id": target_user,
                        "title": "审批已驳回",
                        "content": f"您的{request_data.get('type', '')}申请已被驳回。原因：{reason}",
                        "type": "error",
                        "action_url": "/approval",
                    }
                )
                .execute()
            )
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
