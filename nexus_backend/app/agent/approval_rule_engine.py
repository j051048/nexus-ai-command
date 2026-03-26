"""
S3 Approval Rule Engine — loads org-specific dynamic rules from Supabase.

Reads `auto_approval_rules` table and evaluates tool_args against configured
thresholds. Results feed into symbolic_guard.py as dynamic policy checks.

Cache: Rules are cached per org_id with a 5-minute TTL to avoid repeated
DB reads on every tool call.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# In-memory cache: org_id -> (rules_list, fetch_timestamp)
_ORG_RULES_CACHE: dict[str, tuple[list[dict], float]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes

# Map approval_type to tool_names that create/modify those entities
_TYPE_TO_TOOLS: dict[str, set[str]] = {
    "expense": {"create_expense", "submit_expense"},
    "leave": {"create_leave_request", "submit_leave_request"},
    "purchase": {"create_purchase_order", "update_purchase_order"},
    "travel": {"create_travel_request"},
    "contract": {"create_contract"},
    "overtime": {"create_overtime_request"},
}

# Reverse map: tool_name -> set of approval_types
_TOOL_TO_TYPES: dict[str, set[str]] = {}
for _type, _tools in _TYPE_TO_TOOLS.items():
    for _tool in _tools:
        _TOOL_TO_TYPES.setdefault(_tool, set()).add(_type)

# Comparison operators
_OPS = {
    "lte": lambda v, t: v <= t,
    "lt": lambda v, t: v < t,
    "gte": lambda v, t: v >= t,
    "gt": lambda v, t: v > t,
    "eq": lambda v, t: v == t,
}


async def _load_rules(org_id: str, db: Any = None) -> list[dict]:
    """Load active auto-approval rules for an org, with caching."""
    now = time.time()
    cached = _ORG_RULES_CACHE.get(org_id)
    if cached and (now - cached[1]) < _CACHE_TTL_SECONDS:
        return cached[0]

    try:
        from app.core.database import supabase
        client = db or supabase
        if not client:
            return []

        result = await (
            client.table("auto_approval_rules")
            .select("*")
            .eq("organization_id", org_id)
            .eq("is_active", True)
            .execute()
        )
        rules = result.data or []
        _ORG_RULES_CACHE[org_id] = (rules, now)
        if rules:
            logger.debug(f"[ApprovalRuleEngine] Loaded {len(rules)} rules for org {org_id}")
        return rules
    except Exception as e:
        logger.error(f"[ApprovalRuleEngine] Failed to load rules for org {org_id}: {e}")
        return []


async def check_dynamic_rules(
    tool_name: str,
    tool_args: dict,
    org_id: str,
    db: Any = None,
) -> dict | None:
    """Check tool call against org-specific dynamic approval rules.

    Returns None if no rule matches (tool call allowed).
    Returns a dict with {reason, escalation, policy_name} if a rule blocks.
    """
    # Quick check: does this tool type have any associated approval types?
    relevant_types = _TOOL_TO_TYPES.get(tool_name)
    if not relevant_types:
        return None

    rules = await _load_rules(org_id, db=db)
    if not rules:
        return None

    for rule in rules:
        approval_type = rule.get("approval_type", "")
        if approval_type not in relevant_types:
            continue

        field = rule.get("condition_field", "")
        op = rule.get("condition_op", "lte")
        threshold = float(rule.get("condition_value", 0))
        rule_name = rule.get("name", "unnamed_rule")

        # Extract field value from tool args
        val = tool_args.get(field)
        if val is None:
            continue
        try:
            val = float(val)
        except (ValueError, TypeError):
            continue

        # Check if value VIOLATES the auto-approval condition
        # auto_approval_rules define when auto-approval IS allowed (e.g., amount <= 5000)
        # So violation means: the condition is NOT met → needs manual approval
        op_fn = _OPS.get(op)
        if op_fn and not op_fn(val, threshold):
            reason = (
                f"[动态规则] {rule_name}: {field}={val} 不满足自动审批条件 "
                f"({field} {op} {threshold})"
            )
            logger.info(
                "[ApprovalRuleEngine] BLOCKED %s: %s (org=%s)",
                tool_name, reason, org_id,
            )
            return {
                "reason": reason,
                "escalation": "needs_approval",
                "policy_name": f"dynamic_rule:{rule_name}",
            }

    return None
