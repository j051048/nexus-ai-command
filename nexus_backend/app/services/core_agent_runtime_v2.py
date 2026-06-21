"""Core Agent Runtime V2 contracts.

This module captures the runtime engineering lessons we want in Nexus:
streaming state transitions, lifecycle-aware tools, deferred tool schemas,
structured recovery, prompt section caching, context compression,
explainable permissions, and business skill runtime.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

TransitionReason = Literal[
    "user_prompt",
    "model_stream_started",
    "tool_use_detected",
    "tool_result_appended",
    "recovery_retry",
    "stop",
]


@dataclass(frozen=True)
class AgentRuntimeLoopState:
    messages_count: int = 0
    turn_count: int = 0
    transition_reason: TransitionReason = "user_prompt"
    tool_context: dict[str, Any] = field(default_factory=dict)
    compression_state: dict[str, Any] = field(
        default_factory=lambda: {
            "stage": "none",
            "last_quality_score": 100,
            "preserve_evidence_chain": True,
        }
    )
    recovery_attempts: dict[str, int] = field(default_factory=dict)
    pending_tool_summary: str | None = None


TOOL_LIFECYCLE_V2_STAGES = [
    "discover",
    "load_schema",
    "validate_input",
    "classify_risk",
    "check_permission",
    "pre_tool_hook",
    "execute",
    "post_tool_hook",
    "render_result",
    "summarize_for_context",
]

TOOL_LIFECYCLE_V2_POLICIES: list[dict[str, Any]] = [
    {
        "tool_type": "read_only",
        "concurrency": "parallel",
        "max_concurrency": 10,
        "requires_hitl": False,
        "examples": ["query_customers", "load_knowledge", "query_contracts"],
    },
    {
        "tool_type": "draft_only",
        "concurrency": "parallel",
        "max_concurrency": 5,
        "requires_hitl": False,
        "examples": ["draft_followup", "generate_visit_note", "fill_template"],
    },
    {
        "tool_type": "write",
        "concurrency": "serial",
        "max_concurrency": 1,
        "requires_hitl": True,
        "examples": ["submit_approval", "create_task", "update_contract"],
    },
    {
        "tool_type": "external",
        "concurrency": "serial",
        "max_concurrency": 1,
        "requires_hitl": True,
        "examples": ["send_email", "send_im_message", "sync_erp"],
    },
]

DEFERRED_TOOL_SCHEMA_POLICY: dict[str, Any] = {
    "initial_tool_budget": 12,
    "catalog_fields": ["name", "description", "risk_level", "tool_type", "search_hint"],
    "full_schema_loaded_by": "ToolSearch",
    "always_loaded_tools": [
        "ToolSearch",
        "ask_user",
        "compact_context",
        "query_action_inbox",
    ],
    "deferred_groups": [
        "crm_long_tail_tools",
        "approval_admin_tools",
        "document_export_tools",
        "erp_integration_tools",
    ],
}

AGENT_RECOVERY_POLICIES: list[dict[str, Any]] = [
    {
        "error": "prompt_too_long",
        "transition": "staged_compact_retry",
        "max_attempts": 2,
        "fallback": "auto_compact_then_retry",
    },
    {
        "error": "tool_timeout",
        "transition": "retry_or_degrade",
        "max_attempts": 2,
        "fallback": "return_safe_partial_result",
    },
    {
        "error": "expensive_model_selected",
        "transition": "force_deepseek_v4_flash",
        "max_attempts": 1,
        "fallback": "deny_expensive_model_call",
    },
    {
        "error": "permission_denied",
        "transition": "ask_user_or_suggest_safe_draft",
        "max_attempts": 1,
        "fallback": "draft_only_no_side_effect",
    },
    {
        "error": "stream_broken",
        "transition": "resume_from_last_event",
        "max_attempts": 3,
        "fallback": "replay_last_stable_state",
    },
    {
        "error": "tool_result_too_large",
        "transition": "summarize_result_then_continue",
        "max_attempts": 2,
        "fallback": "attach_result_summary_only",
    },
]

PROMPT_SECTION_REGISTRY: list[dict[str, Any]] = [
    {
        "key": "global_safety_rules",
        "cache_scope": "global",
        "boundary": "static",
        "includes": ["tool_protocol", "security_policy", "response_style"],
    },
    {
        "key": "tenant_business_context",
        "cache_scope": "tenant",
        "boundary": "dynamic",
        "includes": ["enabled_apps", "industry_knowledge", "field_prompt_policies"],
    },
    {
        "key": "session_memory",
        "cache_scope": "session",
        "boundary": "dynamic",
        "includes": ["user_preferences", "open_tasks", "recent_agent_state"],
    },
    {
        "key": "turn_page_context",
        "cache_scope": "turn",
        "boundary": "uncached",
        "includes": ["current_route", "selected_records", "latest_user_intent"],
    },
]

CONTEXT_COMPRESSION_PIPELINE: list[dict[str, Any]] = [
    {
        "stage": "snip",
        "trigger": "tool_result_over_budget",
        "preserve": ["tool_name", "record_ids", "decision", "errors"],
    },
    {
        "stage": "micro",
        "trigger": "repeated_business_context",
        "preserve": ["customer_summary", "contract_risk", "next_action"],
    },
    {
        "stage": "collapse",
        "trigger": "context_above_70_percent",
        "preserve": ["evidence_chain", "open_tasks", "hitl_decisions"],
    },
    {
        "stage": "auto_compact",
        "trigger": "context_above_90_percent",
        "preserve": ["goal", "completed_steps", "remaining_steps", "blocked_reason"],
    },
]

PERMISSION_DECISION_V2_OUTCOMES: list[dict[str, Any]] = [
    {
        "decision": "allow",
        "reason_type": "rule",
        "user_message": "已允许执行，操作会被记录到审计日志。",
        "safe_alternative": None,
    },
    {
        "decision": "ask",
        "reason_type": "hitl",
        "user_message": "该动作需要人工确认后才能继续。",
        "safe_alternative": "先生成草稿或风险说明，不直接提交。",
    },
    {
        "decision": "deny",
        "reason_type": "field_policy",
        "user_message": "该字段或动作不允许进入模型或外部系统。",
        "safe_alternative": "使用脱敏摘要或只读查询。",
    },
    {
        "decision": "passthrough",
        "reason_type": "hook",
        "user_message": "交由业务钩子继续处理。",
        "safe_alternative": "记录 hook 输出并等待下一步。",
    },
]

SKILL_RUNTIME_MANIFESTS: list[dict[str, Any]] = [
    {
        "key": "scientific_instrument_bid_support",
        "title": "科学仪器投标支持",
        "when_to_use": "用户上传招标文件、评分标准或要求生成技术响应时。",
        "context_mode": "fork",
        "default_model": "deepseek-v4-flash",
        "allowed_tools": ["parse_tender_document", "score_tender_response", "fill_template"],
        "hooks": ["BeforeToolUse", "AfterToolUse", "RunStop"],
    },
    {
        "key": "customer_churn_recovery",
        "title": "客户流失挽回",
        "when_to_use": "客户 30 天未跟进、健康分下降或进入流失风险区间时。",
        "context_mode": "inline",
        "default_model": "deepseek-v4-flash",
        "allowed_tools": ["score_customer_health", "draft_followup", "create_task"],
        "hooks": ["BeforeContextBuild", "AfterToolUse"],
    },
    {
        "key": "approval_risk_review",
        "title": "审批风控复核",
        "when_to_use": "审批金额异常、费用类别异常或命中合规规则时。",
        "context_mode": "fork",
        "default_model": "deepseek-v4-flash",
        "allowed_tools": ["approval_risk_review", "explain_policy"],
        "hooks": ["BeforeToolUse", "RunStop"],
    },
    {
        "key": "weekly_business_report",
        "title": "AI 周报生成",
        "when_to_use": "用户要求生成销售、审批、Agent 行为或业务价值周报时。",
        "context_mode": "inline",
        "default_model": "deepseek-v4-flash",
        "allowed_tools": ["generate_customer_360", "fill_template", "export_audit_packet"],
        "hooks": ["BeforeContextBuild", "RunStop"],
    },
]


def build_initial_agent_runtime_loop_state(
    *, messages_count: int = 0, turn_count: int = 0
) -> AgentRuntimeLoopState:
    return AgentRuntimeLoopState(
        messages_count=messages_count,
        turn_count=turn_count,
        transition_reason="user_prompt",
    )


def advance_agent_runtime_loop_state(
    state: AgentRuntimeLoopState,
    *,
    transition_reason: TransitionReason,
    messages_added: int = 0,
    pending_tool_summary: str | None = None,
) -> AgentRuntimeLoopState:
    return AgentRuntimeLoopState(
        messages_count=state.messages_count + messages_added,
        turn_count=state.turn_count + 1,
        transition_reason=transition_reason,
        tool_context=state.tool_context,
        compression_state=state.compression_state,
        recovery_attempts=state.recovery_attempts,
        pending_tool_summary=pending_tool_summary,
    )


def get_core_agent_runtime_v2() -> dict[str, Any]:
    state = build_initial_agent_runtime_loop_state()
    return {
        "source": "Claude Code style runtime engineering adapted for Nexus",
        "agent_runtime_loop": asdict(state),
        "tool_lifecycle_v2": {
            "stages": TOOL_LIFECYCLE_V2_STAGES,
            "policies": TOOL_LIFECYCLE_V2_POLICIES,
        },
        "deferred_tool_schema": DEFERRED_TOOL_SCHEMA_POLICY,
        "agent_recovery_policy": AGENT_RECOVERY_POLICIES,
        "prompt_section_registry": PROMPT_SECTION_REGISTRY,
        "context_compression_pipeline": CONTEXT_COMPRESSION_PIPELINE,
        "permission_decision_v2": PERMISSION_DECISION_V2_OUTCOMES,
        "skill_runtime": SKILL_RUNTIME_MANIFESTS,
        "summary": {
            "runtime_contracts": 8,
            "tool_lifecycle_stage_count": len(TOOL_LIFECYCLE_V2_STAGES),
            "recovery_policy_count": len(AGENT_RECOVERY_POLICIES),
            "prompt_section_count": len(PROMPT_SECTION_REGISTRY),
            "skill_count": len(SKILL_RUNTIME_MANIFESTS),
        },
    }


def validate_core_agent_runtime_v2() -> dict[str, Any]:
    checks = {
        "AgentRuntimeLoop": isinstance(build_initial_agent_runtime_loop_state(), AgentRuntimeLoopState),
        "ToolLifecycleV2": all(
            stage in TOOL_LIFECYCLE_V2_STAGES
            for stage in ["validate_input", "classify_risk", "check_permission", "summarize_for_context"]
        ),
        "DeferredToolSchema": DEFERRED_TOOL_SCHEMA_POLICY["full_schema_loaded_by"] == "ToolSearch",
        "AgentRecoveryPolicy": any(
            policy["transition"] == "force_deepseek_v4_flash" for policy in AGENT_RECOVERY_POLICIES
        ),
        "PromptSectionRegistry": {item["cache_scope"] for item in PROMPT_SECTION_REGISTRY}
        >= {"global", "tenant", "session", "turn"},
        "ContextCompressionPipeline": [item["stage"] for item in CONTEXT_COMPRESSION_PIPELINE]
        == ["snip", "micro", "collapse", "auto_compact"],
        "PermissionDecisionV2": {item["decision"] for item in PERMISSION_DECISION_V2_OUTCOMES}
        == {"allow", "ask", "deny", "passthrough"},
        "SkillRuntime": all(skill["default_model"] == "deepseek-v4-flash" for skill in SKILL_RUNTIME_MANIFESTS),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "runtime_contracts": len(checks),
    }
