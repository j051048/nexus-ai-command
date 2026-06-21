from app.services.enterprise_operating_foundation import (
    AI_SERVER_ACTIONS,
    BUSINESS_APP_MANIFESTS,
    DOCUMENT_TEMPLATE_CENTER,
    FIELD_PROMPT_POLICIES,
    build_nexus_execution_context,
    get_enterprise_operating_foundation,
    validate_enterprise_operating_foundation,
)


def test_nexus_execution_context_defaults_to_low_cost_model():
    context = build_nexus_execution_context(
        user_id="user-1",
        organization_id="org-1",
        role="employee",
    )

    assert context.default_llm_model == "deepseek-v4-flash"
    assert context.locale == "zh-CN"
    assert context.currency == "CNY"
    assert "crm" in context.allowed_apps


def test_business_app_manifests_are_operable_contracts():
    assert len(BUSINESS_APP_MANIFESTS) >= 5
    for manifest in BUSINESS_APP_MANIFESTS:
        assert manifest["routes"]
        assert manifest["apis"]
        assert manifest["tables"]
        assert manifest["agent_tools"]
        assert manifest["quality_gates"]


def test_ai_server_actions_have_batch_limits_and_hitl_for_high_risk():
    assert AI_SERVER_ACTIONS
    for action in AI_SERVER_ACTIONS:
        assert action["max_batch_size"] > 0
        assert action["audit_event"].startswith("ai_server_action.")
        if action["risk_level"] == "high":
            assert action["requires_hitl"] is True


def test_field_prompt_policies_block_sensitive_secrets():
    sensitive = {
        (policy["model"], policy["field"]): policy
        for policy in FIELD_PROMPT_POLICIES
        if policy["classification"] in {"credential", "financial_secret"}
    }

    assert sensitive
    assert all(policy["prompt_visibility"] == "blocked" for policy in sensitive.values())
    assert all(policy["masking"] == "never_send_to_llm" for policy in sensitive.values())


def test_document_template_center_has_exportable_templates():
    assert DOCUMENT_TEMPLATE_CENTER
    for template in DOCUMENT_TEMPLATE_CENTER:
        assert template["source_objects"]
        assert template["output_formats"]


def test_enterprise_operating_foundation_validation_passes():
    model = get_enterprise_operating_foundation(
        user_id="user-1",
        organization_id="org-1",
        role="boss",
    )
    result = validate_enterprise_operating_foundation()

    assert model["summary"]["default_llm_model"] == "deepseek-v4-flash"
    assert result["passed"] is True
    assert all(result["checks"].values())
