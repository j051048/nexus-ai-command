"""
System-level scheduled tasks — run daily by ScheduledTaskRunner.

These are organization-wide background checks (not user-created tasks).
Each function is idempotent and safe to run multiple times per day.
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

CN_TZ = timezone(timedelta(hours=8))


async def run_all_system_tasks():
    """Entry point called by ScheduledTaskRunner once per day at ~09:00 CN."""
    logger.info("[SystemTasks] Starting daily system tasks")
    for task_fn in [check_expiring_contracts, check_inactive_customers, check_data_consistency]:
        try:
            await task_fn()
        except Exception as e:
            logger.error("[SystemTasks] %s failed: %s", task_fn.__name__, e, exc_info=True)
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
            today_start = datetime.now(CN_TZ).replace(hour=0, minute=0, second=0).isoformat()
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

            days_left = (datetime.fromisoformat(contract["end_date"]).date() - today).days
            urgency = "紧急" if days_left <= 7 else "提醒"

            await supabase.table("notifications").insert({
                "user_id": notify_user_id,
                "title": f"[{urgency}] 合同即将到期",
                "body": f"合同「{contract['title']}」将于 {contract['end_date']} 到期（剩余 {days_left} 天），请及时跟进续约。",
                "type": "warning",
                "action_url": f"/contracts/{contract['id']}",
                "organization_id": contract.get("organization_id"),
            }).execute()

            logger.debug("[SystemTasks] Sent contract expiry notification for %s", contract["id"])
        except Exception as e:
            logger.warning("[SystemTasks] Failed to notify for contract %s: %s", contract.get("id"), e)


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

            last_activity = activity_res.data[0]["created_at"] if activity_res.data else None

            # Skip if recent activity exists
            if last_activity and last_activity > cutoff:
                continue

            days_inactive = 60
            if last_activity:
                last_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                days_inactive = (datetime.now(timezone.utc) - last_dt).days

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

            await supabase.table("notifications").insert({
                "user_id": customer["assigned_to"],
                "title": "客户跟进提醒",
                "body": f"客户「{customer['name']}」已超过 {days_inactive} 天无跟进记录，建议尽快联系维护关系。",
                "type": "info",
                "action_url": f"/crm/customers/{customer['id']}",
                "organization_id": customer.get("organization_id"),
            }).execute()

            notified += 1
        except Exception as e:
            logger.warning("[SystemTasks] Failed to check customer %s: %s", customer.get("id"), e)

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
                alerts.append({
                    "type": "customer_no_contract",
                    "message": f"{len(missing)} 个已成交客户没有活跃合同",
                    "items": [{"id": c["id"], "name": c["name"]} for c in missing[:10]],
                })
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
            alerts.append({
                "type": "contract_past_due",
                "message": f"{len(stale.data)} 个合同已过期但状态仍为活跃",
                "items": [{"id": c["id"], "title": c["title"]} for c in stale.data[:10]],
            })
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

        for alert in alerts:
            for admin in admins:
                await supabase.table("notifications").insert({
                    "user_id": admin["id"],
                    "title": "数据一致性预警",
                    "body": alert["message"],
                    "type": "warning",
                    "action_url": "/dashboard",
                    "organization_id": admin.get("organization_id"),
                }).execute()

        logger.info("[SystemTasks] Sent %d consistency alerts to %d admins", len(alerts), len(admins))
    except Exception as e:
        logger.warning("[SystemTasks] Failed to notify admins: %s", e)
