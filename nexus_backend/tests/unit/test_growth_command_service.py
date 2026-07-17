from datetime import UTC, datetime, timedelta

from app.services.growth_command_service import (
    GROWTH_COMMAND_SCHEMA_VERSION,
    compose_growth_workspace,
    growth_capability_registry,
)

NOW = datetime(2026, 7, 17, 8, 0, tzinfo=UTC)


def _workspace(**overrides):
    payload = {
        "clues": [],
        "tasks": [],
        "customers": [],
        "tenders": [],
        "action_events": [],
        "growth_outcomes": [],
        "now": NOW,
    }
    payload.update(overrides)
    return compose_growth_workspace(**payload)


def test_growth_workspace_is_empty_without_fabricated_business_data():
    result = _workspace()

    assert result["schema_version"] == GROWTH_COMMAND_SCHEMA_VERSION
    assert result["metrics"]["pipeline_value"] == 0
    assert result["actions"] == []
    assert result["signals"] == []
    assert result["review"]["estimated_hours_saved"] == 0


def test_growth_workspace_prioritizes_tender_deadline_and_stale_account():
    result = _workspace(
        customers=[
            {
                "id": "customer-1",
                "company": "精密实验室",
                "stage": "opportunity",
                "estimated_value": 680000,
                "updated_at": (NOW - timedelta(days=35)).isoformat(),
            }
        ],
        tenders=[
            {
                "id": "tender-1",
                "project_name": "高分辨质谱采购",
                "client_name": "精密实验室",
                "bid_deadline": (NOW + timedelta(days=2)).isoformat(),
                "estimated_value": 1200000,
                "compliance_status": "unchecked",
            }
        ],
    )

    assert result["metrics"]["high_priority_signals"] == 2
    assert result["signals"][0]["kind"] == "tender_risk"
    assert result["actions"][0]["execution_mode"] == "confirm"
    assert result["accounts"][0]["risk"] == "high"


def test_growth_workspace_tracks_action_adoption_and_task_value_separately():
    result = _workspace(
        tasks=[{"id": 1, "status": "done"}, {"id": 2, "status": "executing"}],
        action_events=[
            {"event_type": "accepted"},
            {"event_type": "completed"},
            {"event_type": "ignored"},
        ],
        growth_outcomes=[
            {
                "outcome_type": "qualified_lead",
                "evidence_ref": "crm://customer-1",
            },
            {
                "outcome_type": "revenue",
                "amount": 580000,
                "evidence_ref": "contract://contract-1",
            },
        ],
    )

    assert result["review"]["completed_growth_tasks"] == 1
    assert result["review"]["accepted_actions"] == 2
    assert result["review"]["action_adoption_rate"] == 66.7
    assert result["review"]["qualified_leads"] == 1
    assert result["review"]["attributed_revenue"] == 580000
    assert result["review"]["outcome_evidence_count"] == 2
    assert "估算" in result["review"]["evidence_note"]


def test_growth_capability_registry_exposes_versioned_extension_points():
    manifest = growth_capability_registry.manifest()
    keys = {item["key"] for item in manifest}

    assert "crm.accounts" in keys
    assert "connector.public-tender" in keys
    assert all(item["contract_version"] == "v1" for item in manifest)


def test_growth_workspace_projects_scientific_instrument_context():
    result = _workspace(
        clues=[
            {
                "id": "clue-ms-1",
                "title": "ICP-MS 更新采购",
                "status": "new",
                "instrument_line_code": "mass_spectrometry",
                "application_field": "环境痕量检测",
                "product_interest": ["ICP-MS 9000"],
                "priority": "high",
            }
        ],
        customers=[
            {
                "id": "customer-ms-1",
                "name": "环境监测中心",
                "stage": "opportunity",
                "instrument_line_code": "mass_spectrometry",
                "application_fields": ["重金属检测"],
            }
        ],
        tasks=[
            {
                "id": "task-ms-1",
                "status": "executing",
                "instrument_line_code": "mass_spectrometry",
            }
        ],
    )

    signal = result["signals"][0]
    assert signal["instrument_line_name"] == "质谱"
    assert signal["domain_context"]["classification_status"] == "classified"
    assert signal["product_models"] == ["ICP-MS 9000"]
    mass_spec = next(
        item
        for item in result["instrument_line_summary"]
        if item["code"] == "mass_spectrometry"
    )
    assert mass_spec == {
        "code": "mass_spectrometry",
        "name": "质谱",
        "signals": 1,
        "accounts": 1,
        "tenders": 0,
        "tasks": 1,
    }
    assert len(result["domain_catalog"]["instrument_lines"]) == 5
