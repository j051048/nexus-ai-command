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
    APPROVAL_RECALLED = "approval.recalled"

    # Performance Events
    PERFORMANCE_UPDATED = "performance.updated"
    PERFORMANCE_THRESHOLD_REACHED = "performance.threshold_reached"
    BADGE_AWARDED = "badge.awarded"

    # Sales Events
    LEAD_CREATED = "lead.created"
    LEAD_UPDATED = "lead.updated"
    LEAD_QUALIFIED = "lead.qualified"
    DEAL_WON = "deal.won"
    DEAL_LOST = "deal.lost"

    # Contract Events
    CONTRACT_CREATED = "contract.created"
    CONTRACT_SIGNED = "contract.signed"
    CONTRACT_EXPIRING = "contract.expiring"

    # Finance Events
    INVOICE_CREATED = "invoice.created"
    PAYMENT_RECEIVED = "payment.received"

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

    # Enterprise Module Events (Phase 2)
    EMPLOYEE_ONBOARDED = "employee.onboarded"
    EMPLOYEE_RESIGNED = "employee.resigned"
    EMPLOYEE_TRANSFERRED = "employee.transferred"
    LEAVE_APPROVED = "leave.approved"
    LEAVE_REJECTED = "leave.rejected"
    EXPENSE_SUBMITTED = "expense.submitted"
    EXPENSE_APPROVED = "expense.approved"
    ASSET_ALLOCATED = "asset.allocated"
    ASSET_RETURNED = "asset.returned"
    ASSET_SCRAPPED = "asset.scrapped"
    WORK_ORDER_CREATED = "work_order.created"
    WORK_ORDER_RESOLVED = "work_order.resolved"
    INVENTORY_LOW_STOCK = "inventory.low_stock"
    CERTIFICATE_EXPIRING = "certificate.expiring"


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
        """Stop the event processing worker with graceful queue drain."""
        self._running = False
        if self._worker_task:
            # Drain remaining events in the queue (max 5s grace period)
            try:
                await asyncio.wait_for(self._queue.join(), timeout=5.0)
                logger.info(
                    f"EventBus: Queue drained ({self._queue.qsize()} remaining)"
                )
            except TimeoutError:
                logger.warning(
                    f"EventBus: Queue drain timeout, {self._queue.qsize()} events dropped"
                )
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
        logger.info("EventBus: Stopped")

    def get_recent_events(
        self, limit: int = 100, event_type: str = None
    ) -> list[Event]:
        """Get recent events from history"""
        events = self._event_history
        if event_type:
            events = [e for e in events if e.type == event_type]
        return events[-limit:]


# Global event bus instance
# #36/49: Use Redis-backed event bus when Redis is available, otherwise in-memory
try:
    from app.services.redis_event_bus import redis_event_bus

    event_bus = redis_event_bus
    logger.info("[EventBus] Using RedisEventBus (Redis Pub/Sub when available)")
except Exception as _e:
    event_bus = InMemoryEventBus()
    logger.info(f"[EventBus] Using InMemoryEventBus (RedisEventBus init failed: {_e})")


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
            await (
                supabase.table("notifications")
                .insert(
                    {
                        "user_id": user_id,
                        "title": "🏆 恭喜获得新徽章！",
                        "content": f"您获得了「{badge_name}」徽章，继续加油！",
                        "type": "success",
                        "action_url": "/gamification",
                    }
                )
                .execute()
            )
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
        bosses = (
            await supabase.table("users").select("id").eq("role", "founder").execute()
        )

        for boss in bosses.data or []:
            await (
                supabase.table("notifications")
                .insert(
                    {
                        "user_id": boss["id"],
                        "title": "⚠️ 审批需要您的处理",
                        "content": f"有一个金额为 ¥{event.payload.get('amount', 0)} 的{event.payload.get('type', '申请')}需要您审批",
                        "type": "warning",
                        "action_url": "/approval",
                    }
                )
                .execute()
            )
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
                .in_("role", ["founder", "boss"])
                .execute()
            )
        else:
            admins = (
                await supabase.table("users")
                .select("id")
                .eq("role", "founder")
                .execute()
            )

        for admin in admins.data or []:
            await (
                supabase.table("notifications")
                .insert(
                    {
                        "user_id": admin["id"],
                        "title": title,
                        "content": content,
                        "type": notification_type,
                    }
                )
                .execute()
            )

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


# ============== Event-driven Semantic Cache Invalidation ==============


@on(EventType.DOCUMENT_PROCESSED.value)
async def invalidate_cache_on_document_change(event: Event):
    """文档处理完成后，失效该租户的语义缓存（防止旧知识库数据被缓存吐出）。"""
    org_id = event.payload.get("org_id")
    if not org_id:
        return
    try:
        from app.services.semantic_cache import semantic_cache_service

        count = await semantic_cache_service.invalidate_by_org(org_id)
        logger.info(
            f"[EventBus] Semantic cache invalidated on document change: org={org_id}, deleted={count}"
        )
    except Exception as e:
        logger.warning(f"[EventBus] Semantic cache invalidation failed: {e}")


@on(EventType.CACHE_INVALIDATED.value)
async def handle_cache_invalidation(event: Event):
    """通用缓存失效事件处理器（供其他服务主动触发 emit('cache.invalidated', ...)）。

    payload 支持:
        org_id (str): 必需，要失效的租户 ID
        keywords (list[str]): 可选，靶向关键词（精准失效包含这些词的缓存）
    """
    org_id = event.payload.get("org_id")
    if not org_id:
        return
    try:
        from app.services.semantic_cache import semantic_cache_service

        keywords = event.payload.get("keywords", [])
        if keywords:
            count = await semantic_cache_service.invalidate_by_keywords(
                org_id, keywords
            )
        else:
            count = await semantic_cache_service.invalidate_by_org(org_id)
        logger.info(
            f"[EventBus] Cache invalidation handled: org={org_id}, keywords={keywords[:3] if keywords else 'all'}, deleted={count}"
        )
    except Exception as e:
        logger.warning(f"[EventBus] Cache invalidation handler failed: {e}")


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
        await supabase.rpc(
            "increment_user_bonus", {"p_user_id": user_id, "p_amount": bonus}
        ).execute()

        # Create incentive record
        await (
            supabase.table("incentives")
            .insert(
                {
                    "user_id": user_id,
                    "type": "bonus",
                    "amount": bonus,
                    "reason": f"成交奖励 (订单金额: ¥{deal_value})",
                    "status": "pending",
                }
            )
            .execute()
        )

        logger.info(f"Deal bonus calculated: ¥{bonus} for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to calculate deal bonus: {e}")


# ============== P0: EventBus → AutoTriggerService Bridge ==============


@on(EventType.DOCUMENT_UPLOADED.value)
async def bridge_document_upload(event: Event):
    """Forward document upload events to auto-trigger service."""
    try:
        from app.services.auto_trigger_service import auto_trigger_service

        await auto_trigger_service.process_event("document_uploaded", event.payload)
    except Exception as e:
        logger.error(f"[EventBridge] document_uploaded forward failed: {e}")


@on(EventType.PERFORMANCE_THRESHOLD_REACHED.value)
async def bridge_performance_threshold(event: Event):
    """Forward performance threshold events to auto-trigger data check."""
    try:
        from app.services.auto_trigger_service import auto_trigger_service

        await auto_trigger_service.check_data_trigger(event.payload)
    except Exception as e:
        logger.error(f"[EventBridge] performance threshold forward failed: {e}")


@on(EventType.AI_ERROR.value)
async def bridge_ai_error(event: Event):
    """Forward AI errors for data-based threshold alerting."""
    try:
        from app.services.auto_trigger_service import auto_trigger_service

        await auto_trigger_service.check_data_trigger(
            {"error_rate": event.payload.get("error_rate", 0)}
        )
    except Exception as e:
        logger.error(f"[EventBridge] AI error forward failed: {e}")


# ============== Cross-Module Data Workflow ==============
# These handlers wire the horizontal business flow:
# Lead → Analysis → Quote → Approval → Contract → Payment


@on(EventType.DEAL_WON.value)
async def auto_create_contract_from_deal(event: Event):
    """When a deal is won, auto-create a draft contract and notify finance."""
    from app.core.database import supabase

    if not supabase:
        return

    user_id = event.payload.get("user_id")
    customer_name = event.payload.get("customer_name", "")
    deal_value = event.payload.get("value", 0)
    deal_id = event.payload.get("deal_id")
    org_id = event.payload.get("org_id")

    if not user_id or not deal_value:
        return

    try:
        # Create draft contract linked to the deal
        contract_data = {
            "title": f"{customer_name} 合同",
            "party_a": customer_name,
            "amount": deal_value,
            "status": "draft",
            "created_by": user_id,
            "metadata": json.dumps({"source_deal_id": deal_id, "auto_generated": True}),
        }
        if org_id:
            contract_data["organization_id"] = org_id

        await supabase.table("contracts").insert(contract_data).execute()

        # Notify the sales rep
        await (
            supabase.table("notifications")
            .insert(
                {
                    "user_id": user_id,
                    "title": "合同已自动创建",
                    "content": f"客户「{customer_name}」的合同草稿已自动生成（金额: ¥{deal_value:,.0f}），请前往合同管理确认。",
                    "type": "info",
                    "action_url": "/contracts",
                }
            )
            .execute()
        )

        logger.info(
            f"[CrossModule] Auto-created contract from deal {deal_id} for {customer_name}"
        )
    except Exception as e:
        logger.error(f"[CrossModule] Failed to auto-create contract from deal: {e}")


@on(EventType.CONTRACT_SIGNED.value)
async def auto_create_invoice_from_contract(event: Event):
    """When a contract is signed, auto-create an invoice and notify finance team."""
    from app.core.database import supabase

    if not supabase:
        return

    contract_id = event.payload.get("contract_id")
    amount = event.payload.get("amount", 0)
    customer_name = event.payload.get("customer_name", "")
    org_id = event.payload.get("org_id")
    _user_id = event.payload.get("user_id")

    if not contract_id or not amount:
        return

    try:
        # Create invoice linked to contract
        invoice_data = {
            "contract_id": contract_id,
            "amount": amount,
            "status": "pending",
            "title": f"{customer_name} 应收款",
            "metadata": json.dumps({"auto_generated": True}),
        }
        if org_id:
            invoice_data["organization_id"] = org_id

        await supabase.table("payment_orders").insert(invoice_data).execute()

        # Notify finance team (founders and managers)
        finance_roles = (
            await supabase.table("users")
            .select("id")
            .in_("role", ["founder", "manager"])
            .execute()
        )
        for user in finance_roles.data or []:
            await (
                supabase.table("notifications")
                .insert(
                    {
                        "user_id": user["id"],
                        "title": "新应收款项待确认",
                        "content": f"客户「{customer_name}」合同已签署，应收金额 ¥{amount:,.0f}，请在财务中心确认。",
                        "type": "info",
                        "action_url": "/finance",
                    }
                )
                .execute()
            )

        logger.info(f"[CrossModule] Auto-created invoice from contract {contract_id}")
    except Exception as e:
        logger.error(f"[CrossModule] Failed to auto-create invoice from contract: {e}")


@on(EventType.LEAD_QUALIFIED.value)
async def auto_trigger_tender_analysis(event: Event):
    """When a lead is qualified (high-value), auto-suggest tender analysis."""
    from app.core.database import supabase

    if not supabase:
        return

    user_id = event.payload.get("user_id")
    lead_value = event.payload.get("estimated_value", 0)
    lead_name = event.payload.get("name", "")

    # Only trigger for high-value leads (> 100k)
    if not user_id or lead_value < 100_000:
        return

    try:
        await (
            supabase.table("notifications")
            .insert(
                {
                    "user_id": user_id,
                    "title": "建议发起招标分析",
                    "content": f"线索「{lead_name}」预估价值 ¥{lead_value:,.0f}，建议前往标书审阅进行竞争分析。",
                    "type": "info",
                    "action_url": "/sales",
                }
            )
            .execute()
        )

        logger.info(f"[CrossModule] Suggested tender analysis for lead {lead_name}")
    except Exception as e:
        logger.error(f"[CrossModule] Failed to suggest tender analysis: {e}")


@on(EventType.PAYMENT_RECEIVED.value)
async def update_sales_metrics_on_payment(event: Event):
    """When payment is received, update sales metrics and close the loop."""
    from app.core.database import supabase

    if not supabase:
        return

    user_id = event.payload.get("user_id")
    amount = event.payload.get("amount", 0)
    _org_id = event.payload.get("org_id")

    if not user_id or not amount:
        return

    try:
        # Update sales_metrics: increment revenue
        await supabase.rpc(
            "increment_user_bonus",
            {
                "p_user_id": user_id,
                "p_amount": amount * 0.003,  # 0.3% commission on payment
            },
        ).execute()

        # Notify the sales rep
        await (
            supabase.table("notifications")
            .insert(
                {
                    "user_id": user_id,
                    "title": "回款到账通知",
                    "content": f"客户回款 ¥{amount:,.0f} 已确认，佣金已自动计入您的奖励账户。",
                    "type": "success",
                    "action_url": "/finance",
                }
            )
            .execute()
        )

        logger.info(
            f"[CrossModule] Payment received ¥{amount} → metrics updated for user {user_id}"
        )
    except Exception as e:
        logger.error(f"[CrossModule] Failed to update metrics on payment: {e}")


@on(EventType.APPROVAL_APPROVED.value)
async def trigger_downstream_on_approval(event: Event):
    """When an approval is approved, trigger downstream actions based on type."""
    approval_type = event.payload.get("type", "")

    if approval_type == "contract":
        # Auto-emit contract signed event
        await emit(
            EventType.CONTRACT_SIGNED.value,
            payload=event.payload,
            user_id=event.user_id,
        )
    elif approval_type == "expense":
        # Notify finance for expense reimbursement
        from app.core.database import supabase

        if supabase:
            try:
                finance_users = (
                    await supabase.table("users")
                    .select("id")
                    .in_("role", ["founder"])
                    .execute()
                )
                for user in finance_users.data or []:
                    await (
                        supabase.table("notifications")
                        .insert(
                            {
                                "user_id": user["id"],
                                "title": "费用报销已审批",
                                "content": f"¥{event.payload.get('amount', 0):,.0f} 的报销申请已通过审批，请在财务中心处理打款。",
                                "type": "info",
                                "action_url": "/finance",
                            }
                        )
                        .execute()
                    )
            except Exception as e:
                logger.error(
                    f"[CrossModule] Failed to notify finance on expense approval: {e}"
                )
