"""
智能审批工具 - 支持批量审批、条件审批、委托审批

P0 Security Fix #1: All approval operations require explicit confirmation
"""

import logging
from datetime import datetime
from typing import Any

from ..base_tool import BaseTool
from ..boss_shared import MAX_BATCH_SIZE, _get_client, _parse_amount_from_condition

logger = logging.getLogger(__name__)


class SmartApprovalTool(BaseTool):
    """
    智能审批工具 - 支持批量审批、条件审批、委托审批

    P0 Security Fix #1:
    - All operations require explicit confirm=true
    - Batch operations limited to MAX_BATCH_SIZE
    - Idempotency checks prevent duplicate processing
    """

    name = "smart_approve"
    description = """批量处理或按条件处理待审批事项。当领导说'批量审批'、'5000以下的都批'、'一键通过'时调用。注意：单条审批用 approve_request 或 reject_request。
首次调用返回预览信息，需要确认后设置 confirm=true 才会真正执行。
这是不可逆操作，需要人工确认。"""
    required_role = "boss"
    domain = "approval"
    is_irreversible = True
    confirmation_message = "⚠️ 审批操作不可逆。请在弹出的确认框中确认后执行。"
    examples = [
        {
            "input": {"action": "batch_approve", "confirm": False},
            "output_summary": "返回所有待审批事项的预览列表，等待确认",
        },
        {
            "input": {
                "action": "conditional_approve",
                "condition": "金额小于5000的全部通过",
                "confirm": True,
            },
            "output_summary": "批准所有金额小于5000的申请",
        },
        {
            "input": {"action": "delegate", "delegate_to": "张三", "confirm": True},
            "output_summary": "将待审批事项委托给张三处理",
        },
    ]
    gotchas = "仅老板或创始人角色可用。必须先以 confirm=false 获取预览，再以 confirm=true 执行。单次批量上限由 MAX_BATCH_SIZE 控制。"
    related_tools = ["get_pending_approvals", "get_daily_briefing"]
    depends_on = ["get_pending_approvals"]

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "approve",
                    "reject",
                    "delegate",
                    "batch_approve",
                    "conditional_approve",
                ],
                "description": "操作类型: approve(批准), reject(驳回), delegate(委托), batch_approve(批量批准), conditional_approve(条件批准)",
            },
            "request_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要处理的申请ID列表（可选，不填则处理全部待审批）",
            },
            "request_numbers": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "要处理的申请序号列表，如[1,2,3]表示第1、2、3条",
            },
            "condition": {
                "type": "string",
                "description": "审批条件，如'金额小于5000的全部通过'",
            },
            "delegate_to": {"type": "string", "description": "委托给谁（姓名）"},
            "comment": {"type": "string", "description": "审批意见"},
            "confirm": {
                "type": "boolean",
                "description": "是否确认执行？首次调用请设为false获取预览，确认后设为true执行",
            },
        },
        "required": ["action"],
    }

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _get_client(config)
        action = args.get("action", "approve")
        request_ids = args.get("request_ids", [])
        request_numbers = args.get("request_numbers", [])
        condition = args.get("condition", "")
        delegate_to = args.get("delegate_to", "")
        comment = args.get("comment", "")
        confirm = args.get("confirm", False)  # P0 Security: Default to preview mode

        # 获取待审批列表
        pending_res = (
            await client.table("approval_requests")
            .select("*, users:submitted_by(name, department)")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )

        pending_list = pending_res.data or []

        if not pending_list:
            return self.format_result(
                data=None,
                summary="当前没有待审批的事项，您可以放心休息",
            )

        # 根据序号筛选
        if request_numbers:
            selected_requests = [
                pending_list[i - 1]
                for i in request_numbers
                if 0 < i <= len(pending_list)
            ]
        elif request_ids:
            selected_requests = [r for r in pending_list if r["id"] in request_ids]
        else:
            selected_requests = pending_list

        # 条件筛选
        if condition:
            if "小于" in condition or "<" in condition:
                amount_threshold = _parse_amount_from_condition(condition)
                if amount_threshold is not None:
                    selected_requests = [
                        r
                        for r in selected_requests
                        if float(r.get("amount", 0)) < amount_threshold
                    ]
                else:
                    logger.warning(
                        f"Failed to parse amount threshold from condition: {condition}"
                    )
            elif "大于" in condition or ">" in condition:
                amount_threshold = _parse_amount_from_condition(condition)
                if amount_threshold is not None:
                    selected_requests = [
                        r
                        for r in selected_requests
                        if float(r.get("amount", 0)) > amount_threshold
                    ]
                else:
                    logger.warning(
                        f"Failed to parse amount threshold from condition: {condition}"
                    )

        if not selected_requests:
            return self.format_result(
                data=None,
                summary="没有符合条件的审批事项",
            )

        # P0 Security: Limit batch size
        if len(selected_requests) > MAX_BATCH_SIZE:
            return self.format_result(
                data={"max_batch_size": MAX_BATCH_SIZE, "total_matching": len(selected_requests)},
                summary=f"安全限制：单次批量操作最多处理{MAX_BATCH_SIZE}条，当前符合条件{len(selected_requests)}条，请分批处理",
            )

        # Calculate totals for preview
        total_amount = sum(float(r.get("amount", 0)) for r in selected_requests)

        # P0 Security Fix #1: Return preview if not confirmed
        if not confirm:
            action_name = {
                "approve": "批准",
                "reject": "驳回",
                "delegate": "委托",
                "batch_approve": "批量批准",
            }.get(action, action)

            preview_items = []
            for i, req in enumerate(selected_requests[:5], 1):
                user_info = req.get("users", {})
                user_name = (
                    user_info.get("name", "未知")
                    if isinstance(user_info, dict)
                    else "未知"
                )
                preview_items.append({
                    "index": i,
                    "user_name": user_name,
                    "type": req.get("type", "未知"),
                    "amount": float(req.get("amount", 0)),
                })

            return self.format_result(
                data={
                    "action": action_name,
                    "count": len(selected_requests),
                    "total_amount": total_amount,
                    "preview_items": preview_items,
                    "remaining": max(0, len(selected_requests) - 5),
                },
                summary=f"{action_name}预览: {len(selected_requests)}件，共¥{total_amount:,.2f}，请确认后执行",
                actions=[{"label": f"确认{action_name}", "tool": "smart_approve", "args": {"action": action, "confirm": True}}],
            )

        # P0 Security: Log the confirmed action
        logger.info(
            f"[P0 Security] User {user_id} confirmed {action} for {len(selected_requests)} requests"
        )

        # 执行操作
        if action == "approve" or action == "batch_approve":
            # Use advance_step for chain-bound requests, fallback to RPC for others
            from app.services.approval_chain import approval_chain_service

            approved_count = 0
            skipped_count = 0
            updated_ids = set()
            rpc_ids = []  # requests without chain_id use batch RPC

            for req in selected_requests:
                if req.get("chain_id"):
                    # Has approval chain: use advance_step for proper multi-level flow
                    try:
                        updated = await approval_chain_service.advance_step(
                            request_id=req["id"],
                            decision="approved",
                            approver_id=user_id,
                            comment=comment or "已批准",
                            db=client,
                        )
                        updated_ids.add(req["id"])
                        approved_count += 1

                        # If still pending (promoted to next level), notify next approver
                        if updated.get("status") == "pending":
                            try:
                                from app.tools.approval_tools import (
                                    _notify_next_approver,
                                )

                                user_info = req.get("users", {})
                                req_name = (
                                    user_info.get("name", "员工")
                                    if isinstance(user_info, dict)
                                    else "员工"
                                )
                                await _notify_next_approver(
                                    client=client,
                                    approval_level=updated.get(
                                        "approval_level", "manager"
                                    ),
                                    requester_id=req["submitted_by"],
                                    requester_name=req_name,
                                    approval_type=req.get("type", "default"),
                                    amount=float(req.get("amount", 0)),
                                    req_id=req["id"],
                                    org_id=req.get("organization_id"),
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to notify next approver for {req['id']}: {e}"
                                )
                    except Exception as e:
                        logger.warning(f"advance_step failed for {req['id']}: {e}")
                        skipped_count += 1
                else:
                    rpc_ids.append(req["id"])

            # Batch RPC for requests without chain
            if rpc_ids:
                try:
                    rpc_result = await client.rpc(
                        "batch_update_approvals",
                        {
                            "p_request_ids": rpc_ids,
                            "p_new_status": "approved",
                            "p_approved_by": user_id,
                            "p_comment": comment or "已批准",
                        },
                    ).execute()

                    batch_data = rpc_result.data or {}
                    approved_count += batch_data.get("updated_count", 0)
                    skipped_count += batch_data.get("skipped_count", 0)
                    updated_ids.update(batch_data.get("updated_ids", []))
                except Exception as e:
                    logger.error(f"Batch approval RPC failed: {e}")
                    skipped_count += len(rpc_ids)

            # Send notifications for successfully approved requests (non-transactional, best-effort)
            for req in selected_requests:
                if req["id"] in updated_ids:
                    try:
                        await (
                            client.table("notifications")
                            .insert(
                                {
                                    "user_id": req["submitted_by"],
                                    "title": "✅ 您的申请已批准",
                                    "content": f"您提交的{req.get('type', '申请')}（¥{req.get('amount', 0)}）已被批准",
                                    "type": "success",
                                }
                            )
                            .execute()
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send approval notification: {e}")

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
                                title="✅ 您的申请已批准",
                                content=f"您提交的{req.get('type', '申请')}（¥{req.get('amount', 0):,.0f}）已被批准",
                                target_user_id=req["submitted_by"],
                                channel=NotificationChannel.IN_APP,
                                priority=NotificationPriority.NORMAL,
                            )
                        )
                    except Exception as e:
                        logger.warning(
                            f"Multi-channel approval notification failed: {e}"
                        )

            return self.format_result(
                data={
                    "approved_count": approved_count,
                    "skipped_count": skipped_count,
                    "total_amount": total_amount,
                    "processed_at": datetime.now().strftime("%H:%M:%S"),
                },
                summary=f"批量审批完成，批准{approved_count}件，跳过{skipped_count}件，涉及金额¥{total_amount:,.2f}",
                actions=[{"label": "查看每日简报", "tool": "get_daily_briefing", "args": {}}],
            )

        elif action == "reject":
            # Use advance_step for chain-bound requests, fallback to RPC for others
            from app.services.approval_chain import approval_chain_service

            rejected_count = 0
            skipped_count = 0
            updated_ids = set()
            rpc_ids = []

            for req in selected_requests:
                if req.get("chain_id"):
                    try:
                        await approval_chain_service.advance_step(
                            request_id=req["id"],
                            decision="rejected",
                            approver_id=user_id,
                            comment=comment or "已驳回",
                            db=client,
                        )
                        updated_ids.add(req["id"])
                        rejected_count += 1
                    except Exception as e:
                        logger.warning(
                            f"advance_step (reject) failed for {req['id']}: {e}"
                        )
                        skipped_count += 1
                else:
                    rpc_ids.append(req["id"])

            if rpc_ids:
                try:
                    rpc_result = await client.rpc(
                        "batch_update_approvals",
                        {
                            "p_request_ids": rpc_ids,
                            "p_new_status": "rejected",
                            "p_approved_by": user_id,
                            "p_comment": comment or "已驳回",
                        },
                    ).execute()

                    batch_data = rpc_result.data or {}
                    rejected_count += batch_data.get("updated_count", 0)
                    skipped_count += batch_data.get("skipped_count", 0)
                    updated_ids.update(batch_data.get("updated_ids", []))
                except Exception as e:
                    logger.error(f"Batch rejection RPC failed: {e}")
                    skipped_count += len(rpc_ids)

            # Send notifications (best-effort)
            for req in selected_requests:
                if req["id"] in updated_ids:
                    try:
                        await (
                            client.table("notifications")
                            .insert(
                                {
                                    "user_id": req["submitted_by"],
                                    "title": "❌ 您的申请被驳回",
                                    "content": f"您提交的{req.get('type', '申请')}被驳回。原因: {comment or '未说明'}",
                                    "type": "warning",
                                }
                            )
                            .execute()
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send rejection notification: {e}")

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
                                title="❌ 您的申请被驳回",
                                content=f"您提交的{req.get('type', '申请')}（¥{req.get('amount', 0):,.0f}）被驳回。原因: {comment or '未说明'}",
                                target_user_id=req["submitted_by"],
                                channel=NotificationChannel.IN_APP,
                                priority=NotificationPriority.HIGH,
                            )
                        )
                    except Exception as e:
                        logger.warning(
                            f"Multi-channel rejection notification failed: {e}"
                        )

            return f"""❌ 已驳回 {rejected_count} 件申请

驳回原因: {comment or "未说明"}
跳过数量: {skipped_count} 件（已被他人处理）
📧 已通知相关申请人
"""

        elif action == "delegate":
            if not delegate_to:
                return "❌ 请指定委托人"

            # 查找委托人
            delegate_res = (
                await client.table("users")
                .select("id, name")
                .ilike("name", f"%{delegate_to}%")
                .limit(1)
                .execute()
            )
            if not delegate_res.data:
                return f"❌ 未找到名为「{delegate_to}」的人员"

            delegate_user = delegate_res.data[0]

            # 更新审批人 (委托不是不可逆操作，可以重新委托)
            # RLS policy "approval_admin_update" allows boss/admin in same org
            for req in selected_requests:
                await (
                    client.table("approval_requests")
                    .update({"current_approver": delegate_user["id"]})
                    .eq("id", req["id"])
                    .eq("status", "pending")
                    .execute()
                )

            # 通知被委托人
            await (
                client.table("notifications")
                .insert(
                    {
                        "user_id": delegate_user["id"],
                        "title": "📋 收到委托审批",
                        "content": f"领导将 {len(selected_requests)} 件审批事项委托给您处理",
                        "type": "warning",
                    }
                )
                .execute()
            )

            return f"""✅ 已委托给 {delegate_user["name"]}

委托事项: {len(selected_requests)} 件
📧 已通知 {delegate_user["name"]}
"""

        return "未知操作"

    def _format_request_list(self, requests: list[dict]) -> str:
        result = ""
        type_icons = {"expense": "💰", "leave": "🏖️", "purchase": "🛒", "travel": "✈️"}
        for _i, req in enumerate(requests, 1):
            icon = type_icons.get(req.get("type"), "📋")
            user_name = (
                req.get("users", {}).get("name", "未知")
                if isinstance(req.get("users"), dict)
                else "未知"
            )
            amount = req.get("amount", 0)
            result += f"{icon} {user_name}: ¥{amount:,.0f}\n"
        return result
