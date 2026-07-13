"""Memory audit log — records every ADD / UPDATE / DELETE event.

Provides full traceability for memory changes, enabling:
- Understanding WHY a memory changed
- Rollback to previous versions
- Memory explainability for users
"""

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any, Literal

from app.core.database import supabase

logger = logging.getLogger(__name__)

ActionType = Literal[
    "ADD", "UPDATE", "DELETE", "PROMOTE", "MERGE", "RESOLVE_CONFLICT", "DECAY"
]


def _fingerprint(value: str | None) -> str | None:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None


async def log_memory_change(
    memory_id: str,
    user_id: str,
    action: ActionType,
    new_value: str | None = None,
    old_value: str | None = None,
    reason: str | None = None,
    actor: str = "system",
    db: Any = None,
    *,
    source: str | None = None,
    extraction_method: str | None = None,
    organization_id: str | None = None,
) -> bool:
    """记录一条记忆变更审计日志。

    Args:
        memory_id: 被操作的记忆 ID
        user_id: 所属用户
        action: ADD / UPDATE / DELETE / PROMOTE / MERGE / RESOLVE_CONFLICT / DECAY
        new_value: 变更后的值 (DELETE 时为 None)
        old_value: 变更前的值 (ADD 时为 None)
        reason: LLM 给出的变更原因（可选）
        actor: 操作来源，如 'system', 'user_explicit', 'conflict_resolution'
        db: 数据库客户端
        source: Provenance — where this memory came from (e.g. 'chat_session:abc123')
        extraction_method: How the memory was extracted ('regex', 'llm', 'user_explicit', 'consolidation')

    Returns:
        True if logged successfully, False otherwise (non-fatal)
    """
    client = db or supabase
    if not client:
        return False

    try:
        row = {
            "memory_id": memory_id,
            "user_id": user_id,
            "action": action,
            "old_value_hash": _fingerprint(old_value),
            "new_value_hash": _fingerprint(new_value),
            # Audit trails prove change without duplicating sensitive content.
            "old_value_preview": None,
            "new_value_preview": None,
            "reason": reason,
            "actor": actor,
            "created_at": datetime.now(UTC).isoformat(),
        }
        if organization_id:
            row["organization_id"] = organization_id
        if source:
            row["source"] = source
        if extraction_method:
            row["extraction_method"] = extraction_method
        await client.table("memory_audit_log").insert(row).execute()
        return True
    except Exception as e:
        # Audit logging is non-fatal — don't block the main operation
        err_str = str(e)
        if "memory_audit_log" in err_str and ("42P01" in err_str or "PGRST" in err_str):
            logger.debug("memory_audit_log table not yet created, skipping audit")
        else:
            logger.error(f"Failed to log memory audit: {e}")
        return False


async def get_memory_audit_trail(
    memory_id: str,
    user_id: str,
    limit: int = 20,
    db: Any = None,
) -> list[dict]:
    """获取某条记忆的完整变更历史。"""
    client = db or supabase
    if not client:
        return []

    try:
        result = (
            await client.table("memory_audit_log")
            .select("*")
            .eq("memory_id", memory_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to retrieve audit trail: {e}")
        return []


async def get_user_recent_changes(
    user_id: str,
    limit: int = 50,
    db: Any = None,
) -> list[dict]:
    """获取用户最近的记忆变更记录。"""
    client = db or supabase
    if not client:
        return []

    try:
        result = (
            await client.table("memory_audit_log")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to retrieve user changes: {e}")
        return []
