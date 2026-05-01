"""
P0-1: Event Sensors — Proactive anomaly detection tasks.

Borrowed from OpenFang's "Hands" philosophy: the AI doesn't just respond to
prompts — it continuously monitors business data and proactively alerts users
when something needs attention.

Five sensors:
1. Sales metric anomaly (daily revenue drop >30%)
2. Follow-up timeout (opportunity customers 7 days without follow-up)
3. Contract expiry ladder (15/7/3 day warnings)
4. Approval backlog (>3 pending + oldest >4 hours)
5. Target progress gap (monthly target <50% past mid-month)
"""

import logging
from datetime import UTC, datetime, timedelta

from app.core.celery_app import NexusTask, celery_app
from app.tasks.scheduler import _run_async, _with_redis_lock

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configurable Thresholds (per-tenant via SystemConfigService)
# ---------------------------------------------------------------------------

_DEFAULT_THRESHOLDS = {
    "sales_anomaly_drop_ratio": 0.7,
    "sales_anomaly_window_days": 8,
    "followup_timeout_days": 7,
    "followup_limit": 30,
    "contract_expiry_ladder": [3, 7, 15],
    "approval_backlog_hours": 4,
    "approval_backlog_min_count": 3,
    "approval_backlog_amount_threshold": 1000,
    "target_progress_ratio": 0.6,
}


async def _get_all_org_ids() -> list[str]:
    """P0-3 Security Fix: 获取所有活跃组织 ID，用于按租户遍历。"""
    from app.core.database import supabase

    if not supabase:
        return []
    try:
        result = await supabase.table("organizations").select("id").execute()
        return [r["id"] for r in (result.data or []) if r.get("id")]
    except Exception as e:
        logger.error("Failed to fetch organization list: %s", e)
        return []


def _get_org_client(org_id: str):
    """P0-3 Security Fix: 获取按组织隔离的数据库客户端。"""
    from app.core.database import supabase

    if not supabase:
        return None
    return supabase.get_org_filtered_client(org_id)


async def _get_thresholds(org_id: str | None = None) -> dict:
    """Read tenant-level sensor thresholds, fallback to defaults."""
    if not org_id:
        return dict(_DEFAULT_THRESHOLDS)
    try:
        from app.services.system_config_service import system_config_service

        config = await system_config_service.get_config(
            config_type="event_sensor_thresholds", org_id=org_id
        )
        if config and config.get("value"):
            merged = dict(_DEFAULT_THRESHOLDS)
            merged.update(config["value"])
            return merged
    except Exception as e:
        logger.error("tenant sensor thresholds query failed: %s", e)


async def _record_action(
    action_type: str,
    target_id: str | None,
    target_name: str,
    user_id: str,
    expected_outcome: str,
    org_id: str | None = None,
) -> None:
    """Record an AI action for outcome tracking (P1-2)."""
    try:
        from app.core.database import supabase

        if not supabase or not org_id:
            return
        # P0-3 Security Fix: 使用 org-scoped client
        db = supabase.get_org_filtered_client(org_id)
        await (
            db.table("ai_action_outcomes")
            .insert(
                {
                    "action_type": action_type,
                    "target_id": target_id,
                    "target_name": target_name,
                    "user_id": user_id,
                    "organization_id": org_id,
                    "expected_outcome": expected_outcome,
                }
            )
            .execute()
        )
    except Exception as e:
        logger.error(f"Failed to record action outcome: {e}")


# ---------------------------------------------------------------------------
# Sensor 1: Sales Metric Anomaly Detection
# ---------------------------------------------------------------------------


@celery_app.task(base=NexusTask)
@_with_redis_lock("sensor_sales_anomaly", lock_ttl=600)
def sensor_sales_anomaly():
    """Detect sudden drops in key sales metrics (revenue, leads, conversions).

    Runs daily at 10:30. Compares yesterday vs previous 7-day average.
    If any metric drops >30%, generates AI analysis and notifies boss/managers.

    P0-3 Security Fix: 按组织遍历，每个 org 使用隔离的 client。
    """

    async def _run():
        org_ids = await _get_all_org_ids()
        if not org_ids:
            return "skipped: no orgs or no db"

        total_notified = 0
        for org_id in org_ids:
            try:
                n = await _run_sales_anomaly_for_org(org_id)
                total_notified += n
            except Exception as e:
                logger.error("sensor_sales_anomaly failed for org %s: %s", org_id, e)
        return f"Sales anomaly check done for {len(org_ids)} orgs, {total_notified} alerts sent"

    return _run_async(_run())


async def _run_sales_anomaly_for_org(org_id: str) -> int:
    """单个组织的销售异常检测。"""
    from app.services.notification_service import (
        NotificationPriority,
        send_notification,
    )

    db = _get_org_client(org_id)
    if not db:
        return 0

    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    thresholds = await _get_thresholds(org_id)
    week_ago = today - timedelta(days=thresholds["sales_anomaly_window_days"])

    # Get yesterday's totals
    try:
        yesterday_res = (
            await db.table("sales_metrics")
            .select("revenue, leads_count, conversions")
            .eq("date", yesterday.isoformat())
            .execute()
        )
    except Exception:
        try:
            yesterday_res = (
                await db.table("sales_metrics")
                .select("metric_type, value")
                .gte("created_at", yesterday.isoformat())
                .lt("created_at", today.isoformat())
                .execute()
            )
        except Exception as e:
            logger.error("sales_metrics query failed for org %s: %s", org_id, e)
            return 0

    yesterday_data = yesterday_res.data or []
    if not yesterday_data:
        return 0

    y_revenue = sum(float(r.get("revenue", 0) or 0) for r in yesterday_data)
    y_leads = sum(int(r.get("leads_count", 0) or 0) for r in yesterday_data)

    try:
        week_res = (
            await db.table("sales_metrics")
            .select("revenue, leads_count")
            .gte("date", week_ago.isoformat())
            .lt("date", yesterday.isoformat())
            .execute()
        )
        week_data = week_res.data or []
    except Exception as e:
        logger.error("historical sales_metrics query failed for org %s: %s", org_id, e)
        week_data = []

    if not week_data:
        return 0

    days_count = max(len(set(r.get("date", "") for r in week_data)), 1)
    avg_revenue = sum(float(r.get("revenue", 0) or 0) for r in week_data) / days_count
    avg_leads = sum(int(r.get("leads_count", 0) or 0) for r in week_data) / days_count

    drop_ratio = thresholds["sales_anomaly_drop_ratio"]
    anomalies = []
    if avg_revenue > 0 and y_revenue < avg_revenue * drop_ratio:
        drop_pct = round((1 - y_revenue / avg_revenue) * 100, 1)
        anomalies.append(
            f"销售额环比下跌 {drop_pct}%（昨日 ¥{y_revenue:,.0f} vs 7日均值 ¥{avg_revenue:,.0f}）"
        )
    if avg_leads > 0 and y_leads < avg_leads * drop_ratio:
        drop_pct = round((1 - y_leads / avg_leads) * 100, 1)
        anomalies.append(
            f"新增线索骤降 {drop_pct}%（昨日 {y_leads} 条 vs 7日均值 {avg_leads:.0f} 条）"
        )

    if not anomalies:
        return 0

    analysis = ""
    try:
        from app.services.ai_service import AIService

        context = "\n".join(anomalies)
        analysis = await AIService.call_llm(
            f"以下是销售指标异常:\n{context}",
            "你是企业经营分析师。简要分析可能原因并给出2-3条改善建议（每条一句话）。",
        )
    except Exception as e:
        logger.warning(f"AI analysis failed: {e}")
        analysis = "\n".join(anomalies)

    alert_content = (
        f"⚠️ 销售指标异常预警\n\n{chr(10).join(anomalies)}\n\n{analysis[:300]}"
    )

    try:
        mgr_res = (
            await db.table("users")
            .select("id")
            .in_("role", ["founder", "boss", "manager"])
            .execute()
        )
        notified = 0
        for u in mgr_res.data or []:
            try:
                await send_notification(
                    title="📉 销售指标异常预警",
                    content=alert_content[:500],
                    target_user_id=u["id"],
                    priority=NotificationPriority.HIGH,
                    metadata={
                        "action_url": "/dashboard",
                        "source": "sensor_sales_anomaly",
                        "proactive_prompt": f"检测到销售额异常下跌。{'; '.join(anomalies)}。需要我分析可能的原因并生成恢复建议吗？",
                    },
                )
                notified += 1
            except Exception as e:
                logger.error("anomaly notification send failed for user: %s", e)
        return notified
    except Exception as e:
        logger.error("Failed to send anomaly alerts for org %s: %s", org_id, e)
        return 0


# ---------------------------------------------------------------------------
# Sensor 2: Follow-up Timeout Detection
# ---------------------------------------------------------------------------


@celery_app.task(base=NexusTask)
@_with_redis_lock("sensor_followup_timeout", lock_ttl=600)
def sensor_followup_timeout():
    """Detect opportunity-stage customers with no follow-up in 7+ days.

    Runs every 4 hours. Notifies the assigned salesperson with AI-generated
    follow-up suggestions.

    P0-3 Security Fix: 按组织遍历，每个 org 使用隔离的 client。
    """

    async def _run():
        org_ids = await _get_all_org_ids()
        if not org_ids:
            return "skipped: no orgs or no db"

        total_notified = 0
        for org_id in org_ids:
            try:
                n = await _run_followup_timeout_for_org(org_id)
                total_notified += n
            except Exception as e:
                logger.error("sensor_followup_timeout failed for org %s: %s", org_id, e)
        return f"Follow-up timeout check done for {len(org_ids)} orgs, {total_notified} reminders sent"

    return _run_async(_run())


async def _run_followup_timeout_for_org(org_id: str) -> int:
    """单个组织的跟进超时检测。"""
    from app.services.notification_service import send_notification

    db = _get_org_client(org_id)
    if not db:
        return 0

    thresholds = await _get_thresholds(org_id)
    timeout_days = thresholds["followup_timeout_days"]
    cutoff = (datetime.now(UTC) - timedelta(days=timeout_days)).isoformat()

    try:
        result = (
            await db.table("customers")
            .select("id, name, stage, user_id, updated_at")
            .in_("stage", ["opportunity", "prospect", "qualified"])
            .lt("updated_at", cutoff)
            .limit(thresholds["followup_limit"])
            .execute()
        )
    except Exception as e:
        logger.error("customers query failed for org %s: %s", org_id, e)
        return 0

    stale = result.data or []
    if not stale:
        return 0

    notified = 0
    for customer in stale:
        if not customer.get("user_id"):
            continue
        try:
            days_since = (
                datetime.now(UTC)
                - datetime.fromisoformat(customer["updated_at"].replace("Z", "+00:00"))
            ).days

            suggestion = ""
            try:
                from app.services.ai_service import AIService

                suggestion = await AIService.call_llm(
                    f"客户: {customer['name']}, 阶段: {customer['stage']}, 已 {days_since} 天未跟进",
                    "你是销售顾问。用1-2句话给出有针对性的跟进建议。",
                )
            except Exception:
                suggestion = f"该客户已 {days_since} 天未跟进，建议尽快联系。"

            await send_notification(
                title=f"⏰ 客户跟进提醒: {customer['name']}",
                content=f"客户处于 {customer['stage']} 阶段，已 {days_since} 天未跟进。\n\n💡 建议: {suggestion[:200]}",
                target_user_id=customer["user_id"],
                metadata={
                    "action_url": f"/customers/{customer['id']}",
                    "source": "sensor_followup_timeout",
                    "proactive_prompt": f"客户「{customer['name']}」已超过{days_since}天未跟进，处于{customer['stage']}阶段。需要我帮你生成跟进话术吗？",
                },
            )
            await _record_action(
                action_type="followup_reminder",
                target_id=customer["id"],
                target_name=customer["name"],
                user_id=customer["user_id"],
                expected_outcome="客户记录在48小时内被更新",
                org_id=org_id,
            )
            notified += 1
        except Exception as e:
            logger.error(
                "Follow-up reminder failed for customer %s in org %s: %s",
                customer.get("id"),
                org_id,
                e,
            )

    return notified


# ---------------------------------------------------------------------------
# Sensor 3: Contract Expiry Ladder Warning
# ---------------------------------------------------------------------------


@celery_app.task(base=NexusTask)
@_with_redis_lock("sensor_contract_expiry_ladder", lock_ttl=600)
def sensor_contract_expiry_ladder():
    """Enhanced contract expiry with 15/7/3 day ladder warnings.

    Runs daily at 9:00. Generates renewal suggestions for critical contracts.
    Escalates: 15-day = normal, 7-day = high, 3-day = urgent.

    P0-3 Security Fix: 按组织遍历，每个 org 使用隔离的 client。
    """

    async def _run():
        org_ids = await _get_all_org_ids()
        if not org_ids:
            return "skipped: no orgs or no db"

        total_notified = 0
        for org_id in org_ids:
            try:
                n = await _run_contract_expiry_for_org(org_id)
                total_notified += n
            except Exception as e:
                logger.error("sensor_contract_expiry failed for org %s: %s", org_id, e)
        return f"Contract expiry check done for {len(org_ids)} orgs, {total_notified} alerts sent"

    return _run_async(_run())


async def _run_contract_expiry_for_org(org_id: str) -> int:
    """单个组织的合同到期阶梯预警。"""
    from app.services.notification_service import (
        NotificationPriority,
        send_notification,
    )

    db = _get_org_client(org_id)
    if not db:
        return 0

    today = datetime.now().date()
    thresholds = await _get_thresholds(org_id)
    ladder_days = thresholds["contract_expiry_ladder"]
    ladders = [
        {
            "days": ladder_days[0],
            "label": "🔴 紧急",
            "priority": NotificationPriority.URGENT,
        },
        {
            "days": ladder_days[1],
            "label": "🟡 重要",
            "priority": NotificationPriority.HIGH,
        },
        {
            "days": ladder_days[2],
            "label": "🟢 提醒",
            "priority": NotificationPriority.NORMAL,
        },
    ]

    notified = 0
    for ladder in ladders:
        target_date = (today + timedelta(days=ladder["days"])).isoformat()
        try:
            result = (
                await db.table("contracts")
                .select("id, title, end_date, user_id, customer_name, amount")
                .eq("end_date", target_date)
                .eq("status", "active")
                .execute()
            )
        except Exception as e:
            logger.error(
                "contract expiry query failed for %d-day ladder in org %s: %s",
                ladder["days"],
                org_id,
                e,
            )
            continue

        for contract in result.data or []:
            if not contract.get("user_id"):
                continue
            try:
                amount_str = (
                    f"，金额 ¥{float(contract.get('amount', 0)):,.0f}"
                    if contract.get("amount")
                    else ""
                )
                customer = contract.get("customer_name", "")

                suggestion = ""
                if ladder["days"] <= 7:
                    try:
                        from app.services.ai_service import AIService

                        suggestion = await AIService.call_llm(
                            f"合同: {contract.get('title', '')}, 客户: {customer}, 金额: {amount_str}, {ladder['days']}天后到期",
                            "你是合同管理顾问。用2句话给出续签策略建议。",
                        )
                        suggestion = f"\n\n💡 续签建议: {suggestion[:200]}"
                    except Exception as e:
                        logger.error(
                            "contract renewal suggestion generation failed: %s", e
                        )

                await send_notification(
                    title=f"{ladder['label']} 合同到期: {contract.get('title', '未命名')}",
                    content=f"合同将在 {ladder['days']} 天后到期 ({target_date}){amount_str}{suggestion}",
                    target_user_id=contract["user_id"],
                    priority=ladder["priority"],
                    metadata={
                        "action_url": f"/contracts/{contract['id']}",
                        "source": "sensor_contract_expiry_ladder",
                        "proactive_prompt": f"合同「{contract.get('title', '未命名')}」将在{ladder['days']}天内到期{amount_str}。需要我帮你起草续约邮件吗？",
                    },
                )
                await _record_action(
                    action_type="contract_expiry_reminder",
                    target_id=contract["id"],
                    target_name=contract.get("title", "未命名"),
                    user_id=contract["user_id"],
                    expected_outcome=f"合同在到期前被处理（{ladder['days']}天预警）",
                    org_id=org_id,
                )
                notified += 1
            except Exception as e:
                logger.error(
                    "Contract expiry notification failed in org %s: %s", org_id, e
                )

    return notified


# ---------------------------------------------------------------------------
# Sensor 4: Approval Backlog Detection
# ---------------------------------------------------------------------------


@celery_app.task(base=NexusTask)
@_with_redis_lock("sensor_approval_backlog", lock_ttl=600)
def sensor_approval_backlog():
    """Detect approval backlogs: >3 pending items AND oldest pending >4 hours.

    Runs every 30 minutes. Notifies the approver and optionally suggests
    auto-approval for low-amount items.

    P0-3 Security Fix: 按组织遍历，每个 org 使用隔离的 client。
    """

    async def _run():
        org_ids = await _get_all_org_ids()
        if not org_ids:
            return "skipped: no orgs or no db"

        total_notified = 0
        for org_id in org_ids:
            try:
                n = await _run_approval_backlog_for_org(org_id)
                total_notified += n
            except Exception as e:
                logger.error("sensor_approval_backlog failed for org %s: %s", org_id, e)
        return f"Approval backlog check done for {len(org_ids)} orgs, {total_notified} alerts sent"

    return _run_async(_run())


async def _run_approval_backlog_for_org(org_id: str) -> int:
    """单个组织的审批积压检测。"""
    from app.services.notification_service import (
        NotificationPriority,
        send_notification,
    )

    db = _get_org_client(org_id)
    if not db:
        return 0

    thresholds = await _get_thresholds(org_id)
    backlog_hours = thresholds["approval_backlog_hours"]
    cutoff_time = (datetime.now(UTC) - timedelta(hours=backlog_hours)).isoformat()

    try:
        result = (
            await db.table("approval_requests")
            .select(
                "id, type, amount, description, submitted_by, created_at, assigned_to"
            )
            .eq("status", "pending")
            .order("created_at", desc=False)
            .execute()
        )
    except Exception as e:
        logger.error("approval_requests query failed for org %s: %s", org_id, e)
        return 0

    pending = result.data or []
    if len(pending) < thresholds["approval_backlog_min_count"]:
        return 0

    oldest = pending[0]
    oldest_time = oldest.get("created_at", "")
    if oldest_time > cutoff_time:
        return 0

    approver_groups: dict[str, list] = {}
    for item in pending:
        approver = item.get("assigned_to") or "unassigned"
        approver_groups.setdefault(approver, []).append(item)

    notified = 0
    for approver_id, items in approver_groups.items():
        if approver_id == "unassigned" or len(items) < 2:
            continue

        low_amount = [
            i
            for i in items
            if float(i.get("amount", 0) or 0)
            < thresholds["approval_backlog_amount_threshold"]
        ]
        high_amount = [
            i
            for i in items
            if float(i.get("amount", 0) or 0)
            >= thresholds["approval_backlog_amount_threshold"]
        ]

        summary_parts = [f"您有 {len(items)} 条待审批事项积压"]
        if low_amount:
            summary_parts.append(
                f"其中 {len(low_amount)} 条金额<¥1000，建议批量快速处理"
            )
        if high_amount:
            total_high = sum(float(i.get("amount", 0) or 0) for i in high_amount)
            summary_parts.append(
                f"{len(high_amount)} 条高金额（合计 ¥{total_high:,.0f}）需要重点审核"
            )

        try:
            await send_notification(
                title=f"📋 审批积压提醒 ({len(items)}条待处理)",
                content="\n".join(summary_parts),
                target_user_id=approver_id,
                priority=NotificationPriority.HIGH,
                metadata={
                    "action_url": "/approvals",
                    "source": "sensor_approval_backlog",
                    "proactive_prompt": f"你有 {len(items)} 笔审批待处理。需要我帮你快速审批吗？",
                },
            )
            notified += 1
        except Exception as e:
            logger.error(
                "Approval backlog notification failed for %s in org %s: %s",
                approver_id,
                org_id,
                e,
            )

    return notified


# ---------------------------------------------------------------------------
# Sensor 5: Target Progress Gap Detection
# ---------------------------------------------------------------------------


@celery_app.task(base=NexusTask)
@_with_redis_lock("sensor_target_progress", lock_ttl=600)
def sensor_target_progress():
    """Detect users falling behind on monthly targets.

    Runs daily at 17:00. Past mid-month, if completion <50%,
    generates AI strategy suggestions and notifies the user + their manager.

    P0-3 Security Fix: 按组织遍历，每个 org 使用隔离的 client。
    """

    async def _run():
        org_ids = await _get_all_org_ids()
        if not org_ids:
            return "skipped: no orgs or no db"

        total_notified = 0
        for org_id in org_ids:
            try:
                n = await _run_target_progress_for_org(org_id)
                total_notified += n
            except Exception as e:
                logger.error("sensor_target_progress failed for org %s: %s", org_id, e)
        return f"Target progress check done for {len(org_ids)} orgs, {total_notified} alerts sent"

    return _run_async(_run())


async def _run_target_progress_for_org(org_id: str) -> int:
    """单个组织的目标进度差距检测。"""
    import calendar

    from app.services.notification_service import send_notification

    db = _get_org_client(org_id)
    if not db:
        return 0

    thresholds = await _get_thresholds(org_id)
    today = datetime.now().date()
    day_of_month = today.day
    days_in_month = calendar.monthrange(today.year, today.month)[1]

    if day_of_month < days_in_month // 2:
        return 0

    month_progress = day_of_month / days_in_month
    month_start = today.replace(day=1).isoformat()

    try:
        targets_res = (
            await db.table("sales_targets")
            .select("id, user_id, target_value, current_value, metric_type")
            .gte("period_start", month_start)
            .execute()
        )
    except Exception:
        return 0

    targets = targets_res.data or []
    if not targets:
        return 0

    notified = 0
    for target in targets:
        target_val = float(target.get("target_value", 0) or 0)
        current_val = float(target.get("current_value", 0) or 0)
        if target_val <= 0:
            continue

        completion = current_val / target_val
        expected = month_progress

        if completion >= expected * thresholds["target_progress_ratio"]:
            continue

        user_id = target.get("user_id")
        if not user_id:
            continue

        gap_pct = round((expected - completion) * 100, 1)
        completion_pct = round(completion * 100, 1)

        suggestion = ""
        try:
            from app.services.ai_service import AIService

            suggestion = await AIService.call_llm(
                f"目标完成率 {completion_pct}%，预期应达到 {round(expected * 100, 1)}%，差距 {gap_pct}%",
                "你是绩效教练。用2-3句话给出提升业绩的具体建议。",
            )
        except Exception:
            suggestion = f"当前完成率 {completion_pct}%，距离预期差距 {gap_pct}%。建议加大客户拜访力度。"

        try:
            await send_notification(
                title=f"📊 目标进度预警: 完成率 {completion_pct}%",
                content=f"本月已过 {round(month_progress * 100)}%，但目标完成率仅 {completion_pct}%。\n\n💡 {suggestion[:300]}",
                target_user_id=user_id,
                metadata={
                    "action_url": "/dashboard",
                    "source": "sensor_target_progress",
                    "proactive_prompt": f"本月目标完成率 {completion_pct}%，距离月底还有 {days_in_month - day_of_month} 天。需要我帮你制定冲刺计划吗？",
                },
            )
            notified += 1
        except Exception as e:
            logger.error(
                "Target progress alert failed for user %s in org %s: %s",
                user_id,
                org_id,
                e,
            )

    return notified
