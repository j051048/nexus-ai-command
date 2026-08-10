from app.services.artifact_generation_job_service import build_request_key, public_job
from app.services.artifact_output_eval_service import evaluate_artifact_output
from app.services.knowledge_readiness_service import build_knowledge_readiness
from app.services.scientific_instrument_ontology import normalize_product_specs
from app.services.tender_quality_service import evaluate_tender_workspace


def test_knowledge_readiness_explains_missing_categories():
    result = build_knowledge_readiness(
        [
            {
                "id": "doc-1",
                "name": "产品手册",
                "doc_type": "product",
                "status": "ready",
                "review_status": "verified",
                "quality_score": 0.9,
                "source_version": "2026.1",
            }
        ],
        product_count=1,
    )
    assert result["ready"] is False
    assert "competitor" in result["missing_categories"]
    assert result["next_actions"]


def test_parameter_ontology_keeps_source_and_flags_missing_unit():
    result = normalize_product_specs(
        "mass_spectrometry", {"质量精度": "2.5 ppm", "质量范围": "2000"}
    )
    assert result["normalized_specs"]["mass_accuracy"]["observed_unit"] == "ppm"
    assert any("质量范围缺少单位" in item for item in result["warnings"])


def test_tender_quality_fails_closed_on_blocked_mandatory_item():
    workspace = {
        "response_matrix": [
            {
                "category": "mandatory",
                "status": "blocked",
                "response": "",
                "evidence_ref": "",
                "owner": "",
            }
        ],
        "review_gates": [],
        "draft_sections": [],
    }
    result = evaluate_tender_workspace({}, workspace)
    assert result["decision"] == "no_bid"
    assert result["can_deliver"] is False
    assert result["no_go_reasons"]


def test_recorded_artifact_eval_requires_evidence_and_depth():
    result = evaluate_artifact_output(
        {
            "id": "case-1",
            "minimum_character_count": 20,
            "expected_sections": ["技术方案"],
            "required_terms": ["验收"],
            "forbidden_terms": ["绝对领先"],
        },
        {"content": "# 技术方案\n验收依据 [EVID:doc-1:chunk-1]，内容完整且可追溯。"},
    )
    assert result["passed"] is True


def test_artifact_job_request_key_is_idempotent_when_explicit():
    payload = {"request_key": "customer-delivery-42", "title": "技术方案"}
    request_key = build_request_key(
        organization_id="org-1", user_id="user-1", payload=payload
    )
    assert request_key == "customer-delivery-42"
    assert "request_key" not in payload


def test_artifact_job_public_contract_hides_request_and_builds_downloads():
    result = public_job(
        {
            "id": "job-1",
            "status": "completed",
            "stage": "completed",
            "progress": 100,
            "artifact_id": "artifact-1",
            "request_payload": {"sensitive_context": "internal"},
            "result_payload": {"requested_formats": ["docx", "pdf"]},
        }
    )
    assert "request_payload" not in result
    assert result["result"]["download_urls"] == {
        "docx": "/api/artifacts/artifact-1/download?format=docx",
        "pdf": "/api/artifacts/artifact-1/download?format=pdf",
    }
