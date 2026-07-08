"""Bounded loop engineering contracts for Nexus agents.

Loop engineering here means an external, reusable operating contract around an
agent task: trigger, goal, verifier, budget, stopping states, memory, and audit.
It is intentionally conservative. Loops must be bounded, cheap by default, and
verified by deterministic checks before any model judge or human review is used.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from app.services.agent_operational_hardening import (
    LOW_COST_DEFAULT_MODEL,
    enforce_model_policy,
)

LoopRiskLevel = Literal["low", "medium", "high"]
LoopTriggerType = Literal["manual", "schedule", "event", "ci_failure"]
LoopVerifierKind = Literal[
    "deterministic",
    "schema",
    "test_command",
    "business_rule",
    "llm_judge",
    "human_review",
]
LoopTerminalState = Literal[
    "success",
    "no_op",
    "blocked",
    "stalled",
    "exhausted",
    "unsafe",
]
LoopAutonomyMode = Literal["proposal_only", "low_risk_auto", "hitl_required"]

LOOP_TERMINAL_STATES: tuple[LoopTerminalState, ...] = (
    "success",
    "no_op",
    "blocked",
    "stalled",
    "exhausted",
    "unsafe",
)

LOOP_VERIFICATION_LADDER: tuple[LoopVerifierKind, ...] = (
    "deterministic",
    "schema",
    "test_command",
    "business_rule",
    "llm_judge",
    "human_review",
)

NON_LLM_VERIFIERS: tuple[LoopVerifierKind, ...] = (
    "deterministic",
    "schema",
    "test_command",
    "business_rule",
    "human_review",
)


@dataclass(frozen=True)
class LoopBudget:
    """Hard resource caps for one loop run."""

    max_iterations: int = 3
    max_tokens: int = 16000
    max_cost_usd: float = 0.12
    max_minutes: int = 12
    default_model: str = LOW_COST_DEFAULT_MODEL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LoopTrigger:
    """How a loop is started."""

    type: LoopTriggerType
    source: str
    condition: str
    debounce_minutes: int = 15

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LoopVerifier:
    """Verification contract for proving a loop outcome."""

    kind: LoopVerifierKind
    name: str
    command: str | None = None
    deterministic_tokens: tuple[str, ...] = ()
    required_artifacts: tuple[str, ...] = ()
    allow_llm_final_approval: bool = False

    def is_non_llm(self) -> bool:
        return self.kind in NON_LLM_VERIFIERS

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LoopMemory:
    """Small reusable memory snapshot carried between loop runs."""

    last_run_id: str | None = None
    last_terminal_state: LoopTerminalState | None = None
    learned_failures: tuple[str, ...] = ()
    checkpoint_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LoopSpec:
    """External LoopSpec: bounded goal + verifier + stop rules."""

    id: str
    name: str
    trigger: LoopTrigger
    goal: str
    verifier: LoopVerifier
    stop_states: tuple[LoopTerminalState, ...] = LOOP_TERMINAL_STATES
    budget: LoopBudget = field(default_factory=LoopBudget)
    memory: LoopMemory = field(default_factory=LoopMemory)
    tools: tuple[str, ...] = ()
    risk_level: LoopRiskLevel = "low"
    autonomy: LoopAutonomyMode = "proposal_only"
    default_model: str = LOW_COST_DEFAULT_MODEL
    requires_hitl: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "trigger": self.trigger.to_dict(),
            "goal": self.goal,
            "verifier": self.verifier.to_dict(),
            "stop_states": list(self.stop_states),
            "budget": self.budget.to_dict(),
            "memory": self.memory.to_dict(),
            "tools": list(self.tools),
            "risk_level": self.risk_level,
            "autonomy": self.autonomy,
            "default_model": self.default_model,
            "requires_hitl": self.requires_hitl,
        }


@dataclass(frozen=True)
class LoopRunAudit:
    """Audit packet emitted at the end of a loop run."""

    run_id: str
    spec_id: str
    terminal_state: LoopTerminalState
    iteration_count: int
    tokens_used: int
    cost_usd: float
    verifier_results: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    learned_failures: list[str] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    model: str = LOW_COST_DEFAULT_MODEL

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_loop_model(
    requested_model: str | None,
    *,
    source: str = "agent_loop",
    environment: str = "production",
) -> dict[str, Any]:
    """Apply the same low-cost model policy used by scheduled agent tasks."""

    return asdict(
        enforce_model_policy(
            requested_model,
            source=source,
            environment=environment,
        )
    )


def validate_loop_spec(spec: LoopSpec) -> dict[str, Any]:
    """Validate that a LoopSpec is bounded, verifiable, and cost-governed."""

    model_decision = resolve_loop_model(
        spec.default_model,
        source=f"loop_spec:{spec.id}",
    )
    checks = {
        "has_goal": bool(spec.goal.strip()),
        "has_bounded_budget": spec.budget.max_iterations > 0
        and spec.budget.max_tokens > 0
        and spec.budget.max_cost_usd > 0
        and spec.budget.max_minutes > 0,
        "has_named_terminal_states": set(LOOP_TERMINAL_STATES).issubset(
            set(spec.stop_states)
        ),
        "uses_low_cost_default_model": model_decision["resolved_model"]
        == LOW_COST_DEFAULT_MODEL,
        "has_non_llm_verifier": spec.verifier.is_non_llm()
        or bool(spec.verifier.deterministic_tokens),
        "llm_judge_cannot_final_approve": not spec.verifier.allow_llm_final_approval,
        "high_risk_requires_hitl": spec.risk_level != "high"
        or spec.requires_hitl
        or spec.autonomy == "hitl_required",
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "model_policy_decision": model_decision,
    }


def decide_terminal_state(
    *,
    verification_passed: bool,
    changed: bool,
    budget_exhausted: bool = False,
    unsafe: bool = False,
    blocked_reason: str | None = None,
    stalled: bool = False,
) -> LoopTerminalState:
    """Map verifier and runtime signals into one explicit terminal state."""

    if unsafe:
        return "unsafe"
    if budget_exhausted:
        return "exhausted"
    if blocked_reason:
        return "blocked"
    if stalled:
        return "stalled"
    if verification_passed and changed:
        return "success"
    if verification_passed and not changed:
        return "no_op"
    return "blocked"


def build_loop_run_audit(
    spec: LoopSpec,
    *,
    run_id: str,
    terminal_state: LoopTerminalState,
    iteration_count: int,
    tokens_used: int,
    cost_usd: float,
    verifier_results: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    learned_failures: list[str] | None = None,
) -> LoopRunAudit:
    """Create a durable audit packet for persistence in Agent Ops tables."""

    if iteration_count > spec.budget.max_iterations:
        terminal_state = "exhausted"
    if tokens_used > spec.budget.max_tokens or cost_usd > spec.budget.max_cost_usd:
        terminal_state = "exhausted"
    return LoopRunAudit(
        run_id=run_id,
        spec_id=spec.id,
        terminal_state=terminal_state,
        iteration_count=iteration_count,
        tokens_used=tokens_used,
        cost_usd=round(cost_usd, 6),
        verifier_results=verifier_results or [],
        actions=actions or [],
        learned_failures=learned_failures or [],
        model=spec.default_model,
    )


def _test_command_verifier(
    name: str,
    command: str,
    *,
    required_artifacts: tuple[str, ...] = (),
) -> LoopVerifier:
    return LoopVerifier(
        kind="test_command",
        name=name,
        command=command,
        required_artifacts=required_artifacts,
    )


def build_ci_self_repair_loop() -> LoopSpec:
    return LoopSpec(
        id="ci_self_repair_loop",
        name="CI self repair loop",
        trigger=LoopTrigger(
            type="ci_failure",
            source="github_actions",
            condition="quality_gate.status == failure",
            debounce_minutes=5,
        ),
        goal=(
            "Read failing CI logs, apply the smallest safe fix, run the matching "
            "test or static gate, and stop with a named terminal state."
        ),
        verifier=_test_command_verifier(
            "targeted_ci_gate",
            "scripts/run_last_mile_checks.ps1",
            required_artifacts=("ci_log_excerpt", "changed_files", "test_output"),
        ),
        tools=("read_ci_logs", "apply_patch", "targeted_test_runner"),
        risk_level="medium",
        autonomy="proposal_only",
    )


def build_agent_eval_regression_loop() -> LoopSpec:
    return LoopSpec(
        id="agent_eval_regression_loop",
        name="Agent eval regression loop",
        trigger=LoopTrigger(
            type="event",
            source="prompt_or_tool_change",
            condition="agent_prompt_versions.changed OR tool_schema.changed",
        ),
        goal=(
            "Run deterministic Agent eval baselines after prompt, tool, or context "
            "changes and block regressions before rollout."
        ),
        verifier=LoopVerifier(
            kind="business_rule",
            name="agent_eval_baseline_accuracy",
            deterministic_tokens=("accuracy", "case_count", "regression_count"),
            required_artifacts=("agent_eval_cases_200", "baseline_report"),
        ),
        tools=("agent_eval_baseline_service", "production_proof_gate"),
        risk_level="medium",
        autonomy="proposal_only",
    )


def build_llm_cost_governor_loop() -> LoopSpec:
    return LoopSpec(
        id="llm_cost_governor_loop",
        name="LLM cost governor loop",
        trigger=LoopTrigger(
            type="schedule",
            source="llm_call_log",
            condition="expensive_model_call.detected OR daily_llm_spend > budget",
        ),
        goal=(
            "Detect expensive model calls, attribute the source, downgrade to "
            "deepseek-v4-flash where allowed, and report unresolved leaks."
        ),
        verifier=LoopVerifier(
            kind="deterministic",
            name="low_cost_model_policy",
            deterministic_tokens=(
                "deepseek-v4-flash",
                "gemini-3.1-pro-preview",
                "force_low_cost_default",
            ),
            required_artifacts=("model_policy_decision", "cost_report"),
        ),
        budget=LoopBudget(max_iterations=2, max_tokens=8000, max_cost_usd=0.05),
        tools=("enforce_model_policy", "agent_cost_attribution"),
        risk_level="low",
        autonomy="low_risk_auto",
    )


def build_default_loop_specs() -> list[LoopSpec]:
    """Return the first three production-safe loops worth operationalizing."""

    return [
        build_ci_self_repair_loop(),
        build_agent_eval_regression_loop(),
        build_llm_cost_governor_loop(),
    ]


def get_loop_engineering_contract() -> dict[str, Any]:
    specs = build_default_loop_specs()
    validations = {spec.id: validate_loop_spec(spec) for spec in specs}
    return {
        "source": "bounded loop engineering for Nexus Agent Ops",
        "default_model": LOW_COST_DEFAULT_MODEL,
        "verification_ladder": list(LOOP_VERIFICATION_LADDER),
        "terminal_states": list(LOOP_TERMINAL_STATES),
        "default_loop_specs": [spec.to_dict() for spec in specs],
        "validations": validations,
        "audit_contract": {
            "records_input_goal": True,
            "records_actions": True,
            "records_verifier_results": True,
            "records_terminal_state": True,
            "records_tokens_and_cost": True,
            "records_learned_failures": True,
        },
        "guardrails": {
            "no_unbounded_loops": True,
            "model_judge_cannot_final_approve": True,
            "high_risk_requires_hitl": True,
            "default_low_cost_model": LOW_COST_DEFAULT_MODEL,
        },
    }


def validate_loop_engineering_contract() -> dict[str, Any]:
    contract = get_loop_engineering_contract()
    validations = contract["validations"]
    checks = {
        "has_loop_spec": len(contract["default_loop_specs"]) >= 3,
        "has_budget_fields": all(
            {"max_iterations", "max_tokens", "max_cost_usd", "max_minutes"}
            <= set(spec["budget"])
            for spec in contract["default_loop_specs"]
        ),
        "has_named_terminal_states": set(LOOP_TERMINAL_STATES).issubset(
            set(contract["terminal_states"])
        ),
        "has_non_llm_verifier": all(
            validation["checks"]["has_non_llm_verifier"]
            for validation in validations.values()
        ),
        "defaults_to_deepseek_v4_flash": contract["default_model"]
        == LOW_COST_DEFAULT_MODEL,
        "high_risk_operations_require_hitl": all(
            validation["checks"]["high_risk_requires_hitl"]
            for validation in validations.values()
        ),
        "audit_memory_contract": contract["audit_contract"]["records_learned_failures"]
        is True,
    }
    return {
        "passed": all(checks.values())
        and all(item["passed"] for item in validations.values()),
        "checks": checks,
        "loop_count": len(contract["default_loop_specs"]),
    }


class AgentLoopEngineeringService:
    """Small facade matching the repository's service object convention."""

    def get_contract(self) -> dict[str, Any]:
        return get_loop_engineering_contract()

    def validate_contract(self) -> dict[str, Any]:
        return validate_loop_engineering_contract()


agent_loop_engineering_service = AgentLoopEngineeringService()
