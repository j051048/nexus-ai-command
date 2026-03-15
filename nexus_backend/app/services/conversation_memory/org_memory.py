"""Organization-level memory operations."""

import logging
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


async def save_org_memory(
    org_id: str,
    category: str,
    key: str,
    value: str,
    user_id: str | None = None,
    metadata: dict | None = None,
    db: Any = None,
) -> dict | None:
    """Save an organization-level memory visible to all users in the tenant.

    Always uses the global admin client because org_memories RLS
    relies on a session variable (app.current_org_id) that PostgREST
    scoped clients do not set. Application-layer org_id filtering
    ensures tenant isolation.
    """
    if not supabase:
        return None
    try:
        record = {
            "organization_id": org_id,
            "scope": "organization",
            "category": category,
            "key": key,
            "value": value,
            "contributed_by": user_id,
            "metadata": metadata or {},
        }
        res = (
            await supabase.table("org_memories")
            .upsert(record, on_conflict="organization_id,category,key")
            .execute()
        )
        return res.data[0] if res.data else record
    except Exception as e:
        logger.error("Failed to save org memory: %s", e)
        return None


async def get_org_memories(
    org_id: str,
    category: str | None = None,
    limit: int = 50,
    db: Any = None,
) -> list[dict]:
    """Get organization-level memories. Uses admin client to bypass RLS."""
    if not supabase:
        return []
    try:
        query = (
            supabase.table("org_memories")
            .select("*")
            .eq("organization_id", org_id)
            .order("updated_at", desc=True)
            .limit(limit)
        )
        if category:
            query = query.eq("category", category)
        res = await query.execute()
        return res.data or []
    except Exception as e:
        logger.error("Failed to get org memories: %s", e)
        return []


async def search_org_memories(
    org_id: str,
    query: str,
    limit: int = 10,
    db: Any = None,
) -> list[dict]:
    """Search organization memories by keyword. Uses admin client to bypass RLS."""
    if not supabase:
        return []
    try:
        res = (
            await supabase.table("org_memories")
            .select("*")
            .eq("organization_id", org_id)
            .or_(f"key.ilike.%{query}%,value.ilike.%{query}%")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logger.error("Failed to search org memories: %s", e)
        return []


async def delete_org_memory(
    org_id: str,
    memory_id: str,
    db: Any = None,
) -> bool:
    """Delete a specific organization memory. Uses admin client to bypass RLS."""
    if not supabase:
        return False
    try:
        await supabase.table("org_memories").delete().eq("id", memory_id).eq("organization_id", org_id).execute()
        return True
    except Exception as e:
        if hasattr(e, "code") and str(getattr(e, "code", "")) == "204":
            return True
        logger.error("Failed to delete org memory: %s", e)
        return False


async def build_org_memory_context(
    org_id: str,
    query: str | None = None,
    db: Any = None,
) -> str:
    """Build organization memory context string for injection into system prompt.

    Strategy:
    - policy: always inject (behavioral rules, must be obeyed)
    - preference/knowledge: only inject query-relevant ones via search
    """
    if not org_id:
        return ""

    parts: list[str] = []

    # Always inject org behavior policies (highest priority, query-independent)
    policies = await get_org_memories(org_id, category="policy", limit=10, db=db)
    if policies:
        parts.append("## 组织行为准则（必须遵守）")
        for m in policies:
            parts.append(f"- {m['key']}: {m['value']}")

    # Search for query-relevant org memories (preference/knowledge/etc.)
    if query:
        relevant = await search_org_memories(org_id, query, limit=5, db=db)
        existing_keys = {m["key"] for m in policies}
        relevant = [m for m in relevant if m["key"] not in existing_keys]
        if relevant:
            parts.append("## 相关组织记忆")
            for m in relevant:
                parts.append(f"- [{m['category']}] {m['key']}: {m['value']}")

    return "\n".join(parts)
