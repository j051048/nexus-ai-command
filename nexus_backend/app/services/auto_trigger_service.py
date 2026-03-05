"""
P2 Enhancement: Auto Trigger Service

Implements automatic AI feature triggering without manual activation.
Fixes Issue #4: Users need to manually trigger AI features.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


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
        """Main scheduler loop for time-based triggers."""
        while self._running:
            try:
                now = datetime.utcnow()

                # Check time-based triggers
                for _trigger_id, trigger in self._triggers.items():
                    if trigger.trigger_type == TriggerType.TIME_BASED and trigger.enabled:
                        await self._check_time_trigger(trigger, now)

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
        # Check cooldown
        if trigger.trigger_id in self._last_triggered:
            last = self._last_triggered[trigger.trigger_id]
            elapsed = (datetime.utcnow() - last).total_seconds()
            if elapsed < trigger.cooldown_seconds:
                logger.debug(f"Trigger {trigger.trigger_id} on cooldown")
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

            # Record trigger
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


# Global instance
auto_trigger_service = AutoTriggerService()
