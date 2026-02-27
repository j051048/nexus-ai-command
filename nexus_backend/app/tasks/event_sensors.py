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

from app.core.celery_app import celery_app
from app.tasks.scheduler import _run_async

logger = logging.getLogger(__name__)


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

        if not supabase:
            return
        await (
            supabase.table("ai_action_outcomes")
            .insert({
                "action_type": action_type,
                "target_id": target_id,
                "target_name": target_name,
                "user_id": user_id,
                "org_id": org_id,
                "expected_outcome": expected_outcome,
            })
            .execute()
        )
    except Exception as e:
        logger.debug(f"Failed to record action outcome: {e}")


# ---------------------------------------------------------------------------
# Sensor 1: Sales Metric Anomaly Detection
# ---------------------------------------------------------------------------

@celery_app.task
def sensor_sales_anomaly():
    """Detect sudden drops in key sales metrics (revenue, leads, conversions).

    Runs daily at 10:30. Compares yesterday vs previous 7-day average.
    If any metric drops >30%, generates AI analysis and notifies boss/managers.
    """

    async def _run():
        from app.core.database import supabase
        from app.services.notification_service import NotificationPriority, send_notification

        if not supabase:
            return "skipped: no db"

        today = datetime.now(UTC).date()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=8)

        # Get yesterday's totals
        try:
            yesterday_res = (
                await supabase.table("sales_metrics")
                .select("revenue, leads_count, conversions")
                .eq("date", yesterday.isoformat())
                .execute()
            )
        except Exception:
            # Fallback: use key-value schema
            try:
                yesterday_res = (
                    await supabase.table("sales_metrics")
                    .select("metric_type, value")
                    .gte("created_at", yesterday.isoformat())
                    .lt("created_at", today.isoformat())
                    .execute()
                )
            except Exception as e:
                logger.debug(f"sales_metrics query failed: {e}")
                return "skipped: sales_metrics not available"

        yesterday_data = yesterday_res.data or []
        if not yesterday_data:
            return "no data for yesterday"

        # Calculate yesterday's totals
        y_revenue = sum(float(r.get("revenue", 0) or 0) for r in yesterday_data)
        y_leads = sum(int(r.get("leads_count", 0) or 0) for r in yesterday_data)

        # Get previous 7-day average
        try:
            week_res = (
                await supabase.table("sales_metrics")
                .select("revenue, leads_count")
                .gte("date", week_ago.isoformat())
                .lt("date", yesterday.isoformat())
                .execute()
            )
            week_data = week_res.data or []
        except Exception:
            week_data = []

        if not week_data:
            return "no historical data for comparison"

        days_count = max(len(set(r.get("date", "") for r in week_data)), 1)
        avg_revenue = sum(float(r.get("revenue", 0) or 0) for r in week_data) / days_count
        avg_leads = sum(int(r.get("leads_count", 0) or 0) for r in week_data) / days_count

        # Detect anomalies (>30% drop)
        anomalies = []
        if avg_revenue > 0 and y_revenue < avg_revenue * 0.7:
            drop_pct = round((1 - y_revenue / avg_revenue) * 100, 1)
            anomalies.append(f"销售额环比下跌 {drop_pct}%（昨日 ¥{y_revenue:,.0f} vs 7日均值 ¥{avg_revenue:,.0f}）")

        if avg_leads > 0 and y_leads < avg_leads * 0.7:
            drop_pct = round((1 - y_leads / avg_leads) * 100, 1)
            anomalies.append(f"新增线索骤降 {drop_pct}%（昨日 {y_leads} 条 vs 7日均值 {avg_leads:.0f} 条）")

        if not anomalies:
            return "no anomalies detected"

        # Generate AI analysis
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

        # Notify boss/managers
        alert_content = f"⚠️ 销售指标异常预警\n\n{chr(10).join(anomalies)}\n\n{analysis[:300]}"

        try:
            mgr_res = (
                await supabase.table("users")
                .select("id")
                .in_("role", ["founder", "boss", "manager"])
                .execute()
            )
            notified = 0
            for u in (mgr_res.data or []):
                try:
                    await send_notification(
                        title="📉 销售指标异常预警",
                        content=alert_content[:500],
                        target_user_id=u["id"],
                        priority=NotificationPriority.HIGH,
                    )
                    notified += 1
                except Exception:
                    pass
            return f"Sales anomaly alert sent to {notified} users: {'; '.join(anomalies)}"
        except Exception as e:
            logger.error(f"Failed to send anomaly alerts: {e}")
            return f"anomaly detected but notification failed: {e}"

    return _run_async(_run())


# ---------------------------------------------------------------------------
# Sensor 2: Follow-up Timeout Detection
# ---------------------------------------------------------------------------

@celery_app.task
def sensor_followup_timeout():
    """Detect opportunity-stage customers with no follow-up in 7+ days.

    Runs every 4 hours. Notifies the assigned salesperson with AI-generated
    follow-up suggestions.
    """

    async def _run():
        from app.core.database import supabase
        from app.services.notification_service import send_notification

        if not supabase:
            return "skipped: no db"

        seven_days_ago = (datetime.now(UTC) - timedelta(days=7)).isoformat()

        try:
            result = (
                await supabase.table("customers")
                .select("id, name, stage, user_id, updated_at")
                .in_("stage", ["opportunity", "prospect", "qualified"])
                .lt("updated_at", seven_days_ago)
                .limit(30)
                .execute()
            )
        except Exception as e:
            logger.debug(f"customers query failed: {e}")
            return "skipped: customers table not available"

        stale = result.data or []
        if not stale:
            return "no stale opportunities"

        notified = 0
        for customer in stale:
            if not customer.get("user_id"):
                continue
            try:
                days_since = (datetime.now(UTC) - datetime.fromisoformat(
                    customer["updated_at"].replace("Z", "+00:00")
                )).days

                # Generate follow-up suggestion
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
                )
                # P1-2: Record action for outcome tracking
                await _record_action(
                    action_type="followup_reminder",
                    target_id=customer["id"],
                    target_name=customer["name"],
                    user_id=customer["user_id"],
                    expected_outcome="客户记录在48小时内被更新",
                )
                notified += 1
            except Exception as e:
                logger.error(f"Follow-up reminder failed for customer {customer['id']}: {e}")

        return f"Sent {notified} follow-up reminders for {len(stale)} stale opportunities"

    return _run_async(_run())


# ---------------------------------------------------------------------------
# Sensor 3: Contract Expiry Ladder Warning
# ---------------------------------------------------------------------------

@celery_app.task
def sensor_contract_expiry_ladder():
    """Enhanced contract expiry with 15/7/3 day ladder warnings.

    Runs daily at 9:00. Generates renewal suggestions for critical contracts.
    Escalates: 15-day = normal, 7-day = high, 3-day = urgent.
    """

    async def _run():
        from app.core.database import supabase
        from app.services.notification_service import NotificationPriority, send_notification

        if not supabase:
            return "skipped: no db"

        today = datetime.now().date()

        # Define ladder thresholds
        ladders = [
            {"days": 3, "label": "🔴 紧急", "priority": NotificationPriority.URGENT},
            {"days": 7, "label": "🟡 重要", "priority": NotificationPriority.HIGH},
            {"days": 15, "label": "🟢 提醒", "priority": NotificationPriority.NORMAL},
        ]

        notified = 0
        for ladder in ladders:
            target_date = (today + timedelta(days=ladder["days"])).isoformat()
            try:
                result = (
                    await supabase.table("contracts")
                    .select("id, title, end_date, user_id, customer_name, amount")
                    .eq("end_date", target_date)
                    .eq("status", "active")
                    .execute()
                )
            except Exception:
                continue

            for contract in (result.data or []):
                if not contract.get("user_id"):
                    continue
                try:
                    amount_str = f"，金额 ¥{float(contract.get('amount', 0)):,.0f}" if contract.get("amount") else ""
                    customer = contract.get("customer_name", "")

                    # Generate renewal suggestion for 7-day and 3-day warnings
                    suggestion = ""
                    if ladder["days"] <= 7:
                        try:
                            from app.services.ai_service import AIService

                            suggestion = await AIService.call_llm(
                                f"合同: {contract.get('title', '')}, 客户: {customer}, 金额: {amount_str}, {ladder['days']}天后到期",
                                "你是合同管理顾问。用2句话给出续签策略建议。",
                            )
                            suggestion = f"\n\n💡 续签建议: {suggestion[:200]}"
                        except Exception:
                            pass

                    await send_notification(
                        title=f"{ladder['label']} 合同到期: {contract.get('title', '未命名')}",
                        content=f"合同将在 {ladder['days']} 天后到期 ({target_date}){amount_str}{suggestion}",
                        target_user_id=contract["user_id"],
                        priority=ladder["priority"],
                    )
                    # P1-2: Record action for outcome tracking
                    await _record_action(
                        action_type="contract_expiry_reminder",
                        target_id=contract["id"],
                        target_name=contract.get("title", "未命名"),
                        user_id=contract["user_id"],
                        expected_outcome=f"合同在到期前被处理（{ladder['days']}天预警）",
                    )
                    notified += 1
                except Exception as e:
                    logger.error(f"Contract expiry ladder notification failed: {e}")

        return f"Sent {notified} contract expiry ladder notifications"

    return _run_async(_run())


# ---------------------------------------------------------------------------
# Sensor 4: Approval Backlog Detection
# ---------------------------------------------------------------------------

@celery_app.task
def sensor_approval_backlog():
    """Detect approval backlogs: >3 pending items AND oldest pending >4 hours.

    Runs every 30 minutes. Notifies the approver and optionally suggests
    auto-approval for low-amount items.
    """

    async def _run():
        from app.core.database import supabase
        from app.services.notification_service import NotificationPriority, send_notification

        if not supabase:
            return "skipped: no db"

        four_hours_ago = (datetime.now(UTC) - timedelta(hours=4)).isoformat()

        try:
            result = (
                await supabase.table("approval_requests")
                .select("id, type, amount, description, submitted_by, created_at, assigned_to")
                .eq("status", "pending")
                .order("created_at", desc=False)
                .execute()
            )
        except Exception as e:
            logger.debug(f"approval_requests query failed: {e}")
            return "skipped: approval_requests not available"

        pending = result.data or []
        if len(pending) < 3:
            return f"only {len(pending)} pending approvals, below threshold"

        # Check if oldest is >4 hours
        oldest = pending[0]
        oldest_time = oldest.get("created_at", "")
        if oldest_time > four_hours_ago:
            return "oldest approval is within 4 hours, no backlog"

        # Group by approver
        approver_groups: dict[str, list] = {}
        for item in pending:
            approver = item.get("assigned_to") or "unassigned"
            approver_groups.setdefault(approver, []).append(item)

        notified = 0
        for approver_id, items in approver_groups.items():
            if approver_id == "unassigned" or len(items) < 2:
                continue

            # Build summary
            low_amount = [i for i in items if float(i.get("amount", 0) or 0) < 1000]
            high_amount = [i for i in items if float(i.get("amount", 0) or 0) >= 1000]

            summary_parts = [f"您有 {len(items)} 条待审批事项积压"]
            if low_amount:
                summary_parts.append(f"其中 {len(low_amount)} 条金额<¥1000，建议批量快速处理")
            if high_amount:
                total_high = sum(float(i.get("amount", 0) or 0) for i in high_amount)
                summary_parts.append(f"{len(high_amount)} 条高金额（合计 ¥{total_high:,.0f}）需要重点审核")

            try:
                await send_notification(
                    title=f"📋 审批积压提醒 ({len(items)}条待处理)",
                    content="\n".join(summary_parts),
                    target_user_id=approver_id,
                    priority=NotificationPriority.HIGH,
                )
                notified += 1
            except Exception as e:
                logger.error(f"Approval backlog notification failed for {approver_id}: {e}")

        return f"Approval backlog alerts sent to {notified} approvers ({len(pending)} total pending)"

    return _run_async(_run())


# ---------------------------------------------------------------------------
# Sensor 5: Target Progress Gap Detection
# ---------------------------------------------------------------------------

@celery_app.task
def sensor_target_progress():
    """Detect users falling behind on monthly targets.

    Runs daily at 17:00. Past mid-month, if completion <50%,
    generates AI strategy suggestions and notifies the user + their manager.
    """

    async def _run():
        from app.core.database import supabase
        from app.services.notification_service import send_notification

        if not supabase:
            return "skipped: no db"

        today = datetime.now().date()
        day_of_month = today.day
        import calendar
        days_in_month = calendar.monthrange(today.year, today.month)[1]

        # Only trigger past mid-month
        if day_of_month < days_in_month // 2:
            return f"day {day_of_month}/{days_in_month}, not past mid-month yet"

        month_progress = day_of_month / days_in_month  # Expected completion ratio

        # Query targets for current month
        month_start = today.replace(day=1).isoformat()
        try:
            targets_res = (
                await supabase.table("sales_targets")
                .select("id, user_id, target_value, current_value, metric_type")
                .gte("period_start", month_start)
                .execute()
            )
        except Exception:
            # Fallback: try users with score-based targets
            try:
                targets_res = (
                    await supabase.table("users")
                    .select("id, name, score, role")
                    .in_("role", ["sales", "founder", "manager"])
                    .execute()
                )
                # No target tracking table, skip
                return "skipped: sales_targets table not available"
            except Exception:
                return "skipped: no target data"

        targets = targets_res.data or []
        if not targets:
            return "no targets set for current month"

        notified = 0
        for target in targets:
            target_val = float(target.get("target_value", 0) or 0)
            current_val = float(target.get("current_value", 0) or 0)
            if target_val <= 0:
                continue

            completion = current_val / target_val
            expected = month_progress

            # Alert if significantly behind (completion < expected * 0.6)
            if completion >= expected * 0.6:
                continue

            user_id = target.get("user_id")
            if not user_id:
                continue

            gap_pct = round((expected - completion) * 100, 1)
            completion_pct = round(completion * 100, 1)

            # Generate strategy suggestion
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
                )
                notified += 1
            except Exception as e:
                logger.error(f"Target progress alert failed for user {user_id}: {e}")

        return f"Sent {notified} target progress alerts for {len(targets)} targets"

    return _run_async(_run())
