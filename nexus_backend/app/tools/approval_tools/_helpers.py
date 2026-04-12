import logging

from ._constants import _LEVEL_NAMES, _LEVEL_ROLE_MAP

logger = logging.getLogger(__name__)


async def _notify_next_approver(
    *,
    client,
    approval_level: str,
    requester_id: str,
    requester_name: str,
    approval_type: str,
    amount: float,
    req_id: str,
    org_id: str | None = None,
):
    """
    Notify the correct approver(s) for the current step.
    Strategy:
    1. Try direct manager (manager_id) for manager-level
    2. Fall back to role-based lookup within the same org
    3. Always fall back to founder if nobody found
    """
    from app.services.approval_chain import approval_chain_service

    notified = False
    type_names = {
        "travel": "出差",
        "leave": "请假",
        "expense": "报销",
        "purchase": "采购",
    }
    type_label = type_names.get(approval_type, approval_type)
    level_label = _LEVEL_NAMES.get(approval_level, approval_level)
    content = (
        f"{requester_name} 提交了一笔{type_label}申请（¥{amount:,.0f}），"
        f"需要您（{level_label}）审批。\n单号：{req_id[:8]}..."
    )

    try:
        # Strategy 1: Direct manager for manager-level
        if approval_level == "manager":
            manager = await approval_chain_service.get_direct_manager(
                requester_id, db=client
            )
            if manager:
                await (
                    client.table("notifications")
                    .insert(
                        {
                            "user_id": manager["id"],
                            "title": f"📋 待审批: {requester_name}的{type_label}申请",
                            "content": content,
                            "type": "warning",
                            "action_url": "/approval",
                        }
                    )
                    .execute()
                )
                notified = True

        # Strategy 2: Role-based lookup
        if not notified:
            roles = _LEVEL_ROLE_MAP.get(approval_level, ["founder"])
            query = client.table("users").select("id, name").in_("role", roles)
            if org_id:
                query = query.eq("organization_id", org_id)
            approvers_res = await query.neq("id", requester_id).limit(5).execute()

            for approver in approvers_res.data or []:
                await (
                    client.table("notifications")
                    .insert(
                        {
                            "user_id": approver["id"],
                            "title": f"📋 待审批: {requester_name}的{type_label}申请",
                            "content": content,
                            "type": "warning",
                            "action_url": "/approval",
                        }
                    )
                    .execute()
                )
                notified = True

        # Strategy 3: Ultimate fallback to any founder
        if not notified:
            founders_res = (
                await client.table("users")
                .select("id")
                .eq("role", "founder")
                .limit(3)
                .execute()
            )
            for f in founders_res.data or []:
                await (
                    client.table("notifications")
                    .insert(
                        {
                            "user_id": f["id"],
                            "title": f"📋 待审批: {requester_name}的{type_label}申请",
                            "content": content,
                            "type": "warning",
                            "action_url": "/approval",
                        }
                    )
                    .execute()
                )

    except Exception as e:
        logger.warning(f"Failed to notify approver for {req_id}: {e}")
