"""
Safety Guards — Irreversible tool detection, mutation fast-path, SLO checks,
and three-tier approval scope (once / session / permanent).

Extracted from graph.py for modularity.

Guards:
  G1: Irreversible tools (financial approvals, destructive ops) must always
      go through Critic review — never take a fast path.
  SLO: Dynamic time-budget checks per complexity level.
  G2: Three-tier approval scope — 借鉴 Hermes Agent 设计:
      - once:      每次确认
      - session:   会话级自动通过
      - permanent: 永久白名单
"""

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.state import AgentState

from app.agent.approval_rule_engine import ApprovalScope, SessionApprovalCache
from app.agent.state import QueryComplexity
from app.tools import get_tool

logger = logging.getLogger(__name__)

# ── G2: 操作类型到默认审批范围的映射 ──
_OPERATION_APPROVAL_SCOPE: dict[str, ApprovalScope] = {
    # 查询类 — 永久白名单（只读操作无风险）
    "query": ApprovalScope.PERMANENT,
    "search": ApprovalScope.PERMANENT,
    "list": ApprovalScope.PERMANENT,
    # 常规写操作 — 会话级（同类操作确认一次即可）
    "leave_request": ApprovalScope.SESSION,
    "expense_claim": ApprovalScope.SESSION,
    "attendance_update": ApprovalScope.SESSION,
    "task_update": ApprovalScope.SESSION,
    "send_notification": ApprovalScope.SESSION,
    # 高风险操作 — 每次确认
    "approval_action": ApprovalScope.ONCE,
    "financial_mutation": ApprovalScope.ONCE,
    "data_deletion": ApprovalScope.ONCE,
    "hr_sensitive": ApprovalScope.ONCE,
    "bulk_operation": ApprovalScope.ONCE,
}

# 全局审批缓存实例
_approval_cache = SessionApprovalCache()

# ── SLO thresholds (seconds) per complexity level ──
SLO_THRESHOLDS: dict[QueryComplexity, float] = {
    QueryComplexity.SIMPLE: 5.0,
    QueryComplexity.MODERATE: 10.0,
    QueryComplexity.COMPLEX: 20.0,
    QueryComplexity.CRITICAL: 30.0,
}


def has_irreversible_tool(state_or_dict: dict) -> bool:
    """
    Check if any completed tool call used an irreversible (high-risk) tool.

    G1: Irreversible tools (financial approvals, destructive ops, etc.) must
    always go through Critic review — they should NEVER take a fast path.
    """
    completed = state_or_dict.get("completed_tool_calls", [])
    for tc in completed:
        tool = get_tool(getattr(tc, "tool_name", "") or (tc.get("tool_name", "") if isinstance(tc, dict) else ""))
        if tool and tool.is_irreversible:
            return True
    return False


def is_mutation_fast_path(state_or_dict: dict) -> bool:
    """
    Check if all completed tool calls are successful mutations that can
    safely skip reflect+critic.

    Returns False (no fast path) when:
    - No completed tools
    - Any tool failed
    - Any tool is irreversible (G1: high-risk tools must go through Critic)
    """
    completed = state_or_dict.get("completed_tool_calls", [])
    if not completed:
        return False
    # G1: irreversible tools MUST go through Critic — never fast-path
    if has_irreversible_tool(state_or_dict):
        logger.info("[Graph] Irreversible tool detected, blocking mutation fast-path → forcing Critic review")
        return False
    for tc in completed:
        if getattr(tc, "status", None) != "success":
            return False
        tool = get_tool(getattr(tc, "tool_name", ""))
        if not tool:
            return False
    return True


def check_slo_budget(state: "AgentState", budget_ratio: float = 1.0) -> bool:
    """
    Check if the agent has exceeded its SLO time budget.

    Args:
        state: Current agent state
        budget_ratio: Fraction of the SLO budget to check against (e.g. 0.8 for 80%)

    Returns:
        True if SLO budget is exceeded, False otherwise.
    """
    wall_start = state.get("wall_clock_start")
    complexity = state.get("complexity")
    if not wall_start or not complexity:
        return False
    elapsed = time.time() - wall_start
    threshold = SLO_THRESHOLDS.get(complexity, 20.0) * budget_ratio
    if elapsed > threshold:
        logger.info(
            f"[SLO] Budget exceeded: {elapsed:.1f}s > {threshold:.1f}s "
            f"(complexity={complexity}, ratio={budget_ratio})"
        )
        return True
    return False


# ── G2: Three-tier approval helpers ──


def check_approval_needed(
    tool_name: str,
    tool_args: dict,
    session_id: str,
    operation_type: str | None = None,
) -> tuple[bool, ApprovalScope, str]:
    """检查操作是否需要审批。

    Returns:
        (needs_approval, scope, reason)
        - needs_approval: True 表示需要用户确认
        - scope: 审批范围
        - reason: 需要审批的原因描述
    """
    # 推断操作类型
    op_type = operation_type or _infer_operation_type(tool_name, tool_args)
    scope = _OPERATION_APPROVAL_SCOPE.get(op_type, ApprovalScope.ONCE)

    # 永久白名单 — 直接通过
    if scope == ApprovalScope.PERMANENT or _approval_cache.is_permanently_approved(op_type):
        return False, scope, ""

    # 会话级 — 检查是否已批准
    if scope == ApprovalScope.SESSION and _approval_cache.is_approved(session_id, op_type):
        logger.info(f"[ApprovalCache] Session-approved: {op_type} in {session_id[:8]}")
        return False, scope, ""

    # 需要审批
    reason = _build_approval_reason(tool_name, tool_args, op_type, scope)
    return True, scope, reason


def approve_operation(session_id: str, operation_type: str, scope: ApprovalScope):
    """记录用户的审批决定。"""
    _approval_cache.approve(session_id, operation_type, scope)
    logger.info(f"[ApprovalCache] Approved: {operation_type} (scope={scope.value}, session={session_id[:8]})")


def clear_session_approvals(session_id: str):
    """清除会话审批缓存（会话结束时调用）。"""
    _approval_cache.clear_session(session_id)


def _infer_operation_type(tool_name: str, tool_args: dict) -> str:
    """从工具名和参数推断操作类型。"""
    name_lower = tool_name.lower()

    # 查询类
    if any(kw in name_lower for kw in ("query", "search", "list", "get", "fetch", "查询", "搜索")):
        return "query"

    # 审批类
    if any(kw in name_lower for kw in ("approve", "reject", "审批")):
        return "approval_action"

    # 删除类
    if any(kw in name_lower for kw in ("delete", "remove", "删除")):
        return "data_deletion"

    # 财务类
    if any(kw in name_lower for kw in ("payment", "transfer", "reimburse", "付款", "转账", "报销")):
        return "financial_mutation"

    # 请假类
    if any(kw in name_lower for kw in ("leave", "请假")):
        return "leave_request"

    # 默认：会话级
    return "task_update"


def _build_approval_reason(tool_name: str, tool_args: dict, op_type: str, scope: ApprovalScope) -> str:
    """构建审批原因描述。"""
    scope_hint = {
        ApprovalScope.ONCE: "（每次操作都需确认）",
        ApprovalScope.SESSION: "（确认后本次会话内同类操作自动通过）",
        ApprovalScope.PERMANENT: "",
    }
    return f"操作 [{tool_name}] 需要您的确认{scope_hint.get(scope, '')}"
