"""
S3 Approval Rule Engine — loads org-specific dynamic rules from Supabase.

Reads `auto_approval_rules` table and evaluates tool_args against configured
thresholds. Results feed into symbolic_guard.py as dynamic policy checks.

Cache: Rules are cached per org_id with a 5-minute TTL to avoid repeated
DB reads on every tool call.
"""

from __future__ import annotations

import logging
import threading
import time
from contextvars import ContextVar
from enum import StrEnum
from typing import Any


# ---------------------------------------------------------------------------
# Hermes-inspired three-tier approval scope
# ---------------------------------------------------------------------------


class ApprovalScope(StrEnum):
    """审批范围 — Hermes-inspired three-tier approval."""

    ONCE = "once"  # 仅本次操作
    SESSION = "session"  # 当前会话内同类操作自动通过
    PERMANENT = "permanent"  # 永久白名单（存入 DB）


_session_id_var: ContextVar[str] = ContextVar("approval_session_id", default="")


class SessionApprovalCache:
    """会话级审批缓存 — 同类操作在同一会话内只需确认一次。"""

    def __init__(self) -> None:
        self._cache: dict[str, set[str]] = {}  # session_id -> set of approved operation patterns
        self._lock = threading.Lock()

    def is_approved(self, session_id: str, operation_pattern: str) -> bool:
        """检查操作是否已在当前会话中被批准。"""
        with self._lock:
            return operation_pattern in self._cache.get(session_id, set())

    def approve(self, session_id: str, operation_pattern: str, scope: ApprovalScope) -> None:
        """记录审批决策。"""
        if scope == ApprovalScope.ONCE:
            return  # 单次审批不缓存

        if scope == ApprovalScope.PERMANENT:
            # 永久白名单 — 所有 session 都通过
            with self._lock:
                self._cache.setdefault("__permanent__", set()).add(operation_pattern)
            return

        with self._lock:
            if session_id not in self._cache:
                self._cache[session_id] = set()
            self._cache[session_id].add(operation_pattern)

    def is_permanently_approved(self, operation_pattern: str) -> bool:
        """检查是否在永久白名单中。"""
        with self._lock:
            return operation_pattern in self._cache.get("__permanent__", set())

    def clear_session(self, session_id: str) -> None:
        """清除会话缓存（会话结束时调用）。"""
        with self._lock:
            self._cache.pop(session_id, None)

    def _make_pattern(self, tool_name: str, action_type: str = "") -> str:
        """生成操作模式指纹。"""
        return f"{tool_name}:{action_type}" if action_type else tool_name


# 全局实例
session_approval_cache = SessionApprovalCache()

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
    # ---- 会话级缓存检查 (Hermes-style) ----
    action_type = tool_args.get("action_type", "")
    pattern = session_approval_cache._make_pattern(tool_name, action_type)
    session_id = _session_id_var.get("")
    if session_id and session_approval_cache.is_approved(session_id, pattern):
        logger.info(f"[Approval] Session-cached approval for {pattern}")
        return None  # 已在会话中批准，放行

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
            reason = f"[动态规则] {rule_name}: {field}={val} 不满足自动审批条件 " f"({field} {op} {threshold})"
            logger.info(
                "[ApprovalRuleEngine] BLOCKED %s: %s (org=%s)",
                tool_name,
                reason,
                org_id,
            )
            return {
                "reason": reason,
                "escalation": "needs_approval",
                "policy_name": f"dynamic_rule:{rule_name}",
            }

    return None
