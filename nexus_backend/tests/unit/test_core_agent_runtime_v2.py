from app.services.core_agent_runtime_v2 import (
    AGENT_RECOVERY_POLICIES,
    CONTEXT_COMPRESSION_PIPELINE,
    DEFERRED_TOOL_SCHEMA_POLICY,
    PERMISSION_DECISION_V2_OUTCOMES,
    PROMPT_SECTION_REGISTRY,
    SKILL_RUNTIME_MANIFESTS,
    TOOL_LIFECYCLE_V2_STAGES,
    advance_agent_runtime_loop_state,
    build_initial_agent_runtime_loop_state,
    get_core_agent_runtime_v2,
    validate_core_agent_runtime_v2,
)


def test_agent_runtime_loop_tracks_transition_state():
    initial = build_initial_agent_runtime_loop_state(messages_count=1)
    next_state = advance_agent_runtime_loop_state(
        initial,
        transition_reason="tool_use_detected",
        messages_added=2,
        pending_tool_summary="query customers",
    )

    assert initial.transition_reason == "user_prompt"
    assert next_state.transition_reason == "tool_use_detected"
    assert next_state.messages_count == 3
    assert next_state.turn_count == 1
    assert next_state.pending_tool_summary == "query customers"


def test_tool_lifecycle_v2_contains_required_gates():
    for stage in [
        "validate_input",
        "classify_risk",
        "check_permission",
        "pre_tool_hook",
        "post_tool_hook",
        "summarize_for_context",
    ]:
        assert stage in TOOL_LIFECYCLE_V2_STAGES


def test_deferred_tool_schema_uses_tool_search():
    assert DEFERRED_TOOL_SCHEMA_POLICY["full_schema_loaded_by"] == "ToolSearch"
    assert DEFERRED_TOOL_SCHEMA_POLICY["initial_tool_budget"] <= 12


def test_recovery_policy_forces_low_cost_model():
    assert any(
        policy["transition"] == "force_deepseek_v4_flash"
        for policy in AGENT_RECOVERY_POLICIES
    )


def test_prompt_sections_have_cache_boundaries():
    scopes = {section["cache_scope"] for section in PROMPT_SECTION_REGISTRY}
    assert scopes >= {"global", "tenant", "session", "turn"}


def test_context_compression_pipeline_is_four_stage():
    assert [stage["stage"] for stage in CONTEXT_COMPRESSION_PIPELINE] == [
        "snip",
        "micro",
        "collapse",
        "auto_compact",
    ]


def test_permission_decision_v2_is_explainable():
    outcomes = {item["decision"] for item in PERMISSION_DECISION_V2_OUTCOMES}
    assert outcomes == {"allow", "ask", "deny", "passthrough"}
    assert all("reason_type" in item for item in PERMISSION_DECISION_V2_OUTCOMES)


def test_skill_runtime_uses_deepseek_flash_and_tool_allowlists():
    assert SKILL_RUNTIME_MANIFESTS
    for skill in SKILL_RUNTIME_MANIFESTS:
        assert skill["default_model"] == "deepseek-v4-flash"
        assert skill["allowed_tools"]


def test_core_agent_runtime_v2_validation_passes():
    model = get_core_agent_runtime_v2()
    result = validate_core_agent_runtime_v2()

    assert model["summary"]["runtime_contracts"] == 8
    assert result["passed"] is True
    assert all(result["checks"].values())
