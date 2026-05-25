"""Unified action inbox API.

This endpoint is the first step toward an action-first product surface: pages,
mobile, and the AI copilot can all consume the same prioritized ActionItem list
instead of each UI stitching together approvals, notifications, CRM risks, and
system alerts independently.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inbox", tags=["Inbox"])

Priority = Literal["urgent", "high", "medium", "low"]
ActionKind = Literal["api", "navigate"]
ActionSource = Literal["approval", "notification", "crm", "system"]
ActionEventType = Literal[
    "viewed",
    "accepted",
    "completed",
    "ignored",
    "snoozed",
    "command_executed",
]

_PRIORITY_RANK: dict[Priority, int] = {
    "urgent": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


class ActionCommand(BaseModel):
    id: str
    label: str
    kind: ActionKind = "navigate"
    variant: Literal["primary", "secondary", "danger", "ghost"] = "secondary"
    method: str | None = None
    url: str | None = None
    payload: dict[str, Any] | None = None
    navigate_to: str | None = None


class ActionItem(BaseModel):
    id: str
    source: ActionSource
    source_id: str
    type: str
    title: str
    description: str | None = None
    reason: str | None = None
    priority: Priority = "medium"
    status: Literal["open", "done", "archived"] = "open"
    due_at: str | None = None
    created_at: str | None = None
    action_url: str | None = None
    actions: list[ActionCommand] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionEventRequest(BaseModel):
    action_id: str
    source: ActionSource
    source_id: str | None = None
    event_type: ActionEventType
    status: str = "recorded"
    comment: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _as_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    return str(value)


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _approval_to_action_item(item: dict[str, Any]) -> ActionItem:
    source_id = _as_text(item.get("id"))
    approval_type = _as_text(item.get("type"), "approval")
    submitter = _as_text(
        item.get("submitter_name")
        or item.get("requester_name")
        or item.get("submitted_by"),
        "未知提交人",
    )
    amount = item.get("amount")
    amount_text = f" ¥{amount:,.0f}" if isinstance(amount, (int, float)) else ""
    description = _as_text(
        item.get("description") or item.get("details") or item.get("reason"),
        "",
    )
    numeric_amount = float(amount) if isinstance(amount, (int, float)) else 0.0
    risk_flags: list[str] = []
    if numeric_amount >= 10000:
        risk_flags.append("金额超过 10,000 元，建议核对预算与发票依据")
    if not description:
        risk_flags.append("申请说明较少，审批前建议补充业务背景")
    title = f"{submitter} 的{approval_type}审批{amount_text}"
    return ActionItem(
        id=f"approval:{source_id}",
        source="approval",
        source_id=source_id,
        type=approval_type,
        title=title,
        description=description[:180] if description else None,
        reason="等待你处理的审批事项",
        priority="urgent" if numeric_amount >= 10000 else "high",
        created_at=item.get("created_at"),
        action_url="/approval",
        actions=[
            ActionCommand(
                id="reject",
                label="驳回",
                kind="api",
                variant="danger",
                method="POST",
                url=f"/api/approval/{source_id}/advance",
                payload={"decision": "rejected"},
            ),
            ActionCommand(
                id="approve",
                label="批准",
                kind="api",
                variant="primary",
                method="POST",
                url=f"/api/approval/{source_id}/advance",
                payload={"decision": "approved"},
            ),
            ActionCommand(
                id="view",
                label="查看",
                kind="navigate",
                navigate_to="/approval",
            ),
        ],
        metadata={
            "raw_type": approval_type,
            "amount": amount,
            "risk_score": min(100, 45 + len(risk_flags) * 20),
            "risk_flags": risk_flags,
            "evidence": [
                {"label": "提交人", "value": submitter},
                {"label": "审批类型", "value": approval_type},
                {"label": "金额", "value": amount_text.strip() or "未填写"},
                {"label": "说明", "value": description[:80] or "未填写"},
            ],
        },
    )


def _notification_to_action_item(item: dict[str, Any]) -> ActionItem:
    source_id = _as_text(item.get("id"))
    action_url = item.get("action_url") or "/inbox"
    notification_type = _as_text(item.get("type"), "notification")
    priority: Priority = (
        "high" if notification_type in {"error", "approval", "warning"} else "medium"
    )
    return ActionItem(
        id=f"notification:{source_id}",
        source="notification",
        source_id=source_id,
        type=notification_type,
        title=_as_text(item.get("title"), "未命名通知"),
        description=_as_text(item.get("content"), "")[:180] or None,
        reason="未读通知",
        priority=priority,
        created_at=item.get("created_at"),
        action_url=action_url,
        actions=[
            ActionCommand(
                id="mark_read",
                label="标记已读",
                kind="api",
                method="POST",
                url="/api/notifications/mark-read",
                payload={"notification_ids": [source_id]},
            ),
            ActionCommand(
                id="view",
                label="查看",
                kind="navigate",
                variant="primary",
                navigate_to=action_url,
            ),
        ],
        metadata={"is_read": bool(item.get("is_read"))},
    )


def _customer_risk_to_action_item(item: dict[str, Any]) -> ActionItem:
    source_id = _as_text(item.get("id"))
    name = _as_text(item.get("name"), "未命名客户")
    updated_at = item.get("updated_at") or item.get("created_at")
    updated_dt = _parse_datetime(updated_at)
    stale_days = (
        max(0, (datetime.now(timezone.utc) - updated_dt).days) if updated_dt else None
    )
    estimated_value = item.get("estimated_value")
    numeric_value = (
        float(estimated_value) if isinstance(estimated_value, (int, float)) else 0.0
    )
    stage = _as_text(item.get("stage"), "未标记")
    risk_breakdown = {
        "activity_recency": 80 if (stale_days or 0) >= 45 else 65,
        "stage_progression": 70 if stage not in {"customer", "closed", "lost"} else 20,
        "value_indicator": 75 if numeric_value >= 50000 else 45,
    }
    return ActionItem(
        id=f"crm-risk:{source_id}",
        source="crm",
        source_id=source_id,
        type="customer_followup_risk",
        title=f"{name} 需要跟进",
        description="客户长时间没有新的跟进记录，建议今天确认下一步。",
        reason=f"AI 规则：机会客户 {stale_days or 30} 天无更新",
        priority=(
            "high" if numeric_value >= 50000 or (stale_days or 0) >= 45 else "medium"
        ),
        created_at=updated_at,
        action_url=f"/crm?customer={source_id}",
        actions=[
            ActionCommand(
                id="follow_up",
                label="立即跟进",
                kind="navigate",
                variant="primary",
                navigate_to=f"/crm?customer={source_id}",
            ),
            ActionCommand(
                id="view_crm",
                label="客户详情",
                kind="navigate",
                navigate_to="/crm",
            ),
        ],
        metadata={
            "customer_name": name,
            "stage": item.get("stage"),
            "stale_days": stale_days,
            "estimated_value": estimated_value,
            "risk_breakdown": risk_breakdown,
            "risk_flags": [
                f"{stale_days or 30} 天未更新跟进",
                (
                    "高价值机会需优先确认下一步"
                    if numeric_value >= 50000
                    else "保持常规跟进节奏"
                ),
            ],
            "evidence": [
                {"label": "客户", "value": name},
                {"label": "阶段", "value": stage},
                {"label": "停滞天数", "value": f"{stale_days or 30} 天"},
                {
                    "label": "预计金额",
                    "value": f"¥{numeric_value:,.0f}" if numeric_value else "未填写",
                },
            ],
        },
    )


def _sort_actions(items: list[ActionItem]) -> list[ActionItem]:
    def key(item: ActionItem) -> tuple[int, str]:
        created = item.created_at or ""
        return (_PRIORITY_RANK[item.priority], created)

    return sorted(items, key=key)


async def _load_pending_approvals(client: Any, limit: int) -> list[ActionItem]:
    try:
        res = (
            await client.table("approval_requests")
            .select("*")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [_approval_to_action_item(item) for item in (res.data or [])]
    except Exception as exc:
        logger.warning("Inbox approval aggregation failed: %s", exc)
        return []


async def _load_unread_notifications(
    client: Any, user_id: str, limit: int
) -> list[ActionItem]:
    try:
        res = (
            await client.table("notifications")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [_notification_to_action_item(item) for item in (res.data or [])]
    except Exception as exc:
        logger.warning("Inbox notification aggregation failed: %s", exc)
        return []


async def _load_customer_risks(client: Any, limit: int) -> list[ActionItem]:
    try:
        stale_before = (
            (datetime.now(timezone.utc) - timedelta(days=30)).date().isoformat()
        )
        res = (
            await client.table("customers")
            .select("id,name,stage,estimated_value,updated_at,created_at")
            .neq("stage", "customer")
            .lt("updated_at", stale_before)
            .order("updated_at", desc=False)
            .limit(limit)
            .execute()
        )
        return [_customer_risk_to_action_item(item) for item in (res.data or [])]
    except Exception as exc:
        logger.warning("Inbox CRM risk aggregation failed: %s", exc)
        return []


@router.post("/actions/{action_id}/events")
async def record_action_event(
    action_id: str,
    payload: ActionEventRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """Persist user feedback and completion signals for action-first workflows."""
    if payload.action_id != action_id:
        raise api_error(ErrorCode.VALIDATION_ERROR, "行动项 ID 不一致")

    try:
        client = get_request_db(request)
        row = {
            "organization_id": org_id,
            "user_id": user_id,
            "action_id": payload.action_id,
            "source": payload.source,
            "source_id": payload.source_id,
            "event_type": payload.event_type,
            "status": payload.status,
            "comment": payload.comment,
            "metadata": payload.metadata,
        }
        res = await client.table("action_events").insert(row).execute()
        inserted = (res.data or [{}])[0]
        return api_success(data={"event": inserted, "recorded": True})
    except Exception as exc:
        logger.error("Inbox action event recording failed: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "行动事件记录失败")


@router.get("/actions")
async def list_action_items(
    request: Request,
    limit: int = Query(30, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
):
    """Return prioritized work actions across approvals, notifications, and CRM."""
    try:
        client = get_request_db(request)
        per_source_limit = max(5, min(limit, 50))
        items: list[ActionItem] = []
        items.extend(await _load_pending_approvals(client, per_source_limit))
        items.extend(
            await _load_unread_notifications(client, user_id, per_source_limit)
        )
        items.extend(await _load_customer_risks(client, per_source_limit))

        sorted_items = _sort_actions(items)[:limit]
        summary = {
            "total": len(sorted_items),
            "urgent": sum(1 for item in sorted_items if item.priority == "urgent"),
            "high": sum(1 for item in sorted_items if item.priority == "high"),
            "by_source": {
                "approval": sum(
                    1 for item in sorted_items if item.source == "approval"
                ),
                "notification": sum(
                    1 for item in sorted_items if item.source == "notification"
                ),
                "crm": sum(1 for item in sorted_items if item.source == "crm"),
                "system": sum(1 for item in sorted_items if item.source == "system"),
            },
        }
        return api_success(
            data={
                "items": [item.model_dump() for item in sorted_items],
                "summary": summary,
            }
        )
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise
        logger.error("Inbox action aggregation failed: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "行动项聚合失败")


@router.get("/analytics")
async def get_action_analytics(
    request: Request,
    days: int = Query(30, ge=1, le=180),
    limit: int = Query(500, ge=50, le=2000),
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """Return operating metrics for the unified action inbox."""
    try:
        client = get_request_db(request)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        since_iso = since.isoformat()

        events_res = (
            await client.table("action_events")
            .select("*")
            .eq("organization_id", org_id)
            .gte("created_at", since_iso)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        events = events_res.data or []
        event_counts = Counter(_as_text(event.get("event_type")) for event in events)
        source_counts: dict[str, Counter[str]] = defaultdict(Counter)
        actor_counts: Counter[str] = Counter()
        actor_event_counts: dict[str, Counter[str]] = defaultdict(Counter)
        daily_counts: dict[str, Counter[str]] = defaultdict(Counter)
        recent_events: list[dict[str, Any]] = []
        handled_action_ids: set[str] = set()

        for event in events:
            event_type = _as_text(event.get("event_type"), "unknown")
            source = _as_text(event.get("source"), "system")
            source_counts[source][event_type] += 1
            if event.get("user_id"):
                actor_id = _as_text(event.get("user_id"))
                actor_counts[actor_id] += 1
                actor_event_counts[actor_id][event_type] += 1
            created = _parse_datetime(event.get("created_at"))
            if created:
                daily_counts[created.date().isoformat()][event_type] += 1
            if event_type in {"accepted", "completed", "ignored", "command_executed"}:
                handled_action_ids.add(_as_text(event.get("action_id")))
            if len(recent_events) < 10:
                recent_events.append(
                    {
                        "id": event.get("id"),
                        "action_id": event.get("action_id"),
                        "source": source,
                        "event_type": event_type,
                        "created_at": event.get("created_at"),
                        "metadata": event.get("metadata") or {},
                    }
                )

        per_source = {
            source: {
                "total": sum(counter.values()),
                "accepted": counter.get("accepted", 0),
                "completed": counter.get("completed", 0),
                "ignored": counter.get("ignored", 0),
                "snoozed": counter.get("snoozed", 0),
                "command_executed": counter.get("command_executed", 0),
            }
            for source, counter in source_counts.items()
        }
        by_actor = [
            {
                "user_id": user_id_value,
                "total": sum(counter.values()),
                "accepted": counter.get("accepted", 0),
                "completed": counter.get("completed", 0)
                + counter.get("command_executed", 0),
                "ignored": counter.get("ignored", 0),
                "snoozed": counter.get("snoozed", 0),
            }
            for user_id_value, counter in actor_event_counts.items()
        ]
        by_actor.sort(key=lambda item: item["total"], reverse=True)
        daily_trend = [
            {
                "date": date,
                "total": sum(counter.values()),
                "accepted": counter.get("accepted", 0),
                "completed": counter.get("completed", 0)
                + counter.get("command_executed", 0),
                "ignored": counter.get("ignored", 0),
                "snoozed": counter.get("snoozed", 0),
            }
            for date, counter in sorted(daily_counts.items())
        ]

        open_actions = _sort_actions(
            [
                item
                for source_items in [
                    await _load_pending_approvals(client, 30),
                    await _load_unread_notifications(client, user_id, 30),
                    await _load_customer_risks(client, 30),
                ]
                for item in source_items
                if item.id not in handled_action_ids
            ]
        )
        stale_open = [
            item
            for item in open_actions
            if item.priority in {"urgent", "high"} or item.source == "crm"
        ][:10]

        total_events = len(events)
        accepted = event_counts.get("accepted", 0)
        completed = event_counts.get("completed", 0) + event_counts.get(
            "command_executed", 0
        )
        ignored = event_counts.get("ignored", 0)
        handled = accepted + completed + ignored
        actionable = max(1, handled + event_counts.get("snoozed", 0))

        return api_success(
            data={
                "window_days": days,
                "summary": {
                    "total_events": total_events,
                    "accepted": accepted,
                    "completed": completed,
                    "ignored": ignored,
                    "snoozed": event_counts.get("snoozed", 0),
                    "completion_rate": round(completed / actionable, 4),
                    "acceptance_rate": round(accepted / actionable, 4),
                    "ignored_rate": round(ignored / actionable, 4),
                    "open_high_risk": len(stale_open),
                    "unique_actors": len(actor_counts),
                },
                "by_source": per_source,
                "by_actor": by_actor[:10],
                "daily_trend": daily_trend,
                "stale_open_actions": [item.model_dump() for item in stale_open],
                "recent_events": recent_events,
            }
        )
    except Exception as exc:
        if hasattr(exc, "status_code"):
            raise
        logger.error("Inbox analytics failed: %s", exc)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "行动分析加载失败")
