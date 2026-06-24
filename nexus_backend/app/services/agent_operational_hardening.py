"""Agent operational hardening layer.

These contracts turn the Agent Runtime V2 design into rollout-ready controls:
main-chain adoption, lifecycle migration, low-cost model enforcement, replay
evaluation, memory write governance, permission explanations, and run debugging.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

LOW_COST_DEFAULT_MODEL = "deepseek-v4-flash"
EXPENSIVE_MODEL_DENYLIST = {
    "gemini-3.1-pro-preview",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    "gpt-5-pro",
}

AgentHardeningArea = Literal[
    "runtime_v2_main_chain",
    "tool_lifecycle_v2_rollout",
    "deferred_tool_schema_runtime",
    "model_policy_enforcer",
    "context_compression_eval",
    "skill_runtime_activation",
    "agent_replay_behavior_eval",
    "memory_write_governance",
    "permission_decision_explainability",
    "agent_run_replay_debugger",
]

AGENT_OPERATIONAL_HARDENING_AREAS: list[AgentHardeningArea] = [
    "runtime_v2_main_chain",
    "tool_lifecycle_v2_rollout",
    "deferred_tool_schema_runtime",
    "model_policy_enforcer",
    "context_compression_eval",
    "skill_runtime_activation",
    "agent_replay_behavior_eval",
    "memory_write_governance",
    "permission_decision_explainability",
    "agent_run_replay_debugger",
]

MODEL_POLICY_ENFORCER: dict[str, Any] = {
    "denylist": sorted(EXPENSIVE_MODEL_DENYLIST),
    "default_model": LOW_COST_DEFAULT_MODEL,
    "scheduled_tasks_policy": "force_low_cost_default",
    "production_fallback": "deny_expensive_model_call",
}


@dataclass(frozen=True)
class ModelPolicyDecision:
    requested_model: str | None
    resolved_model: str
    allowed: bool
    reason: str
    source: str
    enforcement: str = "force_low_cost_default"


RUNTIME_V2_MAIN_CHAIN_ADOPTION: list[dict[str, Any]] = [
    {
        "chain": "/api/chat",
        "entrypoint": "chat_service -> agent.graph",
        "required_fields": [
            "transition_reason",
            "compression_state",
            "recovery_attempts",
            "pending_tool_summary",
        ],
        "rollout_state": "contract_ready",
    },
    {
        "chain": "LangGraph node_execute",
        "entrypoint": "app.agent.node_execute",
        "required_fields": [
            "tool_lifecycle_stage",
            "permission_decision",
            "tool_summary",
        ],
        "rollout_state": "contract_ready",
    },
    {
        "chain": "SSE stream",
        "entrypoint": "app.agent.stream",
        "required_fields": [
            "runtime_transition_event",
            "resume_cursor",
            "last_stable_state",
        ],
        "rollout_state": "contract_ready",
    },
]

TOOL_LIFECYCLE_V2_ROLLOUT: list[dict[str, Any]] = [
    {
        "phase": "read_only_tools",
        "tool_types": ["read_only"],
        "strategy": "parallel execution with schema summary",
        "required_stages": [
            "validate_input",
            "check_permission",
            "summarize_for_context",
        ],
    },
    {
        "phase": "draft_tools",
        "tool_types": ["draft_only"],
        "strategy": "parallel draft generation with result renderer",
        "required_stages": ["classify_risk", "render_result", "summarize_for_context"],
    },
    {
        "phase": "write_tools",
        "tool_types": ["write", "external"],
        "strategy": "serial execution gated by HITL and audit event",
        "required_stages": [
            "classify_risk",
            "check_permission",
            "pre_tool_hook",
            "post_tool_hook",
        ],
    },
]

DEFERRED_TOOL_SCHEMA_RUNTIME: dict[str, Any] = {
    "default_loaded_tool_count": 12,
    "selection_inputs": [
        "user_intent",
        "current_route",
        "selected_records",
        "role",
        "enabled_apps",
    ],
    "tool_search_contract": {
        "name": "ToolSearch",
        "returns": ["name", "description", "input_schema", "risk_level", "tool_type"],
        "max_results": 8,
    },
    "success_metrics": [
        "tool_selection_accuracy",
        "prompt_token_reduction",
        "wrong_tool_rate",
    ],
}

CONTEXT_COMPRESSION_EVAL_CASES: list[dict[str, Any]] = [
    {
        "case": "long_customer_timeline",
        "compression_stage": "micro",
        "must_preserve": [
            "customer_id",
            "last_contact_date",
            "next_action",
            "evidence_links",
        ],
    },
    {
        "case": "large_tender_document",
        "compression_stage": "collapse",
        "must_preserve": ["score_rules", "technical_requirements", "risk_flags"],
    },
    {
        "case": "multi_step_approval",
        "compression_stage": "auto_compact",
        "must_preserve": [
            "approval_id",
            "decision_history",
            "hitl_status",
            "blocked_reason",
        ],
    },
]

SKILL_RUNTIME_ACTIVATION_RULES: list[dict[str, Any]] = [
    {
        "skill": "scientific_instrument_bid_support",
        "signals": ["tender", "bid", "招标", "投标", "评分矩阵"],
        "context_mode": "fork",
        "allowed_tools": [
            "parse_tender_document",
            "score_tender_response",
            "fill_template",
        ],
    },
    {
        "skill": "customer_churn_recovery",
        "signals": ["30天未跟进", "流失风险", "客户健康分下降", "followup"],
        "context_mode": "inline",
        "allowed_tools": ["score_customer_health", "draft_followup", "create_task"],
    },
    {
        "skill": "approval_risk_review",
        "signals": ["审批", "报销", "金额异常", "合规"],
        "context_mode": "fork",
        "allowed_tools": ["approval_risk_review", "explain_policy"],
    },
    {
        "skill": "weekly_business_report",
        "signals": ["周报", "业务价值", "Agent行为", "report"],
        "context_mode": "inline",
        "allowed_tools": [
            "generate_customer_360",
            "fill_template",
            "export_audit_packet",
        ],
    },
]

AGENT_REPLAY_BEHAVIOR_EVALS: list[dict[str, Any]] = [
    {
        "flow": "crm_followup_replay",
        "input": "查询 30 天未跟进客户并生成跟进计划",
        "expected_tools": ["score_customer_health", "draft_followup"],
        "expected_policy": "draft_only_or_low_risk_auto",
    },
    {
        "flow": "approval_risk_replay",
        "input": "审批 12000 元差旅报销并检查异常",
        "expected_tools": ["approval_risk_review", "explain_policy"],
        "expected_policy": "hitl_required",
    },
    {
        "flow": "tender_support_replay",
        "input": "根据招标文件生成评分矩阵和技术响应草稿",
        "expected_tools": [
            "parse_tender_document",
            "score_tender_response",
            "fill_template",
        ],
        "expected_policy": "human_review_before_export",
    },
]

MEMORY_WRITE_GOVERNANCE: list[dict[str, Any]] = [
    {
        "memory_type": "user_preference",
        "write_policy": "allow_with_source",
        "ttl_days": 365,
        "requires_confirmation": False,
    },
    {
        "memory_type": "business_fact",
        "write_policy": "allow_with_evidence",
        "ttl_days": 180,
        "requires_confirmation": False,
    },
    {
        "memory_type": "sensitive_personal_data",
        "write_policy": "deny",
        "ttl_days": 0,
        "requires_confirmation": True,
    },
    {
        "memory_type": "credential_or_secret",
        "write_policy": "deny",
        "ttl_days": 0,
        "requires_confirmation": True,
    },
]

PERMISSION_DECISION_EXPLAINABILITY: list[dict[str, Any]] = [
    {
        "decision": "allow",
        "visible_reason": "该操作符合角色权限、字段策略和当前工具风险等级。",
        "safe_alternative": None,
    },
    {
        "decision": "ask",
        "visible_reason": "该操作会产生业务副作用，需要人工确认后继续。",
        "safe_alternative": "先生成草稿或风险说明。",
    },
    {
        "decision": "deny",
        "visible_reason": "该操作命中了权限、字段或成本限制，已被阻止。",
        "safe_alternative": "改用只读查询、脱敏摘要或草稿模式。",
    },
    {
        "decision": "passthrough",
        "visible_reason": "该操作交由业务 Hook 或上游系统继续判定。",
        "safe_alternative": "等待 Hook 输出并保留审计记录。",
    },
]

AGENT_RUN_REPLAY_DEBUGGER_FIELDS = [
    "run_id",
    "prompt_sections",
    "selected_tools",
    "permission_decisions",
    "compression_events",
    "model_policy_decisions",
    "cost_estimate",
    "recovery_transitions",
    "final_answer",
]


def enforce_model_policy(
    requested_model: str | None,
    *,
    source: str,
    environment: str = "production",
) -> ModelPolicyDecision:
    normalized = (requested_model or "").strip()
    if environment == "production" and (
        not normalized
        or normalized in EXPENSIVE_MODEL_DENYLIST
        or "gemini" in normalized.lower()
    ):
        return ModelPolicyDecision(
            requested_model=requested_model,
            resolved_model=LOW_COST_DEFAULT_MODEL,
            allowed=normalized in {"", LOW_COST_DEFAULT_MODEL},
            reason="production model policy forces deepseek-v4-flash for agent and scheduled tasks",
            source=source,
        )
    if normalized != LOW_COST_DEFAULT_MODEL and environment == "production":
        return ModelPolicyDecision(
            requested_model=requested_model,
            resolved_model=LOW_COST_DEFAULT_MODEL,
            allowed=False,
            reason="non-allowlisted production model was downgraded",
            source=source,
        )
    return ModelPolicyDecision(
        requested_model=requested_model,
        resolved_model=normalized or LOW_COST_DEFAULT_MODEL,
        allowed=True,
        reason="model is allowed by policy",
        source=source,
    )


def select_skill_for_message(message: str) -> dict[str, Any] | None:
    lower = message.lower()
    for rule in SKILL_RUNTIME_ACTIVATION_RULES:
        if any(signal.lower() in lower for signal in rule["signals"]):
            return rule
    return None


def evaluate_compression_quality(
    preserved_keys: list[str], required_keys: list[str]
) -> dict[str, Any]:
    preserved = set(preserved_keys)
    required = set(required_keys)
    missing = sorted(required - preserved)
    score = (
        round((len(required) - len(missing)) / len(required), 4) if required else 1.0
    )
    return {
        "passed": score >= 0.9 and not missing,
        "quality_score": score,
        "missing_required_keys": missing,
    }


def explain_permission_decision(decision: str) -> dict[str, Any]:
    for item in PERMISSION_DECISION_EXPLAINABILITY:
        if item["decision"] == decision:
            return item
    return {
        "decision": "deny",
        "visible_reason": "未知权限判定，按安全默认拒绝。",
        "safe_alternative": "请使用只读查询或联系管理员。",
    }


def build_agent_run_replay_debugger_snapshot(
    *,
    run_id: str,
    prompt_sections: list[str] | None = None,
    selected_tools: list[str] | None = None,
    permission_decisions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "prompt_sections": prompt_sections or [],
        "selected_tools": selected_tools or [],
        "permission_decisions": [
            explain_permission_decision(decision)
            for decision in (permission_decisions or [])
        ],
        "compression_events": [],
        "model_policy_decisions": [
            asdict(enforce_model_policy(None, source="agent_run_replay_debugger"))
        ],
        "cost_estimate": {"model": LOW_COST_DEFAULT_MODEL, "estimated_usd": 0},
        "recovery_transitions": [],
        "final_answer": None,
    }


def get_agent_operational_hardening() -> dict[str, Any]:
    return {
        "source": "agent operational hardening rollout for Nexus",
        "low_cost_default_model": LOW_COST_DEFAULT_MODEL,
        "hardening_areas": AGENT_OPERATIONAL_HARDENING_AREAS,
        "runtime_v2_main_chain": RUNTIME_V2_MAIN_CHAIN_ADOPTION,
        "tool_lifecycle_v2_rollout": TOOL_LIFECYCLE_V2_ROLLOUT,
        "deferred_tool_schema_runtime": DEFERRED_TOOL_SCHEMA_RUNTIME,
        "model_policy_enforcer": MODEL_POLICY_ENFORCER,
        "context_compression_eval": CONTEXT_COMPRESSION_EVAL_CASES,
        "skill_runtime_activation": SKILL_RUNTIME_ACTIVATION_RULES,
        "agent_replay_behavior_eval": AGENT_REPLAY_BEHAVIOR_EVALS,
        "memory_write_governance": MEMORY_WRITE_GOVERNANCE,
        "permission_decision_explainability": PERMISSION_DECISION_EXPLAINABILITY,
        "agent_run_replay_debugger": AGENT_RUN_REPLAY_DEBUGGER_FIELDS,
        "summary": {
            "hardening_area_count": len(AGENT_OPERATIONAL_HARDENING_AREAS),
            "main_chain_count": len(RUNTIME_V2_MAIN_CHAIN_ADOPTION),
            "replay_eval_count": len(AGENT_REPLAY_BEHAVIOR_EVALS),
            "memory_policy_count": len(MEMORY_WRITE_GOVERNANCE),
        },
    }


def validate_agent_operational_hardening() -> dict[str, Any]:
    gemini_decision = enforce_model_policy(
        "gemini-3.1-pro-preview",
        source="scheduled_task",
        environment="production",
    )
    checks = {
        "runtime_v2_main_chain": len(RUNTIME_V2_MAIN_CHAIN_ADOPTION) >= 3,
        "tool_lifecycle_v2_rollout": all(
            "check_permission" in phase["required_stages"]
            or phase["tool_types"] == ["draft_only"]
            for phase in TOOL_LIFECYCLE_V2_ROLLOUT
        ),
        "deferred_tool_schema_runtime": DEFERRED_TOOL_SCHEMA_RUNTIME[
            "tool_search_contract"
        ]["name"]
        == "ToolSearch",
        "model_policy_enforcer": gemini_decision.resolved_model
        == LOW_COST_DEFAULT_MODEL
        and gemini_decision.allowed is False,
        "context_compression_eval": all(
            case["must_preserve"] for case in CONTEXT_COMPRESSION_EVAL_CASES
        ),
        "skill_runtime_activation": all(
            rule["allowed_tools"] for rule in SKILL_RUNTIME_ACTIVATION_RULES
        ),
        "agent_replay_behavior_eval": all(
            case["expected_tools"] for case in AGENT_REPLAY_BEHAVIOR_EVALS
        ),
        "memory_write_governance": all(
            policy["write_policy"] == "deny"
            for policy in MEMORY_WRITE_GOVERNANCE
            if policy["memory_type"]
            in {"sensitive_personal_data", "credential_or_secret"}
        ),
        "permission_decision_explainability": {
            item["decision"] for item in PERMISSION_DECISION_EXPLAINABILITY
        }
        == {"allow", "ask", "deny", "passthrough"},
        "agent_run_replay_debugger": set(AGENT_RUN_REPLAY_DEBUGGER_FIELDS)
        >= {
            "prompt_sections",
            "selected_tools",
            "permission_decisions",
            "model_policy_decisions",
        },
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "hardening_area_count": len(checks),
    }
