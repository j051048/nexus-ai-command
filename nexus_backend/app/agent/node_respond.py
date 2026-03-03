"""
Graph Nodes: respond_node, error_node, _mask_sensitive_fields
"""

import re as _re

from langchain_core.messages import AIMessage, HumanMessage  # noqa: F401

from app.agent.node_helpers import (
    AgentConfig,
    AgentPhase,
    AgentState,
    ThinkingStep,
    logger,
    plugin_system_service,
    sanitize_output,
)
from app.services.plugin_system_service import ExtensionPoint


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPER: Role-based Sensitive Field Masking
# ═══════════════════════════════════════════════════════════════════════════════

# Sensitive field patterns with role access levels
# Only roles at or above the specified level can see unmasked values
_SENSITIVE_FIELD_RULES = [
    # (pattern, mask_replacement, minimum_role_level)
    # Role levels: guest=0, employee=1, manager=2, boss=3, founder=4
    (_re.compile(r"(薪[资酬水]|工资|月薪|年薪|底薪|基本工资)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[薪资信息已隐藏]", 3),
    (_re.compile(r"(提成|奖金|绩效奖|年终奖)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[奖金信息已隐藏]", 3),
    (_re.compile(r"(社保|公积金|五险一金)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[社保信息已隐藏]", 3),
    (_re.compile(r"(合同金额|签约金额|合同价)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[合同金额已隐藏]", 2),
    (_re.compile(r"(成本价|进货价|底价)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[成本信息已隐藏]", 2),
    (_re.compile(r"(利润率|毛利率|净利率)\s*[:：]?\s*[\d,.]+\s*%?"), "[利润信息已隐藏]", 2),
]

_ROLE_LEVELS = {
    "guest": 0,
    "employee": 1,
    "manager": 2,
    "boss": 3,
    "founder": 4,
}


def _mask_sensitive_fields(content: str, user_role: str) -> str:
    """
    P1 Security: Mask sensitive financial/HR fields based on user role.

    Higher-privilege roles see more data. Lower-privilege roles get
    sensitive fields replaced with '[已隐藏]' placeholders.
    """
    if not content or not user_role:
        return content

    current_level = _ROLE_LEVELS.get(user_role, 1)

    for pattern, replacement, min_level in _SENSITIVE_FIELD_RULES:
        if current_level < min_level:
            content = pattern.sub(replacement, content)

    return content


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: respond_node
# ═══════════════════════════════════════════════════════════════════════════════


async def respond_node(state: AgentState) -> dict:
    """
    Finalize output and format for UI.
    Includes role-based sensitive field masking for security.
    """
    final_response = state.get("final_response", "")

    if not final_response:
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content
                break

    # Final moderation filter
    final_response = sanitize_output(final_response)

    # P1 Security: Role-based sensitive field masking
    # Prevents lower-privilege users from seeing sensitive data
    # that may have been retrieved by RAG or tool calls
    config: AgentConfig = state["config"]
    final_response = _mask_sensitive_fields(final_response, config.user_role)

    return {
        "final_response": final_response or "抱歉，系统处理出现异常，请重试。",
        "current_phase": AgentPhase.DONE,
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.RESPONDING.value,
                content=f"思考路径完成，正在输出回复 (置信度: {state.get('confidence_score', 0.8):.0%})",
            )
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: error_node
# ═══════════════════════════════════════════════════════════════════════════════


async def error_node(state: AgentState) -> dict:
    """
    Global error handler with multi-level recovery.

    P1 Fix: 3-level recovery instead of single boolean flag:
      Level 0→1: Clear failed tools, ask LLM for alternative approach
      Level 1→2: Disable tools entirely, ask for best-effort text answer
      Level 2+:  Give up gracefully with user-facing message
    """
    error_msg = state.get("error", "未知错误")
    recovery_level = state.get("error_recovery_level", 0)
    iteration = state.get("iteration", 0)

    logger.error(f"[ErrorNode] Handling error: {error_msg} (level={recovery_level}, iter={iteration})")

    # P1 Plugin: ON_ERROR hook
    try:
        await plugin_system_service.run_hooks(
            ExtensionPoint.ON_ERROR,
            {"error": error_msg, "recovery_level": recovery_level, "iteration": iteration},
        )
    except Exception as e:
        logger.debug(f"[ErrorNode] ON_ERROR hook error: {e}")

    if recovery_level == 0 and iteration < 5:
        # Level 1: Clear failed tools, ask LLM to try alternative approach
        return {
            "error": None,
            "error_recovery_level": 1,
            "error_recovery_attempted": True,
            "pending_tool_calls": [],
            "current_phase": AgentPhase.PLANNING,
            "messages": [
                HumanMessage(content=f"[错误恢复L1] 前序操作失败: {error_msg}。请尝试一个不涉及此错误的替代方案。")
            ],
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.ERROR.value,
                    content=f"恢复L1: 切换方案以避免: {error_msg}",
                )
            ],
        }
    elif recovery_level == 1 and iteration < 5:
        # Level 2: Disable tools, ask for best-effort text answer
        return {
            "error": None,
            "error_recovery_level": 2,
            "pending_tool_calls": [],
            "requires_tools": False,
            "current_phase": AgentPhase.PLANNING,
            "messages": [
                HumanMessage(
                    content="[错误恢复L2] 工具调用持续失败。请不使用任何工具，基于已有信息给出最佳回答。如信息不足请如实说明。"
                )
            ],
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.ERROR.value,
                    content=f"恢复L2: 降级为纯文本模式: {error_msg}",
                )
            ],
        }

    # Level 3: Give up gracefully
    return {
        "final_response": f"⚠️ 系统执行过程中遇到了难以恢复的问题: {error_msg}。您可以尝试换一种说法再次提问。",
        "current_phase": AgentPhase.RESPONDING,
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.ERROR.value,
                content=f"❌ 遇到严重故障，停止执行: {error_msg}",
            )
        ],
    }
