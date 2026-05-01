"""
P0: Unified Tool RBAC — Single Authoritative Layer

All tool permission checks MUST go through this module.
Consolidates the previously scattered 5-layer RBAC into one clear system:

1. Role hierarchy — numeric level comparison (tool.required_role vs user role)
2. Deny-list — explicit tool name or prefix blocks per role
3. Allow-all by default — if not denied and role level sufficient, allow

Design principles:
- Default-allow with deny-list (not whitelist) to avoid blocking new tools
- Role hierarchy is the primary gate (BaseTool.required_role)
- Deny-list handles fine-grained restrictions (viewer can't write, etc.)
- No DB calls — role is already resolved by the time we check
"""

import logging

logger = logging.getLogger(__name__)

# ── Role Hierarchy ─────────────────────────────────────────────────────────
# Higher number = more privileges. Used for BaseTool.required_role comparison.
ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 1,
    "employee": 2,
    "sales": 3,
    "sales_rep": 3,
    "finance": 4,
    "manager": 5,
    "boss": 6,
    "founder": 6,
    "admin": 7,
    "ai_assistant": 99,  # System-level, not a user role
    "all": 0,  # No restriction
}

# ── Deny-List ──────────────────────────────────────────────────────────────
# Per-role tool restrictions. Supports exact names and prefix patterns (ending with *).
# This is the ONLY place to define per-role tool blocks.
ROLE_DENY_LIST: dict[str, list[str]] = {
    "viewer": [
        "create_*",
        "update_*",
        "delete_*",
        "remove_*",
        "insert_*",
        "upsert_*",
        "send_*",
        "approve_*",
        "reject_*",
        "assign_*",
        "transfer_*",
    ],
    "employee": [
        "delete_customer",
        "delete_contract",
        "delete_user",
        "approve_payment",
        "change_salary",
    ],
    "sales": [
        "delete_customer",
        "delete_contract",
        "delete_user",
        "approve_payment",
        "change_salary",
    ],
    "sales_rep": [
        "delete_customer",
        "delete_contract",
        "delete_user",
        "approve_payment",
        "change_salary",
    ],
    "finance": [
        "delete_invoice",
        "delete_payment",
        "delete_user",
        "change_salary",
    ],
    "manager": [
        "delete_user",
        "change_salary",
    ],
    # admin / boss / founder: no deny-list
}


def check_tool_access(
    user_role: str,
    tool_name: str,
    tool_required_role: str = "all",
) -> tuple[bool, str]:
    """
    Unified tool permission check. Called from node_execute.py.

    Args:
        user_role: The user's resolved role (from JWT → DB → middleware)
        tool_name: Name of the tool being invoked
        tool_required_role: The tool's declared required_role (from BaseTool.required_role)

    Returns:
        (allowed: bool, reason: str) — reason is empty if allowed
    """
    # 1. Role hierarchy check
    if tool_required_role not in ("all", "ai_assistant"):
        req_level = ROLE_HIERARCHY.get(tool_required_role, 1)
        user_level = ROLE_HIERARCHY.get(user_role, 1)
        if user_level < req_level:
            role_label = {
                "boss": "领导",
                "manager": "管理者",
                "admin": "管理员",
                "finance": "财务",
                "founder": "创始人",
            }.get(tool_required_role, tool_required_role)
            return (
                False,
                f"⛔ 权限不足: 工具 [{tool_name}] 需要{role_label}权限，"
                f"当前角色为 [{user_role}]。",
            )

    # 2. Deny-list check (exact match + prefix pattern)
    denied_patterns = ROLE_DENY_LIST.get(user_role, [])
    for pattern in denied_patterns:
        if pattern.endswith("*"):
            if tool_name.startswith(pattern[:-1]):
                return (
                    False,
                    f"⛔ 角色 [{user_role}] 无权调用写入类工具 [{tool_name}]。",
                )
        elif tool_name == pattern:
            return (
                False,
                f"⛔ 角色 [{user_role}] 被禁止使用工具 [{tool_name}]。",
            )

    # 3. Default: allow
    return True, ""


def get_denied_tools_for_role(user_role: str) -> list[str]:
    """Return the deny-list patterns for a given role. Used for tool schema filtering."""
    return ROLE_DENY_LIST.get(user_role, [])


def get_role_level(role: str) -> int:
    """Return the numeric privilege level for a role."""
    return ROLE_HIERARCHY.get(role, 1)
