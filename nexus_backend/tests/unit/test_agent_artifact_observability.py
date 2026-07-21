from app.routers.agent_observability import _summarize_artifact_quality


def test_artifact_quality_summary_exposes_readiness_repairs_and_failure_modes():
    summary = _summarize_artifact_quality(
        [
            {
                "artifact_type": "customer_solution",
                "score": 92,
                "ready": True,
                "evidence_count": 8,
                "repair_count": 1,
                "findings": [],
            },
            {
                "artifact_type": "customer_solution",
                "score": 68,
                "ready": False,
                "evidence_count": 2,
                "repair_count": 2,
                "findings": [
                    {"code": "evidence_insufficient"},
                    {"code": "citation_invalid"},
                ],
            },
            {
                "artifact_type": "tender",
                "score": 88,
                "ready": True,
                "evidence_count": 10,
                "repair_count": 0,
                "findings": [],
            },
        ]
    )

    assert summary["sample_size"] == 3
    assert summary["ready_rate"] == 0.6667
    assert summary["avg_score"] == 82.67
    assert summary["by_artifact_type"]["customer_solution"] == {
        "count": 2,
        "ready_rate": 0.5,
        "avg_score": 80.0,
    }
    assert summary["top_failure_codes"]["evidence_insufficient"] == 1
