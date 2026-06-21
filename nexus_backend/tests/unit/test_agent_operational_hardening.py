from dataclasses import asdict

from app.services.agent_operational_hardening import (
    AGENT_OPERATIONAL_HARDENING_AREAS,
    AGENT_REPLAY_BEHAVIOR_EVALS,
    AGENT_RUN_REPLAY_DEBUGGER_FIELDS,
    DEFERRED_TOOL_SCHEMA_RUNTIME,
    EXPENSIVE_MODEL_DENYLIST,
    LOW_COST_DEFAULT_MODEL,
    MEMORY_WRITE_GOVERNANCE,
    MODEL_POLICY_ENFORCER,
    PERMISSION_DECISION_EXPLAINABILITY,
    RUNTIME_V2_MAIN_CHAIN_ADOPTION,
    SKILL_RUNTIME_ACTIVATION_RULES,
    build_agent_run_replay_debugger_snapshot,
    enforce_model_policy,
    evaluate_compression_quality,
    explain_permission_decision,
    get_agent_operational_hardening,
    select_skill_for_message,
    validate_agent_operational_hardening,
)


def test_hardening_model_covers_ten_areas():
    model = get_agent_operational_hardening()
    result = validate_agent_operational_hardening()

    assert len(AGENT_OPERATIONAL_HARDENING_AREAS) == 10
    assert model["summary"]["hardening_area_count"] == 10
    assert result["passed"] is True
    assert all(result["checks"].values())


def test_model_policy_enforcer_downgrades_gemini_in_production():
    decision = enforce_model_policy(
        "gemini-3.1-pro-preview",
        source="scheduled_task",
        environment="production",
    )

    assert "gemini-3.1-pro-preview" in EXPENSIVE_MODEL_DENYLIST
    assert MODEL_POLICY_ENFORCER["default_model"] == LOW_COST_DEFAULT_MODEL
    assert decision.resolved_model == LOW_COST_DEFAULT_MODEL
    assert decision.allowed is False


def test_runtime_v2_main_chain_has_chat_graph_and_sse():
    chains = {item["chain"] for item in RUNTIME_V2_MAIN_CHAIN_ADOPTION}

    assert "/api/chat" in chains
    assert "LangGraph node_execute" in chains
    assert "SSE stream" in chains


def test_deferred_tool_schema_runtime_uses_tool_search():
    assert DEFERRED_TOOL_SCHEMA_RUNTIME["tool_search_contract"]["name"] == "ToolSearch"
    assert DEFERRED_TOOL_SCHEMA_RUNTIME["default_loaded_tool_count"] <= 12


def test_skill_runtime_auto_activation_selects_matching_skill():
    skill = select_skill_for_message("客户 30天未跟进，帮我生成挽回动作")

    assert skill is not None
    assert skill["skill"] == "customer_churn_recovery"
    assert SKILL_RUNTIME_ACTIVATION_RULES


def test_agent_replay_behavior_evals_have_expected_tools():
    for case in AGENT_REPLAY_BEHAVIOR_EVALS:
        assert case["expected_tools"]
        assert case["expected_policy"]


def test_context_compression_eval_detects_missing_evidence():
    result = evaluate_compression_quality(
        preserved_keys=["customer_id", "next_action"],
        required_keys=["customer_id", "next_action", "evidence_links"],
    )

    assert result["passed"] is False
    assert result["missing_required_keys"] == ["evidence_links"]


def test_memory_write_governance_denies_secrets():
    denied = {item["memory_type"] for item in MEMORY_WRITE_GOVERNANCE if item["write_policy"] == "deny"}

    assert "credential_or_secret" in denied
    assert "sensitive_personal_data" in denied


def test_permission_explainability_returns_safe_alternative():
    explanation = explain_permission_decision("deny")

    assert {item["decision"] for item in PERMISSION_DECISION_EXPLAINABILITY} == {
        "allow",
        "ask",
        "deny",
        "passthrough",
    }
    assert explanation["decision"] == "deny"
    assert explanation["safe_alternative"]


def test_agent_run_replay_debugger_snapshot_contains_black_box_fields():
    snapshot = build_agent_run_replay_debugger_snapshot(
        run_id="run-1",
        prompt_sections=["global_safety_rules"],
        selected_tools=["ToolSearch"],
        permission_decisions=["ask"],
    )
    model_decision = snapshot["model_policy_decisions"][0]

    assert set(AGENT_RUN_REPLAY_DEBUGGER_FIELDS) <= set(snapshot)
    assert snapshot["run_id"] == "run-1"
    assert asdict(enforce_model_policy(None, source="test"))["resolved_model"] == LOW_COST_DEFAULT_MODEL
    assert model_decision["resolved_model"] == LOW_COST_DEFAULT_MODEL
