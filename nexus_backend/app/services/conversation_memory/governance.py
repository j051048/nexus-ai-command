"""Lifecycle and authority checks applied after every memory retrieval strategy."""

from datetime import UTC, datetime
from typing import Any

from .visibility import can_access_memory

RULE_CATEGORIES = frozenset({"policy", "business_rule", "company_policy", "pricing_policy", "service_policy"})


def memory_is_current(memory: dict[str, Any], *, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    if memory.get("superseded_by") or memory.get("lifecycle_state", "active") not in {"active", "confirmed"}:
        return False
    for key in ("valid_until", "expires_at"):
        if not memory.get(key):
            continue
        try:
            deadline = datetime.fromisoformat(str(memory[key]).replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            if deadline <= now:
                return False
        except (TypeError, ValueError):
            return False
    if memory.get("category") in RULE_CATEGORIES:
        # Confirming a personal memory is not approval to publish company policy.
        return False
    return True


def filter_current_memories(memories: list[dict], *, user_id: str, org_id: str | None, user_role: str = "employee") -> list[dict]:
    return [memory for memory in memories if memory_is_current(memory) and can_access_memory(
        memory.get("visibility") or "private", str(memory.get("user_id") or ""),
        memory.get("organization_id"), user_id, org_id, user_role,
    )]
