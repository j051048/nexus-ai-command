from app.services.agent_loop_engineering_service import (
    LOOP_TERMINAL_STATES,
    LOOP_VERIFICATION_LADDER,
    build_agent_eval_regression_loop,
    build_ci_self_repair_loop,
    build_default_loop_specs,
    build_llm_cost_governor_loop,
    build_loop_run_audit,
    decide_terminal_state,
    get_loop_engineering_contract,
    resolve_loop_model,
    validate_loop_engineering_contract,
    validate_loop_spec,
)


def test_default_loop_specs_cover_ci_eval_and_cost_governance():
    specs = build_default_loop_specs()
    ids = {spec.id for spec in specs}

    assert ids == {
        "ci_self_repair_loop",
        "agent_eval_regression_loop",
        "llm_cost_governor_loop",
    }
    assert set(LOOP_TERMINAL_STATES) == {
        "success",
        "no_op",
        "blocked",
        "stalled",
        "exhausted",
        "unsafe",
    }
    assert LOOP_VERIFICATION_LADDER[0] == "deterministic"
    assert LOOP_VERIFICATION_LADDER[-1] == "human_review"


def test_loop_spec_validation_requires_budget_non_llm_verifier_and_low_cost_model():
    for spec in [
        build_ci_self_repair_loop(),
        build_agent_eval_regression_loop(),
        build_llm_cost_governor_loop(),
    ]:
        result = validate_loop_spec(spec)

        assert result["passed"] is True
        assert result["checks"]["has_bounded_budget"] is True
        assert result["checks"]["has_non_llm_verifier"] is True
        assert result["checks"]["uses_low_cost_default_model"] is True
        assert result["checks"]["llm_judge_cannot_final_approve"] is True


def test_loop_model_policy_downgrades_expensive_models():
    decision = resolve_loop_model(
        "gemini-3.1-pro-preview",
        source="scheduled_loop",
        environment="production",
    )

    assert decision["resolved_model"] == "deepseek-v4-flash"
    assert decision["allowed"] is False


def test_terminal_state_mapping_is_explicit_and_budget_exhaustion_wins():
    assert decide_terminal_state(verification_passed=True, changed=True) == "success"
    assert decide_terminal_state(verification_passed=True, changed=False) == "no_op"
    assert (
        decide_terminal_state(
            verification_passed=True,
            changed=True,
            budget_exhausted=True,
        )
        == "exhausted"
    )
    assert (
        decide_terminal_state(
            verification_passed=False,
            changed=False,
            unsafe=True,
        )
        == "unsafe"
    )


def test_loop_run_audit_records_terminal_state_cost_and_learned_failures():
    spec = build_llm_cost_governor_loop()
    audit = build_loop_run_audit(
        spec,
        run_id="loop-run-1",
        terminal_state="success",
        iteration_count=1,
        tokens_used=1200,
        cost_usd=0.01,
        verifier_results=[{"name": "low_cost_model_policy", "passed": True}],
        actions=[{"type": "downgrade_model", "model": "deepseek-v4-flash"}],
        learned_failures=["scheduled_task_requested_gemini"],
    )

    data = audit.to_dict()

    assert data["run_id"] == "loop-run-1"
    assert data["terminal_state"] == "success"
    assert data["model"] == "deepseek-v4-flash"
    assert data["verifier_results"][0]["passed"] is True
    assert data["learned_failures"] == ["scheduled_task_requested_gemini"]


def test_loop_run_audit_forces_exhausted_when_budget_is_exceeded():
    spec = build_llm_cost_governor_loop()
    audit = build_loop_run_audit(
        spec,
        run_id="loop-run-2",
        terminal_state="success",
        iteration_count=99,
        tokens_used=1,
        cost_usd=0.01,
    )

    assert audit.terminal_state == "exhausted"


def test_loop_engineering_contract_is_production_proof_ready():
    contract = get_loop_engineering_contract()
    validation = validate_loop_engineering_contract()

    assert contract["default_model"] == "deepseek-v4-flash"
    assert contract["guardrails"]["model_judge_cannot_final_approve"] is True
    assert contract["audit_contract"]["records_tokens_and_cost"] is True
    assert validation["passed"] is True
    assert validation["loop_count"] == 3
