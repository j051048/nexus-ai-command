import json
from pathlib import Path

from app.routers.llm.policy import PolicyUpdateRequest
from app.services.ai_execution_policy_service import (
    AIExecutionMode,
    AIExecutionPolicy,
    ExecutionStopReason,
    RiskLevel,
    assess_task,
    build_inference_receipt,
    check_step_budget,
    effective_policy_for_task,
    worker_registry,
)


def test_simple_mode_update_preserves_advanced_governance_fields():
    current = AIExecutionPolicy.for_mode("balanced")
    current.premium_model = "manual-premium-model"
    current.retain_inference_receipts = False
    current.high_risk_terms = ["custom-high-risk"]
    current.medium_risk_terms = ["custom-medium-risk"]

    updated = PolicyUpdateRequest(mode="economy").to_policy(current)

    assert updated.mode == AIExecutionMode.ECONOMY
    assert updated.max_calls == 1
    assert updated.premium_model == "manual-premium-model"
    assert updated.retain_inference_receipts is False
    assert updated.high_risk_terms == ["custom-high-risk"]
    assert updated.medium_risk_terms == ["custom-medium-risk"]


def test_mode_presets_bound_calls_cost_and_latency():
    economy = AIExecutionPolicy.for_mode("economy")
    balanced = AIExecutionPolicy.for_mode("balanced")
    strict = AIExecutionPolicy.for_mode("strict")

    assert [economy.max_calls, balanced.max_calls, strict.max_calls] == [1, 2, 3]
    assert (
        economy.max_task_cost_usd
        < balanced.max_task_cost_usd
        < strict.max_task_cost_usd
    )
    assert all(
        policy.primary_model == "deepseek-v4-flash"
        for policy in (economy, balanced, strict)
    )
    assert all(policy.premium_manual_only for policy in (economy, balanced, strict))


def test_deterministic_policy_dataset_has_perfect_route_accuracy():
    fixture = Path(__file__).parents[1] / "fixtures" / "ai_execution_policy_cases.json"
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    passed = 0

    for case in cases:
        policy = AIExecutionPolicy.for_mode(AIExecutionMode.BALANCED)
        policy.high_risk_terms = case.get("high_risk_terms", [])
        profile = assess_task(
            case["query"],
            complexity=case["complexity"],
            requires_tools=case["requires_tools"],
            scheduled=case.get("scheduled", False),
            policy=policy,
        )
        passed += (
            profile.risk_level.value == case["expected_risk"]
            and profile.execution_depth == case["expected_depth"]
        )

    assert passed / len(cases) >= 0.95


def test_high_risk_task_cannot_be_weakened_by_economy_mode():
    profile = assess_task("批准并支付这笔合同", requires_tools=True)
    policy = effective_policy_for_task(AIExecutionPolicy.for_mode("economy"), profile)

    assert profile.risk_level == RiskLevel.HIGH
    assert policy.mode == AIExecutionMode.STRICT
    assert policy.max_verifications == 1


def test_step_budget_blocks_before_overspend():
    policy = AIExecutionPolicy.for_mode("balanced")
    decision = check_step_budget(
        policy,
        calls_used=1,
        cost_used_usd=0.07,
        tokens_used=2_000,
        elapsed_ms=1_000,
        estimated_step_cost_usd=0.02,
    )

    assert decision.allowed is False
    assert decision.stop_reason == ExecutionStopReason.COST_BUDGET


def test_worker_registry_limits_tool_and_artifact_access():
    workers = {item.code: item for item in worker_registry()}

    assert workers["direct"].may_call_tools is True
    assert workers["critic"].may_call_tools is False
    assert "request" not in workers["critic"].readable_artifacts
    assert workers["verifier_editor"].max_calls == 1


def test_inference_receipt_hashes_answer_and_trace():
    policy = AIExecutionPolicy.for_mode("balanced")
    profile = assess_task("分析客户风险", requires_tools=True)
    receipt = build_inference_receipt(
        policy=policy,
        profile=profile,
        steps=["direct", "verifier_editor"],
        answer="建议优先跟进 A 客户",
        trace={"tool": "crm_search", "status": "success"},
        input_tokens=100,
        output_tokens=30,
        estimated_cost_usd=0.001,
        actual_cost_usd=0.0008,
        latency_ms=800,
    )

    assert len(receipt.answer_hash) == 64
    assert len(receipt.trace_hash) == 64
    assert receipt.actual_cost_usd < receipt.estimated_cost_usd
