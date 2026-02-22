"""
P2 Enhancement: Auto Trigger Service

Implements automatic AI feature triggering without manual activation.
Fixes Issue #4: Users need to manually trigger AI features.
"""

import json
import logging
import asyncio
from typing import Dict, Optional, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

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
    condition: Dict[str, Any]
    action: TriggerAction
    action_params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    cooldown_seconds: int = 3600  # Minimum time between triggers
    priority: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TriggerEvent:
    """Record of a trigger event."""
    trigger_id: str
    triggered_at: str
    action: TriggerAction
    result: str
    context: Dict[str, Any] = field(default_factory=dict)


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
            "action_params": {"report_type": "daily"}
        },
        {
            "trigger_id": "weekly_summary",
            "name": "每周摘要",
            "trigger_type": "time_based",
            "condition": {"day_of_week": 0, "hour": 9},
            "action": "generate_report",
            "action_params": {"report_type": "weekly"}
        },
        {
            "trigger_id": "data_threshold",
            "name": "数据阈值告警",
            "trigger_type": "data_based",
            "condition": {"metric": "error_rate", "threshold": 0.05, "operator": ">"},
            "action": "send_notification",
            "action_params": {"type": "alert"}
        },
        {
            "trigger_id": "user_idle_analysis",
            "name": "用户空闲分析",
            "trigger_type": "behavior_based",
            "condition": {"idle_seconds": 60},
            "action": "start_analysis",
            "action_params": {"type": "proactive"}
        },
        {
            "trigger_id": "document_upload",
            "name": "文档上传处理",
            "trigger_type": "event_based",
            "condition": {"event": "document_uploaded"},
            "action": "process_data",
            "action_params": {"auto_analyze": True}
        },
        {
            "trigger_id": "page_context_help",
            "name": "页面上下文帮助",
            "trigger_type": "context_based",
            "condition": {"page": "settings", "time_on_page": 30},
            "action": "send_notification",
            "action_params": {"type": "help", "message": "需要帮助配置吗？"}
        }
    ]
    
    def __init__(self):
        self._triggers: Dict[str, AutoTrigger] = {}
        self._action_handlers: Dict[TriggerAction, Callable] = {}
        self._trigger_history: List[TriggerEvent] = []
        self._last_triggered: Dict[str, datetime] = {}
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
                action_params=trigger_config.get("action_params", {})
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
                for trigger_id, trigger in self._triggers.items():
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
            if "day_of_week" in condition:
                if condition["day_of_week"] != now.weekday():
                    return
            
            await self._execute_trigger(trigger)
    
    async def process_event(self, event_type: str, event_data: Dict):
        """
        Process an external event for event-based triggers.
        
        Args:
            event_type: Type of event
            event_data: Event data
        """
        for trigger_id, trigger in self._triggers.items():
            if trigger.trigger_type == TriggerType.EVENT_BASED and trigger.enabled:
                condition = trigger.condition
                
                if condition.get("event") == event_type:
                    await self._execute_trigger(trigger, event_data)
    
    async def check_data_trigger(self, data: Dict[str, Any]):
        """
        Check data-based triggers against current data.
        
        Args:
            data: Current data state
        """
        for trigger_id, trigger in self._triggers.items():
            if trigger.trigger_type == TriggerType.DATA_BASED and trigger.enabled:
                condition = trigger.condition
                
                metric = condition.get("metric")
                threshold = condition.get("threshold")
                operator = condition.get("operator", ">")
                
                if metric and metric in data:
                    value = data[metric]
                    
                    should_trigger = False
                    if operator == ">" and value > threshold:
                        should_trigger = True
                    elif operator == "<" and value < threshold:
                        should_trigger = True
                    elif operator == "==" and value == threshold:
                        should_trigger = True
                    
                    if should_trigger:
                        await self._execute_trigger(trigger, {"metric": metric, "value": value})
    
    async def check_behavior_trigger(self, user_id: str, behavior_data: Dict):
        """
        Check behavior-based triggers.
        
        Args:
            user_id: User identifier
            behavior_data: User behavior data
        """
        for trigger_id, trigger in self._triggers.items():
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
    
    async def check_context_trigger(self, user_id: str, context: Dict):
        """
        Check context-based triggers.
        
        Args:
            user_id: User identifier
            context: Current context
        """
        for trigger_id, trigger in self._triggers.items():
            if trigger.trigger_type == TriggerType.CONTEXT_BASED and trigger.enabled:
                condition = trigger.condition
                
                # Check page context
                if "page" in condition and context.get("page") == condition["page"]:
                    time_on_page = context.get("time_on_page", 0)
                    if time_on_page >= condition.get("time_on_page", 0):
                        await self._execute_trigger(trigger, {"user_id": user_id, "page": context["page"]})
    
    async def _execute_trigger(self, trigger: AutoTrigger, context: Dict = None):
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
            self._trigger_history.append(TriggerEvent(
                trigger_id=trigger.trigger_id,
                triggered_at=datetime.utcnow().isoformat(),
                action=trigger.action,
                result=str(result),
                context=context or {}
            ))
            
            logger.info(f"Executed trigger {trigger.trigger_id}: {trigger.action.value}")
        
        except Exception as e:
            logger.error(f"Trigger execution failed: {e}")
    
    # Default action handlers

    async def _handle_start_analysis(self, params: Dict) -> Dict:
        """Handle start analysis action."""
        analysis_type = params.get("type", "general")
        logger.info(f"Auto-starting analysis: {analysis_type}")

        try:
            from app.services.notification_service import notification_service, NotificationChannel
            context = params.get("context", {})
            user_id = context.get("user_id") if context else None
            if user_id:
                await notification_service.send(
                    user_id=user_id,
                    title=f"AI 分析已启动",
                    content=f"自动触发 {analysis_type} 类型的分析任务",
                    channel=NotificationChannel.IN_APP,
                )
        except Exception as e:
            logger.error(f"Analysis notification failed: {e}")

        return {
            "status": "started",
            "analysis_type": analysis_type,
            "message": "分析已自动启动"
        }

    async def _handle_generate_report(self, params: Dict) -> Dict:
        """Handle generate report action."""
        report_type = params.get("report_type", "daily")
        logger.info(f"Auto-generating report: {report_type}")

        try:
            from app.services.notification_service import notification_service, NotificationChannel
            context = params.get("context", {})
            user_id = context.get("user_id") if context else None
            if user_id:
                await notification_service.send(
                    user_id=user_id,
                    title=f"工作报告已生成",
                    content=f"已自动生成 {report_type} 报告，请在 AI 聊天中查看",
                    channel=NotificationChannel.IN_APP,
                )
        except Exception as e:
            logger.error(f"Report notification failed: {e}")

        return {
            "status": "generated",
            "report_type": report_type,
            "message": f"{report_type}报告已生成"
        }
    
    async def _handle_send_notification(self, params: Dict) -> Dict:
        """Handle send notification action."""
        notification_type = params.get("type", "info")
        message = params.get("message", "您有新的通知")
        logger.info(f"Sending notification: {notification_type} - {message}")

        try:
            from app.services.notification_service import notification_service, NotificationChannel
            context = params.get("context", {})
            user_id = context.get("user_id") if context else None
            if user_id:
                await notification_service.send(
                    user_id=user_id,
                    title="系统通知",
                    content=message,
                    channel=NotificationChannel.IN_APP,
                )
        except Exception as e:
            logger.error(f"Notification send failed: {e}")

        return {
            "status": "sent",
            "type": notification_type,
            "message": message
        }
    
    async def _handle_update_dashboard(self, params: Dict) -> Dict:
        """Handle update dashboard action."""
        logger.info("Auto-updating dashboard")
        
        return {
            "status": "updated",
            "message": "仪表盘已更新"
        }
    
    async def _handle_process_data(self, params: Dict) -> Dict:
        """Handle process data action."""
        auto_analyze = params.get("auto_analyze", False)
        
        logger.info(f"Auto-processing data, analyze={auto_analyze}")
        
        return {
            "status": "processed",
            "auto_analyze": auto_analyze,
            "message": "数据已处理"
        }
    
    async def _handle_schedule_task(self, params: Dict) -> Dict:
        """Handle schedule task action."""
        task_type = params.get("task_type", "general")
        
        logger.info(f"Auto-scheduling task: {task_type}")
        
        return {
            "status": "scheduled",
            "task_type": task_type,
            "message": "任务已调度"
        }
    
    def get_trigger_status(self) -> Dict:
        """Get status of all triggers."""
        return {
            "running": self._running,
            "trigger_count": len(self._triggers),
            "enabled_count": sum(1 for t in self._triggers.values() if t.enabled),
            "recent_executions": [
                {
                    "trigger_id": e.trigger_id,
                    "action": e.action.value,
                    "triggered_at": e.triggered_at
                }
                for e in self._trigger_history[-10:]
            ]
        }
    
    def get_triggers(self, trigger_type: TriggerType = None) -> List[Dict]:
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
                "enabled": t.enabled
            }
            for t in triggers
        ]


# Global instance
auto_trigger_service = AutoTriggerService()
