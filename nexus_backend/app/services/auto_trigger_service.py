"""
P2 Enhancement: Auto Trigger Service

Implements automatic AI feature triggering without manual activation.
Fixes Issue #4: Users need to manually trigger AI features.

Enhanced with smart business reminders (heartbeat-style data patrol).
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

CN_TZ = timezone(timedelta(hours=8))


class TriggerType(Enum):
    """Types of automatic triggers."""

    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    DATA_BASED = "data_based"
    BEHAVIOR_BASED = "behavior_based"
    CONTEXT_BASED = "context_based"


class TriggerAction(Enum):
    """Actions to take when triggered."""

    START_ANALYSIS = "start_analysis"
    GENERATE_REPORT = "generate_report"
    SEND_NOTIFICATION = "send_notification"
    UPDATE_DASHBOARD = "update_dashboard"
    PROCESS_DATA = "process_data"
    SCHEDULE_TASK = "schedule_task"


@dataclass
class AutoTrigger:
    """Automatic trigger definition."""

    trigger_id: str
    name: str
    trigger_type: TriggerType
    condition: dict[str, Any]
    action: TriggerAction
    action_params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    cooldown_seconds: int = 3600  # Minimum time between triggers
    priority: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TriggerEvent:
    """Record of a trigger event."""

    trigger_id: str
    triggered_at: str
    action: TriggerAction
    result: str
    context: dict[str, Any] = field(default_factory=dict)


class AutoTriggerService:
    """
    P2 Enhancement: Automatic AI feature triggering.

    Features:
    - Time-based triggers
    - Event-based triggers
    - Data-based triggers
    - Behavior-based triggers
    - Context-based triggers
    - Smart scheduling
    """

    # Default triggers
    DEFAULT_TRIGGERS = [
        {
            "trigger_id": "daily_report",
            "name": "每日报告生成",
            "trigger_type": "time_based",
            "condition": {"hour": 8, "minute": 0},
            "action": "generate_report",
            "action_params": {"report_type": "daily"},
        },
        {
            "trigger_id": "weekly_summary",
            "name": "每周摘要",
            "trigger_type": "time_based",
            "condition": {"day_of_week": 0, "hour": 9},
            "action": "generate_report",
            "action_params": {"report_type": "weekly"},
        },
        {
            "trigger_id": "data_threshold",
            "name": "数据阈值告警",
            "trigger_type": "data_based",
            "condition": {"metric": "error_rate", "threshold": 0.05, "operator": ">"},
            "action": "send_notification",
            "action_params": {"type": "alert"},
        },
        {
            "trigger_id": "user_idle_analysis",
            "name": "用户空闲分析",
            "trigger_type": "behavior_based",
            "condition": {"idle_seconds": 60},
            "action": "start_analysis",
            "action_params": {"type": "proactive"},
        },
        {
            "trigger_id": "document_upload",
            "name": "文档上传处理",
            "trigger_type": "event_based",
            "condition": {"event": "document_uploaded"},
            "action": "process_data",
            "action_params": {"auto_analyze": True},
        },
        {
            "trigger_id": "page_context_help",
            "name": "页面上下文帮助",
            "trigger_type": "context_based",
            "condition": {"page": "settings", "time_on_page": 30},
            "action": "send_notification",
            "action_params": {"type": "help", "message": "需要帮助配置吗？"},
        },
    ]

    def __init__(self):
        self._triggers: dict[str, AutoTrigger] = {}
        self._action_handlers: dict[TriggerAction, Callable] = {}
        self._trigger_history: list[TriggerEvent] = []
        self._last_triggered: dict[str, datetime] = {}
        self._running = False
        self._scheduler_task = None

        # In-memory cooldown fallback (when Redis is unavailable)
        # key -> expiry datetime
        self._memory_cooldowns: dict[str, datetime] = {}
        # Content-hash dedup: avoid pushing identical reminder text within 8 hours
        # key = hash(user_id + content), value = expiry datetime
        self._recent_push_hashes: dict[str, datetime] = {}

        # Register default triggers
        self._register_default_triggers()

        # Register default action handlers
        self._register_default_handlers()

    def _register_default_triggers(self):
        """Register default triggers."""
        for trigger_config in self.DEFAULT_TRIGGERS:
            trigger = AutoTrigger(
                trigger_id=trigger_config["trigger_id"],
                name=trigger_config["name"],
                trigger_type=TriggerType(trigger_config["trigger_type"]),
                condition=trigger_config["condition"],
                action=TriggerAction(trigger_config["action"]),
                action_params=trigger_config.get("action_params", {}),
            )
            self._triggers[trigger.trigger_id] = trigger

    def _register_default_handlers(self):
        """Register default action handlers."""
        self.register_handler(TriggerAction.START_ANALYSIS, self._handle_start_analysis)
        self.register_handler(TriggerAction.GENERATE_REPORT, self._handle_generate_report)
        self.register_handler(TriggerAction.SEND_NOTIFICATION, self._handle_send_notification)
        self.register_handler(TriggerAction.UPDATE_DASHBOARD, self._handle_update_dashboard)
        self.register_handler(TriggerAction.PROCESS_DATA, self._handle_process_data)
        self.register_handler(TriggerAction.SCHEDULE_TASK, self._handle_schedule_task)

    def register_handler(self, action: TriggerAction, handler: Callable):
        """Register an action handler."""
        self._action_handlers[action] = handler

    def register_trigger(self, trigger: AutoTrigger):
        """Register a custom trigger."""
        self._triggers[trigger.trigger_id] = trigger

    def unregister_trigger(self, trigger_id: str):
        """Unregister a trigger."""
        if trigger_id in self._triggers:
            del self._triggers[trigger_id]

    async def start(self):
        """Start the auto-trigger service."""
        if self._running:
            return

        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Auto-trigger service started")

    async def stop(self):
        """Stop the auto-trigger service."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            self._scheduler_task = None
        logger.info("Auto-trigger service stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop for time-based triggers + smart reminders."""
        # Wait a bit after startup
        await asyncio.sleep(30)

        while self._running:
            try:
                now = datetime.utcnow()

                # Check time-based triggers
                for _trigger_id, trigger in self._triggers.items():
                    if trigger.trigger_type == TriggerType.TIME_BASED and trigger.enabled:
                        await self._check_time_trigger(trigger, now)

                # Smart business reminders (heartbeat)
                await self._check_smart_reminders()

                # Sleep for 1 minute before next check
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)

    async def _check_time_trigger(self, trigger: AutoTrigger, now: datetime):
        """Check if a time-based trigger should fire."""
        condition = trigger.condition

        # Check hour and minute
        if condition.get("hour") == now.hour and condition.get("minute") == now.minute:
            # Check day of week if specified
            if "day_of_week" in condition and condition["day_of_week"] != now.weekday():
                return

            await self._execute_trigger(trigger)

    async def process_event(self, event_type: str, event_data: dict):
        """
        Process an external event for event-based triggers.

        Args:
            event_type: Type of event
            event_data: Event data
        """
        for _trigger_id, trigger in self._triggers.items():
            if trigger.trigger_type == TriggerType.EVENT_BASED and trigger.enabled:
                condition = trigger.condition

                if condition.get("event") == event_type:
                    await self._execute_trigger(trigger, event_data)

    async def check_data_trigger(self, data: dict[str, Any]):
        """
        Check data-based triggers against current data.

        Args:
            data: Current data state
        """
        for _trigger_id, trigger in self._triggers.items():
            if trigger.trigger_type == TriggerType.DATA_BASED and trigger.enabled:
                condition = trigger.condition

                metric = condition.get("metric")
                threshold = condition.get("threshold")
                operator = condition.get("operator", ">")

                if metric and metric in data:
                    value = data[metric]

                    should_trigger = False
                    if (
                        operator == ">"
                        and value > threshold
                        or operator == "<"
                        and value < threshold
                        or operator == "=="
                        and value == threshold
                    ):
                        should_trigger = True

                    if should_trigger:
                        await self._execute_trigger(trigger, {"metric": metric, "value": value})

    async def check_behavior_trigger(self, user_id: str, behavior_data: dict):
        """
        Check behavior-based triggers.

        Args:
            user_id: User identifier
            behavior_data: User behavior data
        """
        for _trigger_id, trigger in self._triggers.items():
            if trigger.trigger_type == TriggerType.BEHAVIOR_BASED and trigger.enabled:
                condition = trigger.condition

                # Check idle time
                if "idle_seconds" in condition:
                    idle_seconds = behavior_data.get("idle_seconds", 0)
                    if idle_seconds >= condition["idle_seconds"]:
                        await self._execute_trigger(trigger, {"user_id": user_id})

                # Check interaction count
                if "interaction_count" in condition:
                    count = behavior_data.get("interaction_count", 0)
                    if count >= condition["interaction_count"]:
                        await self._execute_trigger(trigger, {"user_id": user_id})

    async def check_context_trigger(self, user_id: str, context: dict):
        """
        Check context-based triggers.

        Args:
            user_id: User identifier
            context: Current context
        """
        for _trigger_id, trigger in self._triggers.items():
            if trigger.trigger_type == TriggerType.CONTEXT_BASED and trigger.enabled:
                condition = trigger.condition

                # Check page context
                if "page" in condition and context.get("page") == condition["page"]:
                    time_on_page = context.get("time_on_page", 0)
                    if time_on_page >= condition.get("time_on_page", 0):
                        await self._execute_trigger(trigger, {"user_id": user_id, "page": context["page"]})

    async def _execute_trigger(self, trigger: AutoTrigger, context: dict = None):
        """Execute a trigger's action."""
        # Check cooldown (Redis-backed for multi-instance safety)
        from app.services.cache_service import cache_service

        cooldown_key = f"auto_trigger:cooldown:{trigger.trigger_id}"
        cached = await cache_service.get(cooldown_key)
        if cached:
            logger.debug(f"Trigger {trigger.trigger_id} on cooldown (Redis)")
            return

        # Get handler
        handler = self._action_handlers.get(trigger.action)
        if not handler:
            logger.warning(f"No handler for action: {trigger.action}")
            return

        try:
            # Execute handler
            params = {**trigger.action_params, "context": context}

            if asyncio.iscoroutinefunction(handler):
                result = await handler(params)
            else:
                result = handler(params)

            # Record trigger — Redis cooldown for multi-instance safety
            await cache_service.set(cooldown_key, "1", ttl=trigger.cooldown_seconds)
            self._last_triggered[trigger.trigger_id] = datetime.utcnow()
            self._trigger_history.append(
                TriggerEvent(
                    trigger_id=trigger.trigger_id,
                    triggered_at=datetime.utcnow().isoformat(),
                    action=trigger.action,
                    result=str(result),
                    context=context or {},
                )
            )

            logger.info(f"Executed trigger {trigger.trigger_id}: {trigger.action.value}")

        except Exception as e:
            logger.error(f"Trigger execution failed: {e}")

    # ── Action Handlers with real AI Agent integration ──

    async def _handle_start_analysis(self, params: dict) -> dict:
        """Run AI agent to perform analysis and notify the user."""
        analysis_type = params.get("type", "general")
        context = params.get("context", {})
        user_id = context.get("user_id") if context else None
        org_id = context.get("org_id") if context else None

        logger.info(f"Auto-starting analysis: {analysis_type} for user={user_id}")

        prompt = f"请对当前业务数据进行 {analysis_type} 分析，给出关键发现和建议。"
        result = await self._invoke_agent(prompt, user_id, org_id, scene_code="auto_analysis")

        # Notify user with the analysis result
        await self._notify_user(
            user_id=user_id,
            title="AI 分析完成",
            content=result.get("response", "分析已完成")[:500],
        )

        return {"status": "completed" if result["success"] else "failed", "analysis_type": analysis_type}

    async def _handle_generate_report(self, params: dict) -> dict:
        """Use AI agent to generate a report and notify."""
        report_type = params.get("report_type", "daily")
        context = params.get("context", {})
        user_id = context.get("user_id") if context else None
        org_id = context.get("org_id") if context else None

        logger.info(f"Auto-generating report: {report_type}")

        prompt_map = {
            "daily": "请生成今日工作日报，包含：关键指标变化、待办事项、风险提示。",
            "weekly": "请生成本周工作周报，包含：本周成果、关键数据、下周计划、问题总结。",
            "monthly": "请生成本月工作月报，包含：月度目标达成情况、核心业绩、趋势分析、改进建议。",
        }
        prompt = prompt_map.get(report_type, f"请生成一份 {report_type} 报告。")
        result = await self._invoke_agent(prompt, user_id, org_id, scene_code="auto_report")

        await self._notify_user(
            user_id=user_id,
            title=f"{report_type} 报告已生成",
            content=f"AI 已自动生成{report_type}报告，请在聊天中查看详情。",
        )

        return {"status": "generated" if result["success"] else "failed", "report_type": report_type}

    async def _handle_send_notification(self, params: dict) -> dict:
        """Send notification to user."""
        notification_type = params.get("type", "info")
        message = params.get("message", "您有新的通知")
        context = params.get("context", {})
        user_id = context.get("user_id") if context else None

        await self._notify_user(user_id=user_id, title="系统通知", content=message)

        return {"status": "sent", "type": notification_type, "message": message}

    async def _handle_update_dashboard(self, params: dict) -> dict:
        """Trigger dashboard data refresh via event bus."""
        logger.info("Auto-updating dashboard")

        try:
            from app.services.event_bus import emit

            await emit("cache.invalidated", {"scope": "dashboard"})
        except Exception as e:
            logger.error(f"Dashboard update event failed: {e}")

        return {"status": "updated", "message": "仪表盘刷新事件已发送"}

    async def _handle_process_data(self, params: dict) -> dict:
        """Process uploaded data with AI analysis when auto_analyze is enabled."""
        auto_analyze = params.get("auto_analyze", False)
        context = params.get("context", {})
        user_id = context.get("user_id") if context else None
        org_id = context.get("org_id") if context else None

        logger.info(f"Auto-processing data, analyze={auto_analyze}")

        if auto_analyze and user_id:
            prompt = "用户上传了新文档，请分析文档内容并提取关键信息要点。"
            result = await self._invoke_agent(prompt, user_id, org_id, scene_code="doc_analysis")
            await self._notify_user(
                user_id=user_id,
                title="文档分析完成",
                content=result.get("response", "文档已处理")[:500],
            )
            return {"status": "analyzed" if result["success"] else "processed"}

        return {"status": "processed", "auto_analyze": auto_analyze}

    async def _handle_schedule_task(self, params: dict) -> dict:
        """Schedule a background task."""
        task_type = params.get("task_type", "general")
        logger.info(f"Auto-scheduling task: {task_type}")

        return {"status": "scheduled", "task_type": task_type, "message": "任务已调度"}

    # ── Internal helpers ──

    async def _invoke_agent(
        self,
        prompt: str,
        user_id: str | None,
        org_id: str | None,
        scene_code: str = "",
    ) -> dict:
        """Invoke the proactive agent runner. Returns result dict."""
        if not user_id:
            return {"success": False, "response": "缺少 user_id，无法执行"}

        try:
            from app.agent.proactive_runner import run_proactive_agent

            return await run_proactive_agent(
                prompt=prompt,
                user_id=user_id,
                org_id=org_id,
                scene_code=scene_code,
            )
        except Exception as e:
            logger.error(f"Proactive agent invocation failed: {e}")
            return {"success": False, "response": str(e)[:200]}

    async def _notify_user(self, user_id: str | None, title: str, content: str) -> None:
        """Send a notification to the user via DB."""
        if not user_id:
            return
        try:
            from app.core.database import supabase

            if supabase:
                await (
                    supabase.table("notifications")
                    .insert({"user_id": user_id, "title": title, "content": content, "type": "info"})
                    .execute()
                )
        except Exception as e:
            logger.error(f"Notification insert failed: {e}")

    def get_trigger_status(self) -> dict:
        """Get status of all triggers."""
        return {
            "running": self._running,
            "trigger_count": len(self._triggers),
            "enabled_count": sum(1 for t in self._triggers.values() if t.enabled),
            "recent_executions": [
                {"trigger_id": e.trigger_id, "action": e.action.value, "triggered_at": e.triggered_at}
                for e in self._trigger_history[-10:]
            ],
        }

    def get_triggers(self, trigger_type: TriggerType = None) -> list[dict]:
        """Get all triggers, optionally filtered by type."""
        triggers = list(self._triggers.values())

        if trigger_type:
            triggers = [t for t in triggers if t.trigger_type == trigger_type]

        return [
            {
                "trigger_id": t.trigger_id,
                "name": t.name,
                "type": t.trigger_type.value,
                "action": t.action.value,
                "enabled": t.enabled,
            }
            for t in triggers
        ]

    # ── Smart Business Reminders (Heartbeat) ──

    _REMINDER_COOLDOWN = 7200  # 2 hours between reminder rounds

    def _check_memory_cooldown(self, key: str) -> bool:
        """Check in-memory cooldown. Returns True if still on cooldown."""
        expiry = self._memory_cooldowns.get(key)
        return bool(expiry and datetime.utcnow() < expiry)

    def _set_memory_cooldown(self, key: str, ttl_seconds: int) -> None:
        """Set in-memory cooldown."""
        self._memory_cooldowns[key] = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        # Lazy cleanup: remove expired keys when dict gets large
        if len(self._memory_cooldowns) > 500:
            now = datetime.utcnow()
            self._memory_cooldowns = {k: v for k, v in self._memory_cooldowns.items() if v > now}

    def _check_push_dedup(self, user_id: str, content: str) -> bool:
        """Check if identical content was already pushed recently. Returns True if duplicate."""
        import hashlib

        content_hash = hashlib.md5(f"{user_id}:{content}".encode()).hexdigest()
        expiry = self._recent_push_hashes.get(content_hash)
        if expiry and datetime.utcnow() < expiry:
            return True
        # Mark as pushed, 8 hours dedup window
        self._recent_push_hashes[content_hash] = datetime.utcnow() + timedelta(hours=8)
        # Lazy cleanup
        if len(self._recent_push_hashes) > 1000:
            now = datetime.utcnow()
            self._recent_push_hashes = {k: v for k, v in self._recent_push_hashes.items() if v > now}
        return False

    async def _check_smart_reminders(self):
        """Heartbeat-style smart reminder: patrol business data and proactively notify users."""
        from app.core.database import supabase

        if not supabase:
            return

        now = datetime.now(CN_TZ)

        # Only during business hours (8:00-21:00)
        if not (8 <= now.hour <= 21):
            return

        # Global cooldown: check in-memory first, then Redis
        sr_cooldown_key = "auto_trigger:cooldown:_smart_reminders"
        if self._check_memory_cooldown(sr_cooldown_key):
            return

        from app.services.cache_service import cache_service

        try:
            cached = await cache_service.get(sr_cooldown_key)
            if cached:
                # Sync memory cooldown from Redis
                self._set_memory_cooldown(sr_cooldown_key, self._REMINDER_COOLDOWN)
                return
        except Exception as e:
            logger.debug("Redis cooldown check unavailable: %s", e)  # proceed with memory-only cooldown

        try:
            await self._remind_pending_approvals(supabase, now)
            await self._remind_due_tasks(supabase, now)
            await self._remind_stale_leads(supabase, now)

            # Set both Redis and in-memory cooldowns
            self._set_memory_cooldown(sr_cooldown_key, self._REMINDER_COOLDOWN)
            try:
                await cache_service.set(sr_cooldown_key, "1", ttl=self._REMINDER_COOLDOWN)
            except Exception as e:
                logger.debug("Redis cooldown set unavailable: %s", e)  # memory cooldown is our safety net
            self._last_triggered["_smart_reminders"] = datetime.utcnow()
        except Exception as e:
            logger.error("[SmartReminder] Check failed: %s", e, exc_info=True)

    async def _remind_pending_approvals(self, supabase, now: datetime):
        """Remind boss/manager about approvals pending > 4 hours."""
        threshold = (now - timedelta(hours=4)).isoformat()

        try:
            result = await (
                supabase.table("approval_requests")
                .select("id, type, description, amount, submitted_at, organization_id")
                .eq("status", "pending")
                .lte("submitted_at", threshold)
                .order("submitted_at")
                .limit(50)
                .execute()
            )
            pending = result.data or []
            if not pending:
                return

            # Group by organization
            org_map: dict[str, list] = {}
            for item in pending:
                org_id = item.get("organization_id") or "default"
                org_map.setdefault(org_id, []).append(item)

            # Find boss/manager users per org to notify
            for org_id, items in org_map.items():
                users_result = await (
                    supabase.table("users")
                    .select("id")
                    .in_("role", ["boss", "manager", "founder"])
                    .eq("organization_id", org_id)
                    .limit(10)
                    .execute()
                )
                reviewers = users_result.data or []

                count = len(items)
                oldest = items[0]
                hours_ago = max(
                    1,
                    int(
                        (
                            now
                            - datetime.fromisoformat(oldest["submitted_at"].replace("Z", "+00:00")).astimezone(CN_TZ)
                        ).total_seconds()
                        / 3600
                    ),
                )

                summary_lines = []
                for item in items[:3]:
                    desc = (item.get("description") or item.get("type", ""))[:30]
                    amt = item.get("amount")
                    line = f"• {desc}" + (f"（¥{amt:,.0f}）" if amt else "")
                    summary_lines.append(line)
                if count > 3:
                    summary_lines.append(f"• ...还有 {count - 3} 项")

                message = (
                    f"📋 您有 {count} 个审批申请待处理（最早已等待 {hours_ago} 小时）：\n\n"
                    + "\n".join(summary_lines)
                    + "\n\n请及时处理，避免影响业务进度。"
                )

                for user in reviewers:
                    await self._push_proactive_reminder(
                        user_id=user["id"],
                        title="审批超时提醒",
                        message=message,
                        reminder_type="approval_timeout",
                    )
        except Exception as e:
            logger.error("[SmartReminder] Approval check failed: %s", e)

    async def _remind_due_tasks(self, supabase, now: datetime):
        """Remind users about tasks due today or overdue."""
        today = now.strftime("%Y-%m-%d")

        try:
            result = await (
                supabase.table("oa_tasks")
                .select("id, title, priority, due_date, assignee_id")
                .in_("status", ["todo", "in_progress"])
                .not_.is_("due_date", "null")
                .lte("due_date", today)
                .order("due_date")
                .limit(50)
                .execute()
            )
            tasks = result.data or []
            if not tasks:
                return

            # Group by assignee
            user_map: dict[str, list] = {}
            for task in tasks:
                uid = task.get("assignee_id")
                if uid:
                    user_map.setdefault(uid, []).append(task)

            for user_id, user_tasks in user_map.items():
                overdue = [t for t in user_tasks if t["due_date"] < today]
                due_today = [t for t in user_tasks if t["due_date"] == today]

                lines = []
                if overdue:
                    lines.append(f"🔴 已逾期 {len(overdue)} 项：")
                    for t in overdue[:3]:
                        lines.append(f"  • {t['title'][:30]}（截止 {t['due_date']}）")
                if due_today:
                    lines.append(f"🟡 今日到期 {len(due_today)} 项：")
                    for t in due_today[:3]:
                        lines.append(f"  • {t['title'][:30]}")

                total = len(user_tasks)
                if total > 6:
                    lines.append(f"  ...共 {total} 项待处理")

                message = "⏰ 任务到期提醒\n\n" + "\n".join(lines) + "\n\n请及时完成或调整截止日期。"

                await self._push_proactive_reminder(
                    user_id=user_id,
                    title="任务到期提醒",
                    message=message,
                    reminder_type="task_due",
                )
        except Exception as e:
            logger.error("[SmartReminder] Task due check failed: %s", e)

    async def _remind_stale_leads(self, supabase, now: datetime):
        """Remind sales reps about leads not updated in 7+ days."""
        threshold = (now - timedelta(days=7)).isoformat()

        try:
            # Live DB uses "stage" not "status"; filter in Python to avoid schema drift
            result = await (
                supabase.table("sales_leads")
                .select("*")
                .lte("updated_at", threshold)
                .order("updated_at")
                .limit(100)
                .execute()
            )
            all_leads = result.data or []
            # Exclude terminal stages regardless of column name
            terminal = {"won", "lost", "closed", "converted"}
            leads = [l for l in all_leads if (l.get("stage") or l.get("status") or "").lower() not in terminal][:50]
            if not leads:
                return

            # Group by owner — try common column names for owner field
            user_map: dict[str, list] = {}
            for lead in leads:
                uid = lead.get("owner_id") or lead.get("user_id") or lead.get("assigned_to")
                if uid:
                    user_map.setdefault(uid, []).append(lead)

            for user_id, user_leads in user_map.items():
                lines = []
                for lead in user_leads[:5]:
                    # Graceful label: try multiple possible name columns
                    name = (
                        lead.get("professor")
                        or lead.get("company_name")
                        or lead.get("source_paper")
                        or lead.get("name")
                        or "未命名"
                    )
                    days = max(
                        1,
                        int(
                            (
                                now
                                - datetime.fromisoformat(lead["updated_at"].replace("Z", "+00:00")).astimezone(CN_TZ)
                            ).total_seconds()
                            / 86400
                        ),
                    )
                    score = lead.get("match_score") or lead.get("score") or 0
                    lines.append(f"  • {name[:20]}（{days}天未跟进，匹配度{score}）")

                count = len(user_leads)
                if count > 5:
                    lines.append(f"  ...共 {count} 个商机需关注")

                message = (
                    f"🔔 商机跟进提醒：您有 {count} 个商机超过 7 天未跟进\n\n"
                    + "\n".join(lines)
                    + "\n\n建议及时联系客户，避免商机流失。"
                )

                await self._push_proactive_reminder(
                    user_id=user_id,
                    title="商机跟进提醒",
                    message=message,
                    reminder_type="lead_followup",
                )
        except Exception as e:
            logger.error("[SmartReminder] Lead followup check failed: %s", e)

    async def _push_proactive_reminder(self, user_id: str, title: str, message: str, reminder_type: str):
        """Push a smart reminder as proactive chat message + notification."""
        cooldown_key = f"auto_trigger:cooldown:_reminder_{reminder_type}_{user_id}"

        # Layer 1: In-memory cooldown (always available)
        if self._check_memory_cooldown(cooldown_key):
            return

        # Layer 2: Content-based dedup (prevent identical messages)
        if self._check_push_dedup(user_id, message):
            logger.debug("[SmartReminder] Skipped duplicate content for %s", user_id[:8])
            return

        # Layer 3: Redis cooldown (for multi-instance safety)
        from app.services.cache_service import cache_service

        try:
            cached = await cache_service.get(cooldown_key)
            if cached:
                self._set_memory_cooldown(cooldown_key, 14400)
                return
        except Exception as e:
            logger.debug("Redis cooldown check unavailable: %s", e)  # memory cooldown is our safety net

        try:
            from app.services.agent_result_pusher import push_agent_result

            await push_agent_result(
                user_id=user_id,
                title=title,
                message=message,
                agent_name="smart_reminder",
                metadata={"source": "smart_reminder", "task_name": title, "reminder_type": reminder_type},
            )

            # Set both memory and Redis cooldowns
            self._set_memory_cooldown(cooldown_key, 14400)
            self._last_triggered[cooldown_key] = datetime.utcnow()
            try:
                await cache_service.set(cooldown_key, "1", ttl=14400)  # 4 hours
            except Exception as e:
                logger.debug("Redis cooldown set unavailable: %s", e)
            logger.info("[SmartReminder] Sent '%s' to user %s", reminder_type, user_id[:8])
        except Exception as e:
            logger.error("[SmartReminder] Push failed for %s: %s", user_id[:8], e)


# Global instance
auto_trigger_service = AutoTriggerService()
