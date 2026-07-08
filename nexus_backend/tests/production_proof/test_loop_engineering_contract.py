from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_bounded_loop_engineering_contract():
    service = read("nexus_backend/app/services/agent_loop_engineering_service.py")
    unit_tests = read("nexus_backend/tests/unit/test_agent_loop_engineering_service.py")

    for token in [
        "LoopSpec",
        "LoopBudget",
        "LoopVerifier",
        "LoopRunAudit",
        "success",
        "no_op",
        "blocked",
        "stalled",
        "exhausted",
        "unsafe",
    ]:
        assert token in service

    for token in [
        "max_iterations",
        "max_tokens",
        "max_cost_usd",
        "max_minutes",
        "deepseek-v4-flash",
        "gemini-3.1-pro-preview",
    ]:
        assert token in service

    for token in [
        "deterministic",
        "schema",
        "test_command",
        "business_rule",
        "llm_judge",
        "human_review",
        "model_judge_cannot_final_approve",
        "high_risk_requires_hitl",
    ]:
        assert token in service

    for token in [
        "ci_self_repair_loop",
        "agent_eval_regression_loop",
        "llm_cost_governor_loop",
        "records_learned_failures",
        "records_tokens_and_cost",
    ]:
        assert token in service

    assert "test_loop_engineering_contract_is_production_proof_ready" in unit_tests
