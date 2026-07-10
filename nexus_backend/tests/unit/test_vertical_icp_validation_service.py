from app.services.vertical_icp_validation_service import evaluate_vertical_readiness


def _record(evidence_type, candidate_id, workflow_key=""):
    return {
        "evidence_type": evidence_type,
        "candidate_id": candidate_id,
        "workflow_key": workflow_key,
        "artifact_ref": f"evidence://{evidence_type}/{candidate_id}",
    }


def test_vertical_build_stays_blocked_without_real_evidence():
    result = evaluate_vertical_readiness([])
    assert result["discovery_ready"] is False
    assert result["decision"] == "continue_customer_discovery"


def test_discovery_and_commercial_gates_are_separate():
    rows = [_record("interview", f"candidate-{index}") for index in range(8)]
    for workflow in ("calibration_drift", "service_triage"):
        rows.extend(
            _record("pain_point", f"candidate-{index}", workflow) for index in range(3)
        )
    rows.extend(
        [
            _record("design_partner", "candidate-1"),
            _record("design_partner", "candidate-2"),
            _record("device_data_access", "candidate-1"),
            _record("domain_expert", "expert-1"),
        ]
    )

    discovery = evaluate_vertical_readiness(rows)
    assert discovery["discovery_ready"] is True
    assert discovery["commercial_ready"] is False

    commercial = evaluate_vertical_readiness(
        [*rows, _record("paid_pilot", "candidate-1")]
    )
    assert commercial["commercial_ready"] is True


def test_unreferenced_evidence_is_rejected():
    result = evaluate_vertical_readiness(
        [{"evidence_type": "interview", "candidate_id": "candidate-1"}]
    )
    assert result["invalid_records"] == 1
    assert result["counts"] == {}
