"""
System-level scheduled tasks — run daily by ScheduledTaskRunner.

These are organization-wide background checks (not user-created tasks).
Each function is idempotent and safe to run multiple times per day.
"""

import logging
from datetime import UTC, datetime, timedelta, timezone

from app.services.notification_service import (
    Notification,
    NotificationChannel,
    NotificationPriority,
    notification_service,
)

logger = logging.getLogger(__name__)

CN_TZ = timezone(timedelta(hours=8))


async def _send_system_notification(
    user_id: str,
    title: str,
    content: str,
    *,
    type: str = "info",
    action_url: str | None = None,
    org_id: str | None = None,
) -> None:
    """Send a system notification via NotificationService (unified path)."""
    priority = (
        NotificationPriority.HIGH if type == "warning" else NotificationPriority.NORMAL
    )
    metadata: dict = {}
    if action_url:
        metadata["action_url"] = action_url
    if org_id:
        metadata["organization_id"] = org_id
    await notification_service.send(
        Notification(
            title=title,
            content=content,
            target_user_id=user_id,
            channel=NotificationChannel.IN_APP,
            priority=priority,
            metadata=metadata,
        )
    )


async def run_all_system_tasks():
    """Entry point called by ScheduledTaskRunner once per day at ~09:00 CN."""
    logger.info("[SystemTasks] Starting daily system tasks")
    for task_fn in [
        check_expiring_contracts,
        check_inactive_customers,
        check_data_consistency,
        check_pending_approvals,
        promote_memories,
    ]:
        try:
            await task_fn()
        except Exception as e:
            logger.error(
                "[SystemTasks] %s failed: %s", task_fn.__name__, e, exc_info=True
            )
    logger.info("[SystemTasks] Daily system tasks completed")


# ─── #19 Contract Renewal Reminder ──────────────────────────────────


async def check_expiring_contracts():
    """Find active contracts expiring within 30 days, notify the responsible person."""
    from app.core.database import supabase

    if not supabase:
        return

    today = datetime.now(CN_TZ).date()
    deadline = today + timedelta(days=30)

    # Query active contracts expiring within 30 days
    result = await (
        supabase.table("contracts")
        .select("id, title, end_date, customer_id, organization_id")
        .eq("status", "active")
        .gte("end_date", today.isoformat())
        .lte("end_date", deadline.isoformat())
        .execute()
    )

    contracts = result.data or []
    if not contracts:
        return

    logger.info("[SystemTasks] Found %d expiring contracts", len(contracts))

    for contract in contracts:
        try:
            # Find responsible person via customer.assigned_to
            notify_user_id = None
            if contract.get("customer_id"):
                cust_res = await (
                    supabase.table("customers")
                    .select("assigned_to")
                    .eq("id", contract["customer_id"])
                    .maybe_single()
                    .execute()
                )
                if cust_res.data:
                    notify_user_id = cust_res.data.get("assigned_to")

            if not notify_user_id:
                continue

            # Dedup: check if we already sent a notification today for this contract
            today_start = (
                datetime.now(CN_TZ).replace(hour=0, minute=0, second=0).isoformat()
            )
            existing = await (
                supabase.table("notifications")
                .select("id")
                .eq("user_id", notify_user_id)
                .eq("action_url", f"/contracts/{contract['id']}")
                .gte("created_at", today_start)
                .limit(1)
                .execute()
            )
            if existing.data:
                continue

            days_left = (
                datetime.fromisoformat(contract["end_date"]).date() - today
            ).days
            urgency = "紧急" if days_left <= 7 else "提醒"

            await _send_system_notification(
                user_id=notify_user_id,
                title=f"[{urgency}] 合同即将到期",
                content=f"合同「{contract['title']}」将于 {contract['end_date']} 到期（剩余 {days_left} 天），请及时跟进续约。",
                type="warning",
                action_url=f"/contracts/{contract['id']}",
                org_id=contract.get("organization_id"),
            )

            logger.debug(
                "[SystemTasks] Sent contract expiry notification for %s", contract["id"]
            )
        except Exception as e:
            logger.warning(
                "[SystemTasks] Failed to notify for contract %s: %s",
                contract.get("id"),
                e,
            )


# ─── #15 CRM Relationship Coach ──────────────────────────────────


async def check_inactive_customers():
    """Find customers with no activity in 60+ days, remind the assigned salesperson."""
    from app.core.database import supabase

    if not supabase:
        return

    cutoff = (datetime.now(CN_TZ) - timedelta(days=60)).isoformat()

    # Get all active customers with an assigned salesperson
    cust_result = await (
        supabase.table("customers")
        .select("id, name, assigned_to, organization_id")
        .neq("stage", "churned")
        .not_.is_("assigned_to", "null")
        .execute()
    )

    customers = cust_result.data or []
    if not customers:
        return

    notified = 0
    for customer in customers:
        try:
            # Check latest activity
            activity_res = await (
                supabase.table("customer_activities")
                .select("created_at")
                .eq("customer_id", customer["id"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            last_activity = (
                activity_res.data[0]["created_at"] if activity_res.data else None
            )

            # Skip if recent activity exists
            if last_activity and last_activity > cutoff:
                continue

            days_inactive = 60
            if last_activity:
                last_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                days_inactive = (datetime.now(UTC) - last_dt).days

            # Dedup: one notification per customer per week
            week_ago = (datetime.now(CN_TZ) - timedelta(days=7)).isoformat()
            existing = await (
                supabase.table("notifications")
                .select("id")
                .eq("user_id", customer["assigned_to"])
                .eq("action_url", f"/crm/customers/{customer['id']}")
                .gte("created_at", week_ago)
                .limit(1)
                .execute()
            )
            if existing.data:
                continue

            await _send_system_notification(
                user_id=customer["assigned_to"],
                title="客户跟进提醒",
                content=f"客户「{customer['name']}」已超过 {days_inactive} 天无跟进记录，建议尽快联系维护关系。",
                type="info",
                action_url=f"/crm/customers/{customer['id']}",
                org_id=customer.get("organization_id"),
            )

            notified += 1
        except Exception as e:
            logger.warning(
                "[SystemTasks] Failed to check customer %s: %s", customer.get("id"), e
            )

    if notified:
        logger.info("[SystemTasks] Sent %d inactive customer reminders", notified)


# ─── #7 Cross-domain Data Consistency Check ──────────────────────────


async def check_data_consistency():
    """Check for data inconsistencies across CRM and contracts, alert admins."""
    from app.core.database import supabase

    if not supabase:
        return

    alerts = []

    # Rule 1: Customers with stage='customer' but no active contract
    try:
        won_customers = await (
            supabase.table("customers")
            .select("id, name, organization_id")
            .eq("stage", "customer")
            .execute()
        )
        if won_customers.data:
            customer_ids = [c["id"] for c in won_customers.data]
            active_contracts = await (
                supabase.table("contracts")
                .select("customer_id")
                .eq("status", "active")
                .in_("customer_id", customer_ids)
                .execute()
            )
            contracted_ids = {c["customer_id"] for c in (active_contracts.data or [])}
            missing = [c for c in won_customers.data if c["id"] not in contracted_ids]
            if missing:
                alerts.append(
                    {
                        "type": "customer_no_contract",
                        "message": f"{len(missing)} 个已成交客户没有活跃合同",
                        "items": [
                            {"id": c["id"], "name": c["name"]} for c in missing[:10]
                        ],
                    }
                )
    except Exception as e:
        logger.warning("[SystemTasks] Consistency check rule 1 failed: %s", e)

    # Rule 2: Active contracts past end_date (should be expired)
    try:
        today = datetime.now(CN_TZ).date().isoformat()
        stale = await (
            supabase.table("contracts")
            .select("id, title, end_date, organization_id")
            .eq("status", "active")
            .lt("end_date", today)
            .execute()
        )
        if stale.data:
            alerts.append(
                {
                    "type": "contract_past_due",
                    "message": f"{len(stale.data)} 个合同已过期但状态仍为活跃",
                    "items": [
                        {"id": c["id"], "title": c["title"]} for c in stale.data[:10]
                    ],
                }
            )
    except Exception as e:
        logger.warning("[SystemTasks] Consistency check rule 2 failed: %s", e)

    if not alerts:
        return

    # Notify admins
    try:
        # Get all org admins
        admin_res = await (
            supabase.table("users")
            .select("id, organization_id")
            .in_("role", ["boss", "founder"])
            .execute()
        )
        admins = admin_res.data or []

        week_ago = (datetime.now(CN_TZ) - timedelta(days=7)).isoformat()

        for alert in alerts:
            for admin in admins:
                # 限制此类预警最多7天发送一次
                try:
                    existing = await (
                        supabase.table("notifications")
                        .select("id")
                        .eq("user_id", admin["id"])
                        .eq("title", "数据一致性预警")
                        .gte("created_at", week_ago)
                        .limit(1)
                        .execute()
                    )
                    if existing.data:
                        continue
                except Exception:
                    pass

                await _send_system_notification(
                    user_id=admin["id"],
                    title="数据一致性预警",
                    content=alert["message"],
                    type="warning",
                    action_url="/dashboard",
                    org_id=admin.get("organization_id"),
                )

        logger.info(
            "[SystemTasks] Sent %d consistency alerts to %d admins",
            len(alerts),
            len(admins),
        )
    except Exception as e:
        logger.warning("[SystemTasks] Failed to notify admins: %s", e)


# ─── Pending Approval Timeout Reminder ───────────────────────────


async def check_pending_approvals():
    """Find approval requests pending for too long, remind the approver.

    Rules:
    - pending > 4 hours during work hours (09:00-18:00 CN) → notify
    - pending > 24 hours → urgent notify
    - Dedup: one notification per approval per day
    """
    from app.core.database import supabase

    if not supabase:
        return

    now = datetime.now(CN_TZ)

    # Only check during work hours (09:00-18:00)
    if now.hour < 9 or now.hour >= 18:
        return

    # Find pending approvals older than 4 hours
    cutoff_4h = (now - timedelta(hours=4)).isoformat()
    cutoff_24h = (now - timedelta(hours=24)).isoformat()

    result = await (
        supabase.table("approval_requests")
        .select(
            "id, type, description, amount, submitted_by, submitted_at, organization_id"
        )
        .eq("status", "pending")
        .lte("submitted_at", cutoff_4h)
        .execute()
    )

    approvals = result.data or []
    if not approvals:
        return

    logger.info(
        "[SystemTasks] Found %d pending approvals older than 4h", len(approvals)
    )

    # Get org admins (boss/founder) as approvers
    org_ids = {a["organization_id"] for a in approvals if a.get("organization_id")}
    org_admins: dict[str, list[str]] = {}  # org_id -> [user_ids]

    for org_id in org_ids:
        try:
            admin_res = await (
                supabase.table("users")
                .select("id")
                .eq("organization_id", org_id)
                .in_("role", ["boss", "founder"])
                .execute()
            )
            org_admins[org_id] = [a["id"] for a in (admin_res.data or [])]
        except Exception:
            pass

    notified = 0
    for approval in approvals:
        org_id = approval.get("organization_id")
        if not org_id or org_id not in org_admins:
            continue

        admins = org_admins[org_id]
        if not admins:
            continue

        # Determine urgency
        submitted_at = approval.get("submitted_at", "")
        is_urgent = submitted_at and submitted_at <= cutoff_24h
        urgency = "紧急" if is_urgent else "提醒"

        # Calculate hours pending
        try:
            sub_dt = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
            hours_pending = int(
                (datetime.now(CN_TZ).astimezone(sub_dt.tzinfo) - sub_dt).total_seconds()
                / 3600
            )
        except Exception:
            hours_pending = 4

        desc = (approval.get("description") or approval.get("type") or "未知")[:50]
        amount_str = (
            f"，金额 ¥{approval['amount']:,.0f}" if approval.get("amount") else ""
        )

        for admin_id in admins:
            try:
                # Dedup: one notification per approval per day
                today_start = now.replace(hour=0, minute=0, second=0).isoformat()
                existing = await (
                    supabase.table("notifications")
                    .select("id")
                    .eq("user_id", admin_id)
                    .eq("action_url", f"/approvals/{approval['id']}")
                    .gte("created_at", today_start)
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    continue

                await _send_system_notification(
                    user_id=admin_id,
                    title=f"[{urgency}] 审批待处理",
                    content=f"「{desc}」{amount_str} 已等待 {hours_pending} 小时未审批，请及时处理。",
                    type="warning" if is_urgent else "info",
                    action_url=f"/approvals/{approval['id']}",
                    org_id=org_id,
                )

                notified += 1
            except Exception as e:
                logger.warning(
                    "[SystemTasks] Failed to notify for approval %s: %s",
                    approval.get("id"),
                    e,
                )

    if notified:
        logger.info("[SystemTasks] Sent %d pending approval reminders", notified)


# ─── Memory Auto-Promotion ──────────────────────────────────────


async def promote_memories():
    """Auto-promote high-recurrence memories to business_rule category."""
    from app.services.conversation_memory.cleanup import (
        promote_high_recurrence_memories,
    )

    result = await promote_high_recurrence_memories()
    if result.get("promoted"):
        logger.info("[SystemTasks] Memory promotion: %s", result)
