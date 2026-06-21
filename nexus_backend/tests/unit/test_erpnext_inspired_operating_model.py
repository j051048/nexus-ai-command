from app.services.erpnext_inspired_operating_model import (
    BUSINESS_OBJECT_BLUEPRINTS,
    EVENT_HOOK_BLUEPRINTS,
    IMMUTABLE_LEDGER_STREAMS,
    MIGRATION_GOVERNANCE_RULES,
    ONBOARDING_DEMO_PACKS,
    PORTAL_EXPERIENCE_BLUEPRINTS,
    REPORT_PRINT_BLUEPRINTS,
    UNIFIED_WORKFLOW_BLUEPRINTS,
    get_erpnext_inspired_operating_model,
    validate_erpnext_inspired_operating_model,
)


def test_erpnext_inspired_model_covers_all_eight_capabilities():
    model = get_erpnext_inspired_operating_model()
    capability_keys = {item["key"] for item in model["capabilities"]}

    assert model["summary"]["capability_count"] == 8
    assert capability_keys == {
        "business_object_meta",
        "unified_workflow_state_machine",
        "immutable_business_ledger",
        "customer_supplier_portal",
        "event_hook_registry",
        "report_print_export_templates",
        "module_onboarding_demo_data",
        "migration_patch_governance",
    }


def test_erpnext_inspired_model_has_runtime_blueprints():
    assert BUSINESS_OBJECT_BLUEPRINTS
    assert UNIFIED_WORKFLOW_BLUEPRINTS
    assert IMMUTABLE_LEDGER_STREAMS
    assert PORTAL_EXPERIENCE_BLUEPRINTS
    assert EVENT_HOOK_BLUEPRINTS
    assert REPORT_PRINT_BLUEPRINTS
    assert ONBOARDING_DEMO_PACKS
    assert MIGRATION_GOVERNANCE_RULES


def test_erpnext_inspired_model_validation_passes():
    result = validate_erpnext_inspired_operating_model()

    assert result["passed"] is True
    assert result["missing_capabilities"] == []
    assert result["incomplete_capabilities"] == []
