"""P1.1 Memory Visibility & RBAC (Role-Based Access Control).

Implements three-tier visibility model for multi-tenant memory isolation:
  - private:      Only the owning user can read/write (default)
  - team:         All members within the same organization can read
  - organization: All organization admins can read; members can read if tagged

Usage in retrieval:
    from .visibility import apply_visibility_filter

    query = apply_visibility_filter(query, user_id, org_id, user_role)
"""

import logging
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class MemoryVisibility(StrEnum):
    """Three-tier visibility levels for memory access control."""

    PRIVATE = "private"
    TEAM = "team"
    ORGANIZATION = "organization"


# Role hierarchy for RBAC checks (higher = more access)
_ROLE_HIERARCHY: dict[str, int] = {
    "employee": 1,
    "team_lead": 2,
    "manager": 3,
    "admin": 4,
    "super_admin": 5,
}


def get_role_level(role: str) -> int:
    """Get numeric access level for a role string."""
    return _ROLE_HIERARCHY.get(role.lower().strip(), 1)


def can_access_memory(
    memory_visibility: str,
    memory_user_id: str,
    memory_org_id: str | None,
    requesting_user_id: str,
    requesting_org_id: str | None,
    requesting_role: str = "employee",
) -> bool:
    """Check if a requesting user can access a specific memory.

    Args:
        memory_visibility: 'private', 'team', or 'organization'
        memory_user_id: Owner of the memory
        memory_org_id: Organization the memory belongs to
        requesting_user_id: User requesting access
        requesting_org_id: Organization of the requesting user
        requesting_role: Role of the requesting user

    Returns:
        True if access is allowed, False otherwise
    """
    # Owner always has access
    if requesting_user_id == memory_user_id:
        return True

    visibility = memory_visibility or "private"
    role_level = get_role_level(requesting_role)

    if visibility == MemoryVisibility.PRIVATE:
        # Private: only owner (already checked above)
        return False

    if visibility == MemoryVisibility.TEAM:
        # Team: same org members with team_lead+ or same org employees
        if requesting_org_id and memory_org_id and requesting_org_id == memory_org_id:
            return role_level >= get_role_level("employee")
        return False

    if visibility == MemoryVisibility.ORGANIZATION:
        # Organization: same org, manager+ role
        if requesting_org_id and memory_org_id and requesting_org_id == memory_org_id:
            return role_level >= get_role_level("manager")
        return False

    return False


def apply_visibility_filter(
    query: Any,
    user_id: str,
    org_id: str | None = None,
    user_role: str = "employee",
) -> Any:
    """Apply visibility-based filtering to a Supabase query.

    Strategy:
    - Always include the user's own memories (any visibility)
    - If org_id matches and role permits, include team/org-visible memories
    - This is an application-layer filter; DB-level RLS provides the second layer

    Args:
        query: Supabase query builder
        user_id: The requesting user's ID
        org_id: The requesting user's organization ID
        user_role: The requesting user's role

    Returns:
        Modified query with visibility filters applied
    """
    role_level = get_role_level(user_role)

    if not org_id:
        # No org context: only show user's own private memories
        query = query.eq("user_id", user_id)
        return query

    # Build OR filter for visibility-based access:
    # 1. User's own memories (regardless of visibility)
    # 2. Team-visible memories from same org (for all org members)
    # 3. Organization-visible memories (for manager+ roles)
    or_parts = [f"user_id.eq.{user_id}"]

    # Team visibility: any org member can see team-shared memories
    if role_level >= get_role_level("employee"):
        or_parts.append(f"and(organization_id.eq.{org_id},visibility.eq.team)")

    # Organization visibility: manager+ can see org-shared memories
    if role_level >= get_role_level("manager"):
        or_parts.append(f"and(organization_id.eq.{org_id},visibility.eq.organization)")

    query = query.or_(",".join(or_parts))
    return query


def determine_visibility(
    category: str,
    importance: float = 0.5,
    explicit_visibility: str | None = None,
) -> str:
    """Auto-determine the visibility level for a new memory.

    Rules:
    - Explicit override always wins
    - Organization-level knowledge (policy, document) → organization
    - High-importance facts → team
    - Everything else → private (default)

    Args:
        category: Memory category
        importance: Memory importance score
        explicit_visibility: User-specified visibility override

    Returns:
        Visibility string: 'private', 'team', or 'organization'
    """
    if explicit_visibility and explicit_visibility in (
        MemoryVisibility.PRIVATE,
        MemoryVisibility.TEAM,
        MemoryVisibility.ORGANIZATION,
    ):
        return explicit_visibility

    # Visibility is an authorization decision, never an importance decision.
    # Automatically extracted memories remain private unless the caller
    # explicitly requests a wider scope.
    return MemoryVisibility.PRIVATE
