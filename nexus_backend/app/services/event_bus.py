"""
P2 Optimization: Event Bus / Message Queue Service
Provides event-driven architecture for async processing.
Supports in-memory queue with optional Redis/Celery backend.
"""

import asyncio
import contextlib
import json
import logging
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Predefined event types for the system"""

    # Approval Events
    APPROVAL_SUBMITTED = "approval.submitted"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_ESCALATED = "approval.escalated"

    # Performance Events
    PERFORMANCE_UPDATED = "performance.updated"
    PERFORMANCE_THRESHOLD_REACHED = "performance.threshold_reached"
    BADGE_AWARDED = "badge.awarded"

    # Sales Events
    LEAD_CREATED = "lead.created"
    LEAD_UPDATED = "lead.updated"
    DEAL_WON = "deal.won"
    DEAL_LOST = "deal.lost"

    # Document Events
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_PROCESSED = "document.processed"
    DOCUMENT_FAILED = "document.failed"

    # User Events
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_SETTINGS_CHANGED = "user.settings_changed"

    # AI Events
    AI_CHAT_COMPLETED = "ai.chat_completed"
    AI_TOOL_EXECUTED = "ai.tool_executed"
    AI_ERROR = "ai.error"

    # System Events
    SYSTEM_ALERT = "system.alert"
    CACHE_INVALIDATED = "cache.invalidated"


@dataclass
class Event:
    """Represents an event in the system"""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        return cls(**data)


class EventHandler:
    """Base class for event handlers"""

    async def handle(self, event: Event) -> None:
        raise NotImplementedError


class InMemoryEventBus:
    """
    In-memory event bus implementation.
    Suitable for single-instance deployments.
    For multi-instance, use Redis-backed implementation.
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._event_history: list[Event] = []
        self._max_history = 1000

    def subscribe(self, event_type: str, handler: Callable):
        """
        Subscribe a handler to an event type.
        Handler should be an async function accepting Event.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"EventBus: Subscribed handler to {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe a handler from an event type"""
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]

    async def publish(self, event: Event):
        """
        Publish an event to the bus.
        Handlers are executed asynchronously.
        """
        await self._queue.put(event)

        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history :]

    async def publish_sync(self, event: Event):
        """
        Publish an event and wait for all handlers to complete.
        Use sparingly - prefer async publish for performance.
        """
        handlers = self._handlers.get(event.type, [])
        # Also check for wildcard handlers
        handlers += self._handlers.get("*", [])

        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"EventBus: Handler error for {event.type}: {e}")

    async def _process_events(self):
        """Background worker to process events"""
        while self._running:
            try:
                # Wait for an event with timeout
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)

                handlers = self._handlers.get(event.type, [])
                # Also check for wildcard handlers
                handlers += self._handlers.get("*", [])

                # Execute handlers concurrently
                if handlers:
                    await asyncio.gather(
                        *[self._safe_handle(handler, event) for handler in handlers],
                        return_exceptions=True,
                    )

                self._queue.task_done()
            except TimeoutError:
                continue
            except Exception as e:
                logger.error(f"EventBus: Processing error: {e}")

    async def _safe_handle(self, handler: Callable, event: Event):
        """Safely execute a handler with error catching"""
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"EventBus: Handler error for {event.type}: {e}")

    async def start(self):
        """Start the event processing worker"""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._process_events())
        logger.info("EventBus: Started")

    async def stop(self):
        """Stop the event processing worker"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
        logger.info("EventBus: Stopped")

    def get_recent_events(self, limit: int = 100, event_type: str = None) -> list[Event]:
        """Get recent events from history"""
        events = self._event_history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]


# Global event bus instance
event_bus = InMemoryEventBus()


# ============== Convenience Functions ==============


async def emit(event_type: str, payload: dict = None, user_id: str = None, **kwargs):
    """
    Convenience function to emit an event.

    Usage:
        await emit("approval.submitted", {"amount": 1000}, user_id="xxx")
    """
    event = Event(
        type=event_type if isinstance(event_type, str) else event_type.value,
        payload=payload or {},
        user_id=user_id,
        metadata=kwargs,
    )
    await event_bus.publish(event)
    return event.id


def on(event_type: str):
    """
    Decorator to register an event handler.

    Usage:
        @on("approval.submitted")
        async def handle_approval(event: Event):
            logger.info(f"New approval: {event.payload}")
    """

    def decorator(func):
        event_bus.subscribe(event_type, func)
        return func

    return decorator


# ============== Built-in Event Handlers ==============


@on("*")
async def log_all_events(event: Event):
    """Log all events for debugging (can be disabled in production)"""
    if os.getenv("DEBUG_EVENTS") == "true":
        logger.debug(f"[EVENT] {event.type}: {json.dumps(event.payload)[:200]}")


@on(EventType.BADGE_AWARDED.value)
async def notify_badge_awarded(event: Event):
    """Send notification when a badge is awarded"""
    from app.core.database import supabase

    user_id = event.payload.get("user_id")
    badge_name = event.payload.get("badge_name")

    if user_id and badge_name and supabase:
        try:
            await supabase.table("notifications").insert(
                {
                    "user_id": user_id,
                    "title": "🏆 恭喜获得新徽章！",
                    "content": f"您获得了「{badge_name}」徽章，继续加油！",
                    "type": "success",
                }
            ).execute()
        except Exception as e:
            logger.error(f"Failed to create badge notification: {e}")


@on(EventType.APPROVAL_ESCALATED.value)
async def notify_approval_escalated(event: Event):
    """Notify boss when approval is escalated"""
    from app.core.database import supabase

    if not supabase:
        return

    try:
        # Find all bosses
        bosses = await supabase.table("users").select("id").eq("role", "founder").execute()

        for boss in bosses.data or []:
            await supabase.table("notifications").insert(
                {
                    "user_id": boss["id"],
                    "title": "⚠️ 审批需要您的处理",
                    "content": f"有一个金额为 ¥{event.payload.get('amount', 0)} 的{event.payload.get('type', '申请')}需要您审批",
                    "type": "warning",
                }
            ).execute()
    except Exception as e:
        logger.error(f"Failed to notify boss: {e}")


@on(EventType.SYSTEM_ALERT.value)
async def handle_system_alert(event: Event):
    """P0 Fix: Forward system alerts to org admins via notifications table.

    Ensures critical alerts (credit exhaustion, service degradation) are not
    silently swallowed in memory but delivered to relevant administrators.
    """
    from app.core.database import supabase

    if not supabase:
        return

    org_id = event.payload.get("org_id")
    alert_type = event.payload.get("alert_type", "unknown")
    severity = event.payload.get("severity", "warning")
    usage_pct = event.payload.get("usage_percentage")
    credit_type = event.payload.get("credit_type", "")

    # Build human-readable message
    title_map = {
        "credit_exhaustion": "配额即将耗尽",
        "service_degradation": "服务降级告警",
        "rate_limit_breach": "请求频率异常",
    }
    title = f"⚠️ {title_map.get(alert_type, '系统告警')}"
    content = f"告警类型: {alert_type}"
    if credit_type:
        content += f", 资源: {credit_type}"
    if usage_pct is not None:
        content += f", 使用率: {usage_pct}%"

    notification_type = "error" if severity == "critical" else "warning"

    try:
        # Find org admins (founders and admins)
        if org_id:
            admins = (
                await supabase.table("users")
                .select("id")
                .eq("org_id", org_id)
                .in_("role", ["founder", "admin"])
                .execute()
            )
        else:
            admins = await supabase.table("users").select("id").eq("role", "founder").execute()

        for admin in admins.data or []:
            await supabase.table("notifications").insert(
                {
                    "user_id": admin["id"],
                    "title": title,
                    "content": content,
                    "type": notification_type,
                }
            ).execute()

        logger.info(
            f"[EventBus] SYSTEM_ALERT dispatched to {len(admins.data or [])} admins: "
            f"alert_type={alert_type} severity={severity}"
        )
    except Exception as e:
        logger.error(f"Failed to dispatch system alert notification: {e}")


@on(EventType.USER_SETTINGS_CHANGED.value)
async def invalidate_org_cache(event: Event):
    """P1 Fix: Clear org_id cache when user settings change."""
    user_id = event.payload.get("user_id") or event.user_id
    if not user_id:
        return
    try:
        from app.core.security_middleware import TenantContextMiddleware

        cache = TenantContextMiddleware._org_cache
        # Remove the user's cached org_id entry
        keys_to_remove = [k for k in cache if k == user_id]
        for k in keys_to_remove:
            del cache[k]
            logger.info(f"[EventBus] Invalidated org_id cache for user {user_id}")
    except Exception as e:
        logger.debug(f"org_id cache invalidation skipped: {e}")


@on(EventType.DEAL_WON.value)
async def calculate_deal_bonus(event: Event):
    """Calculate and award bonus when a deal is won"""
    from app.core.database import supabase

    if not supabase:
        return

    user_id = event.payload.get("user_id")
    deal_value = event.payload.get("value", 0)

    if not user_id or deal_value <= 0:
        return

    try:
        # Calculate bonus (example: 0.5% of deal value)
        bonus = deal_value * 0.005

        # Update user's total bonus
        await supabase.rpc("increment_user_bonus", {"p_user_id": user_id, "p_amount": bonus}).execute()

        # Create incentive record
        await supabase.table("incentives").insert(
            {
                "user_id": user_id,
                "type": "bonus",
                "amount": bonus,
                "reason": f"成交奖励 (订单金额: ¥{deal_value})",
                "status": "pending",
            }
        ).execute()

        logger.info(f"Deal bonus calculated: ¥{bonus} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to calculate deal bonus: {e}")
