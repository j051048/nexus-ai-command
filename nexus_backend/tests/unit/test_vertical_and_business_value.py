from app.services.business_value_service import summarize_business_value
from app.services.vertical_icp_validation_service import evaluate_vertical_readiness


def _evidence(kind: str, candidate: str, *, workflow: str = ""):
    return {
        "evidence_type": kind,
        "candidate_id": candidate,
        "artifact_ref": f"evidence/{kind}/{candidate}",
        "workflow_key": workflow,
    }


def test_vertical_gate_builds_pilot_only_from_repeated_evidence():
    rows = [_evidence("interview", f"c{i}") for i in range(8)]
    for workflow in ("calibration_and_maintenance", "service_operations"):
        rows.extend(
            _evidence("pain_point", f"c{i}", workflow=workflow) for i in range(3)
        )
    rows.extend([_evidence("design_partner", "d1"), _evidence("design_partner", "d2")])
    rows.extend(
        [_evidence("device_data_access", "d1"), _evidence("domain_expert", "e1")]
    )

    result = evaluate_vertical_readiness(rows)
    assert result["discovery_ready"] is True
    assert result["pilot_plan"]["eligible"] is True
    assert result["pilot_plan"]["selected_workflows"] == [
        "calibration_and_maintenance",
        "service_operations",
    ]


def test_business_value_separates_verified_from_estimated_value():
    result = summarize_business_value(
        completed_actions=2,
        accepted_actions=3,
        automated_followups=1,
        risk_reviews=1,
        events=[
            {
                "value_evidence_status": "verified",
                "minutes_saved": 30,
                "downtime_minutes_avoided": 60,
                "evidence_ref": "work-order/42",
            }
        ],
    )
    assert result["verified"]["saved_hours"] == 0.5
    assert result["verified"]["downtime_hours_avoided"] == 1.0
    assert result["verified"]["evidence_refs"] == ["work-order/42"]
    assert result["estimated"]["value_cny"] > 0
    assert (
        result["methodology"]["verified_and_estimated_are_reported_separately"] is True
    )
