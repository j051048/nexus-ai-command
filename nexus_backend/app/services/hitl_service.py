"""
HITL Confirmation Persistence Service.

Persists blocked tool confirmation requests to DB so users can approve/reject
even after disconnecting from the SSE stream.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


async def persist_confirmation(
    *,
    org_id: str,
    user_id: str,
    session_id: str,
    thread_id: str,
    tool_name: str,
    tool_args: dict,
    tool_call_id: str,
    confirmation_type: str = "",
    message: str = "",
    ttl_hours: int = 24,
) -> dict | None:
    """Persist a blocked tool confirmation to the DB."""
    db = supabase
    if not db:
        return None
    try:
        expires_at = (datetime.now(UTC) + timedelta(hours=ttl_hours)).isoformat()
        row = {
            "organization_id": org_id,
            "user_id": user_id,
            "session_id": session_id,
            "thread_id": thread_id,
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_call_id": tool_call_id,
            "confirmation_type": confirmation_type,
            "message": message,
            "expires_at": expires_at,
        }
        result = await db.table("pending_confirmations").insert(row).execute()
        if result.data:
            saved = result.data[0] if isinstance(result.data, list) else result.data
            logger.info("[HITL] Persisted confirmation: tool=%s, user=%s", tool_name, user_id)
            return saved
    except Exception as e:
        logger.warning("[HITL] Failed to persist confirmation: %s", e)
    return None


async def get_pending_confirmations(
    user_id: str,
    org_id: str | None = None,
    db: Any = None,
) -> list[dict]:
    """Get all pending (non-expired) confirmations for a user."""
    client = db or supabase
    if not client:
        return []
    try:
        now = datetime.now(UTC).isoformat()
        query = (
            client.table("pending_confirmations")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "pending")
            .gte("expires_at", now)
            .order("created_at", desc=True)
            .limit(20)
        )
        if org_id:
            query = query.eq("organization_id", org_id)
        result = await query.execute()
        return result.data or []
    except Exception as e:
        logger.warning("[HITL] Failed to query confirmations: %s", e)
        return []


async def resolve_confirmation(
    confirmation_id: str,
    user_id: str,
    action: str,  # "approved" | "rejected"
    db: Any = None,
) -> bool:
    """Resolve (approve/reject) a pending confirmation."""
    client = db or supabase
    if not client:
        return False
    if action not in ("approved", "rejected"):
        return False
    try:
        result = (
            await client.table("pending_confirmations")
            .update({
                "status": action,
                "resolved_by": user_id,
                "resolved_at": datetime.now(UTC).isoformat(),
            })
            .eq("id", confirmation_id)
            .eq("user_id", user_id)
            .eq("status", "pending")
            .execute()
        )
        resolved = bool(result.data)
        if resolved:
            logger.info("[HITL] Confirmation %s %s by %s", confirmation_id, action, user_id)
        return resolved
    except Exception as e:
        logger.warning("[HITL] Failed to resolve confirmation: %s", e)
        return False
