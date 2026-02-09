"""
P2 Optimization: Event Bus / Message Queue Service
Provides event-driven architecture for async processing.
Supports in-memory queue with optional Redis/Celery backend.
"""
import asyncio
import os
import json
import time
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid


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
    payload: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Event":
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
        self._handlers: Dict[str, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._event_history: List[Event] = []
        self._max_history = 1000
    
    def subscribe(self, event_type: str, handler: Callable):
        """
        Subscribe a handler to an event type.
        Handler should be an async function accepting Event.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        print(f"EventBus: Subscribed handler to {event_type}")
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """Unsubscribe a handler from an event type"""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]
    
    async def publish(self, event: Event):
        """
        Publish an event to the bus.
        Handlers are executed asynchronously.
        """
        await self._queue.put(event)
        
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
    
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
                print(f"EventBus: Handler error for {event.type}: {e}")
    
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
                        return_exceptions=True
                    )
                
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"EventBus: Processing error: {e}")
    
    async def _safe_handle(self, handler: Callable, event: Event):
        """Safely execute a handler with error catching"""
        try:
            await handler(event)
        except Exception as e:
            print(f"EventBus: Handler error for {event.type}: {e}")
    
    async def start(self):
        """Start the event processing worker"""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._process_events())
        print("EventBus: Started")
    
    async def stop(self):
        """Stop the event processing worker"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        print("EventBus: Stopped")
    
    def get_recent_events(self, limit: int = 100, event_type: str = None) -> List[Event]:
        """Get recent events from history"""
        events = self._event_history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]


# Global event bus instance
event_bus = InMemoryEventBus()


# ============== Convenience Functions ==============

async def emit(event_type: str, payload: Dict = None, user_id: str = None, **kwargs):
    """
    Convenience function to emit an event.
    
    Usage:
        await emit("approval.submitted", {"amount": 1000}, user_id="xxx")
    """
    event = Event(
        type=event_type if isinstance(event_type, str) else event_type.value,
        payload=payload or {},
        user_id=user_id,
        metadata=kwargs
    )
    await event_bus.publish(event)
    return event.id


def on(event_type: str):
    """
    Decorator to register an event handler.
    
    Usage:
        @on("approval.submitted")
        async def handle_approval(event: Event):
            print(f"New approval: {event.payload}")
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
        print(f"[EVENT] {event.type}: {json.dumps(event.payload)[:200]}")


@on(EventType.BADGE_AWARDED.value)
async def notify_badge_awarded(event: Event):
    """Send notification when a badge is awarded"""
    from app.core.database import supabase
    
    user_id = event.payload.get("user_id")
    badge_name = event.payload.get("badge_name")
    
    if user_id and badge_name and supabase:
        try:
            await supabase.table("notifications").insert({
                "user_id": user_id,
                "title": "🏆 恭喜获得新徽章！",
                "content": f"您获得了「{badge_name}」徽章，继续加油！",
                "type": "success"
            }).execute()
        except Exception as e:
            print(f"Failed to create badge notification: {e}")


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
            await supabase.table("notifications").insert({
                "user_id": boss["id"],
                "title": "⚠️ 审批需要您的处理",
                "content": f"有一个金额为 ¥{event.payload.get('amount', 0)} 的{event.payload.get('type', '申请')}需要您审批",
                "type": "warning"
            }).execute()
    except Exception as e:
        print(f"Failed to notify boss: {e}")


@on(EventType.DEAL_WON.value)
async def calculate_deal_bonus(event: Event):
    """Calculate and award bonus when a deal is won"""
    from app.core.database import supabase
    from app.core.config import settings
    
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
        await supabase.rpc("increment_user_bonus", {
            "p_user_id": user_id,
            "p_amount": bonus
        }).execute()
        
        # Create incentive record
        await supabase.table("incentives").insert({
            "user_id": user_id,
            "type": "bonus",
            "amount": bonus,
            "reason": f"成交奖励 (订单金额: ¥{deal_value})",
            "status": "pending"
        }).execute()
        
        print(f"Deal bonus calculated: ¥{bonus} for user {user_id}")
    except Exception as e:
        print(f"Failed to calculate deal bonus: {e}")