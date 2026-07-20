import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.routers.solution_workspace_ops import (
    _is_unique_violation,
    _shape_approval_for_role,
)
from app.services.solution_connector_service import (
    _validate_url,
    prepare_solution_payload,
)
from app.services.solution_generation_policy import (
    compact_generation_context,
    generation_fingerprint,
)
from app.services.solution_learning_service import build_learning_insights
from app.services.solution_quality_eval_service import evaluate_solution
from app.services.solution_scenario_catalog import (
    get_scenario_pack,
    list_scenario_packs,
)
from app.services.solution_tender_service import build_tender_readiness


def _workspace():
    return {
        "requirements": [
            {
                "id": "r1",
                "title": "满足检出限",
                "priority": "must",
                "status": "verified",
                "evidence_ref": "手册 p12",
            }
        ],
        "packages": [
            {
                "id": "recommended",
                "product_models": ["LC-100"],
                "commercial": {
                    "list_price": 800_000,
                    "validation_errors": [],
                },
            }
        ],
        "sections": [
            {
                "id": "summary",
                "title": "摘要",
                "content": "依据产品手册配置 LC-100。",
                "evidence_refs": ["手册 p12"],
                "status": "approved",
            }
        ],
        "extension_data": {"commercial_validation": {"valid": True}},
    }


def test_quality_evaluator_passes_grounded_solution():
    result = evaluate_solution(_workspace())
    assert result["score"] == 100
    assert result["ready"] is True


def test_quality_evaluator_detects_unsupported_absolute_claim():
    workspace = _workspace()
    workspace["sections"][0]["content"] = "保证百分之百成功"
    workspace["sections"][0]["evidence_refs"] = []
    result = evaluate_solution(workspace)
    assert result["ready"] is False
    assert any(item["code"] == "unsupported_claim" for item in result["findings"])


def test_tender_readiness_produces_bid_decision_and_deviation_table():
    result = build_tender_readiness(
        {"budget_max": 1_000_000, "workspace": _workspace()}
    )
    assert result["decision"] == "bid"
    assert result["coverage_percent"] == 100
    assert result["deviations"] == []


def test_scenario_catalog_covers_five_lines_and_six_industries():
    packs = list_scenario_packs()
    assert len(packs) == 30
    assert get_scenario_pack("mass_spectrometry:制药")["required_facts"]


def test_generation_fingerprint_is_stable_and_context_is_bounded():
    products = [{"model_code": f"P-{index}", "revision": 1} for index in range(40)]
    evidence = [
        {"document_id": f"d-{index}", "excerpt": "x" * 2000, "score": 1}
        for index in range(12)
    ]
    compact_products, compact_evidence = compact_generation_context(products, evidence)
    first = generation_fingerprint({}, _workspace(), compact_products, compact_evidence)
    second = generation_fingerprint(
        {}, _workspace(), compact_products, compact_evidence
    )
    assert len(compact_products) == 30
    assert len(compact_evidence) <= 8
    assert sum(len(item["excerpt"]) for item in compact_evidence) <= 8000
    assert first == second


def test_learning_is_recommendation_only():
    insights = build_learning_insights(
        [{"status": "won", "instrument_line_code": "chromatography"}],
        [{"change_type": "edited", "section_id": "commercial"}],
    )
    assert insights["policy"] == "recommendation_only"
    assert insights["recommendations"][0]["auto_apply"] is False


def test_solution_connector_requires_capability_and_redacts_internal_costs():
    with pytest.raises(ValueError, match="未授权"):
        prepare_solution_payload({"capabilities": []}, {"workspace": {}})
    payload = prepare_solution_payload(
        {"capabilities": ["solution.delivery"]},
        {
            "workspace": {
                "packages": [
                    {
                        "commercial": {
                            "total": 120000,
                            "standard_cost": 80000,
                            "gross_margin_percent": 33.3,
                        }
                    }
                ]
            }
        },
    )
    commercial = payload["workspace"]["packages"][0]["commercial"]
    assert commercial == {"total": 120000}


def test_solution_connector_rejects_private_or_insecure_urls():
    with pytest.raises(ValueError, match="HTTPS"):
        _validate_url("http://example.com/hook")
    with pytest.raises(ValueError, match="内网"):
        _validate_url("https://127.0.0.1/hook")


def test_commercial_approval_hides_margin_from_ordinary_users():
    approval = {
        "id": "approval-1",
        "quote_snapshot": {
            "total": 120000,
            "gross_margin_percent": 33.3,
        },
    }
    employee_view = _shape_approval_for_role(approval, "employee")
    manager_view = _shape_approval_for_role(approval, "manager")
    assert employee_view["quote_snapshot"] == {"total": 120000}
    assert manager_view["quote_snapshot"]["gross_margin_percent"] == 33.3
    assert approval["quote_snapshot"]["gross_margin_percent"] == 33.3


def test_connector_delivery_recognizes_database_unique_violation():
    class UniqueViolationError(Exception):
        code = "23505"

    assert _is_unique_violation(UniqueViolationError("duplicate")) is True
    assert _is_unique_violation(RuntimeError("network error")) is False


def test_solution_quality_domain_dataset_is_a_blocking_regression_contract():
    dataset_path = (
        Path(__file__).resolve().parents[2]
        / "evals"
        / "datasets"
        / "solution_quality_cases.json"
    )
    cases = json.loads(dataset_path.read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 12
    for case in cases:
        workspace = deepcopy(_workspace())
        mutation = case.get("mutation")
        if mutation == "unsupported_claim":
            workspace["sections"][0].update(
                {"content": "保证百分之百达到目标", "evidence_refs": []}
            )
        elif mutation == "missing_evidence":
            workspace["requirements"][0].update(
                {"status": "open", "evidence_ref": None}
            )
        elif mutation == "commercial_invalid":
            workspace["extension_data"]["commercial_validation"] = {
                "valid": False,
                "errors": ["budget or currency mismatch"],
            }
        elif mutation == "compatibility_error":
            workspace["packages"][0]["commercial"]["validation_errors"] = [
                "unknown catalog model"
            ]
        result = evaluate_solution(workspace)
        assert result["ready"] is case["expected_ready"], case["id"]
