"""
Neuro-Symbolic Guard — deterministic policy checks before tool execution.

Pure rule-based (zero LLM calls, <1ms), provides hard guardrails that the
neural Agent layer cannot override.  Rules are loaded from:
  1. Settings thresholds (config.py)
  2. Approval flow definitions (Supabase, loaded lazily)

Returns a PolicyVerdict that the execute node uses to block, escalate, or
allow the tool call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verdict dataclass
# ---------------------------------------------------------------------------


@dataclass
class PolicyVerdict:
    """Result of a symbolic policy check."""

    allowed: bool = True
    reason: str = ""
    escalation: str | None = None      # "needs_approval" | "needs_manager" | None
    policy_name: str = ""              # which rule triggered


# ---------------------------------------------------------------------------
# Static financial rules (from settings thresholds)
# ---------------------------------------------------------------------------

# tool_name -> list of rule dicts
# Each rule: {field, max, reason_tpl, escalation, policy_name}
_FINANCIAL_RULES: dict[str, list[dict]] = {
    # 采购
    "create_purchase_order": [
        {
            "field": "amount",
            "max": settings.APPROVAL_PURCHASE_AUTO_LIMIT,
            "reason_tpl": "采购金额 {val} 超过自动审批限额 {limit}",
            "escalation": "needs_approval",
            "policy_name": "purchase_auto_limit",
        },
    ],
    "update_purchase_order": [
        {
            "field": "amount",
            "max": settings.APPROVAL_PURCHASE_AUTO_LIMIT * (1 + settings.APPROVAL_PURCHASE_OVERRUN_TOLERANCE),
            "reason_tpl": "采购金额 {val} 超过含超支容差的上限 {limit}",
            "escalation": "needs_approval",
            "policy_name": "purchase_overrun_limit",
        },
    ],
    # 费用报销
    "create_expense": [
        {
            "field": "amount",
            "max": settings.APPROVAL_EXPENSE_SMALL_LIMIT,
            "reason_tpl": "报销金额 {val} 超过免审限额 {limit}",
            "escalation": "needs_approval",
            "policy_name": "expense_small_limit",
        },
    ],
    "submit_expense": [
        {
            "field": "amount",
            "max": settings.APPROVAL_EXPENSE_SMALL_LIMIT,
            "reason_tpl": "报销金额 {val} 超过免审限额 {limit}",
            "escalation": "needs_approval",
            "policy_name": "expense_small_limit",
        },
    ],
    # 差旅
    "create_travel_request": [
        {
            "field": "daily_budget",
            "max": settings.APPROVAL_TRAVEL_DAILY_LIMIT,
            "reason_tpl": "差旅日预算 {val} 超过日限额 {limit}",
            "escalation": "needs_approval",
            "policy_name": "travel_daily_limit",
        },
    ],
}

# 需要管理员/主管角色的工具
_ROLE_RESTRICTED_TOOLS: dict[str, set[str]] = {
    "approve_request": {"manager", "admin", "boss", "director"},
    "reject_request": {"manager", "admin", "boss", "director"},
    "delete_employee": {"admin", "boss"},
    "update_salary": {"admin", "boss", "hr_manager"},
    "force_close_deal": {"manager", "admin", "boss"},
}


# ---------------------------------------------------------------------------
# Core check function
# ---------------------------------------------------------------------------


async def check_symbolic_policy(
    tool_name: str,
    tool_args: dict,
    user_role: str,
    org_id: str | None = None,
    db=None,
) -> PolicyVerdict:
    """
    Run deterministic policy checks against a tool call.

    Returns PolicyVerdict.allowed=True if the call is safe to proceed.
    This function is pure-rule, zero-LLM, <1ms.
    """
    # --- 1. Financial threshold checks ---
    rules = _FINANCIAL_RULES.get(tool_name)
    if rules:
        for rule in rules:
            val = _extract_numeric(tool_args, rule["field"])
            if val is not None and val > rule["max"]:
                reason = rule["reason_tpl"].format(val=val, limit=rule["max"])
                logger.info(
                    "[SymbolicGuard] BLOCKED %s: %s (org=%s)",
                    tool_name, reason, org_id,
                )
                return PolicyVerdict(
                    allowed=False,
                    reason=reason,
                    escalation=rule.get("escalation"),
                    policy_name=rule["policy_name"],
                )

    # --- 2. Role restriction checks ---
    allowed_roles = _ROLE_RESTRICTED_TOOLS.get(tool_name)
    if allowed_roles:
        role_lower = (user_role or "").lower()
        if role_lower not in allowed_roles:
            reason = f"角色 [{user_role}] 无权执行 [{tool_name}]，需要: {', '.join(sorted(allowed_roles))}"
            logger.info("[SymbolicGuard] BLOCKED %s: %s", tool_name, reason)
            return PolicyVerdict(
                allowed=False,
                reason=reason,
                escalation=None,
                policy_name="role_restriction",
            )

    # --- 3. Dynamic rules from auto_approval_rules (S3: #6) ---
    if org_id and db:
        from app.agent.approval_rule_engine import check_dynamic_rules

        dynamic_result = await check_dynamic_rules(
            tool_name=tool_name,
            tool_args=tool_args,
            org_id=org_id,
            db=db,
        )
        if dynamic_result:
            return PolicyVerdict(
                allowed=False,
                reason=dynamic_result["reason"],
                escalation=dynamic_result.get("escalation"),
                policy_name=dynamic_result["policy_name"],
            )

    return PolicyVerdict(allowed=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_numeric(args: dict, field: str) -> float | None:
    """Safely extract a numeric value from tool args."""
    val = args.get(field)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
