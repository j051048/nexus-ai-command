from app.agent.artifact_contract import ArtifactAudience, ArtifactSpec, ArtifactType
from app.services.artifact_llm_judge import (
    LLM_JUDGE_DIMENSIONS,
    combine_rule_and_llm,
    evaluate_delivery_package,
    normalize_llm_judge,
)


def test_normalize_llm_judge_accepts_four_dimensions():
    raw = {
        "score": 92,
        "dimensions": {
            "evidence_fidelity": 95,
            "customer_value": 90,
            "logical_coherence": 88,
            "language_professionalism": 94,
        },
        "findings": [],
        "strengths": ["有明确选型结论"],
    }
    result = normalize_llm_judge(raw)
    assert result["passed"] is True
    assert result["score"] == 91.75
    assert set(result["dimensions"]) == set(LLM_JUDGE_DIMENSIONS)
    assert result["findings"] == []


def test_normalize_llm_judge_maps_legacy_seven_dimensions():
    raw = {
        "dimensions": {
            "evidence_synthesis": 90,
            "customer_specificity": 80,
            "decision_usefulness": 86,
            "section_coherence": 84,
            "writing_quality": 92,
            "instruction_following": 88,
            "visual_structure": 76,
        },
        "findings": [],
    }
    result = normalize_llm_judge(raw)
    assert result["dimensions"]["evidence_fidelity"] == 90
    assert result["dimensions"]["customer_value"] == 83
    assert result["dimensions"]["logical_coherence"] == 84
    assert result["dimensions"]["language_professionalism"] == 92


def test_normalize_llm_judge_flags_low_dimension():
    raw = {
        "dimensions": {
            "evidence_fidelity": 55,
            "customer_value": 90,
            "logical_coherence": 88,
            "language_professionalism": 94,
        },
        "findings": [],
    }
    result = normalize_llm_judge(raw)
    assert result["passed"] is False
    assert any(
        item["code"] == "llm_dimensions_below_floor" for item in result["findings"]
    )


def test_normalize_llm_judge_unavailable():
    result = normalize_llm_judge(None)
    assert result["passed"] is False
    assert result["score"] == 0.0
    assert result["findings"][0]["code"] == "llm_judge_unavailable"


def test_combine_rule_and_llm_external_uses_fifty_fifty():
    rule = {
        "score": 80.0,
        "ready": True,
        "dimensions": {"structure": 90},
        "findings": [],
    }
    llm = {
        "evaluator_version": "v1",
        "score": 90.0,
        "passed": True,
        "dimensions": {"evidence_fidelity": 92, "customer_value": 88},
        "findings": [],
        "strengths": [],
    }
    combined = combine_rule_and_llm(rule, llm, external_delivery=True)
    assert combined["score"] == 85.0
    assert combined["ready"] is True
    assert "llm_evidence_fidelity" in combined["dimensions"]
    assert combined["judge"]["score"] == 90.0


def test_combine_rule_and_llm_internal_uses_sixty_forty():
    rule = {"score": 80.0, "ready": True, "dimensions": {}, "findings": []}
    llm = {
        "score": 90.0,
        "passed": True,
        "dimensions": {"evidence_fidelity": 92},
        "findings": [],
        "strengths": [],
    }
    combined = combine_rule_and_llm(rule, llm, external_delivery=False)
    assert combined["score"] == 84.0


def test_combine_rule_and_llm_without_llm_keeps_rule():
    rule = {"score": 82.0, "ready": True, "dimensions": {}, "findings": []}
    combined = combine_rule_and_llm(rule, None, external_delivery=True)
    assert combined["score"] == 82.0
    assert combined["judge"] is None


async def _llm_unavailable(*args, **kwargs):
    return None


async def _llm_ok(*args, **kwargs):
    return normalize_llm_judge(
        {
            "score": 90,
            "dimensions": {
                "evidence_fidelity": 92,
                "customer_value": 88,
                "logical_coherence": 90,
                "language_professionalism": 91,
            },
            "findings": [],
            "strengths": [],
        }
    )


async def test_evaluate_delivery_package_falls_back_without_llm(monkeypatch):
    monkeypatch.setattr(
        "app.services.artifact_llm_judge.evaluate_artifact_with_llm", _llm_unavailable
    )
    spec = ArtifactSpec(
        artifact_type=ArtifactType.CUSTOMER_SOLUTION,
        audience=ArtifactAudience.CUSTOMER,
        external_delivery=True,
    )
    text = "# 标题\n\n## 执行摘要\n\n正文内容。\n\n- 列表项\n"
    result = await evaluate_delivery_package(
        text=text,
        spec=spec,
        evidence_packet=None,
        original_request="客户方案",
        customer_context={},
        organization_id="org-1",
        user_id="user-1",
    )
    assert result["judge"] is None
    assert "format_score" in result["dimensions"]
    assert "delivery_safety_score" in result["dimensions"]
    assert result["format_lint"]["score"] == 100.0


async def test_evaluate_delivery_package_combines_llm_when_available(monkeypatch):
    monkeypatch.setattr(
        "app.services.artifact_llm_judge.evaluate_artifact_with_llm", _llm_ok
    )
    spec = ArtifactSpec(
        artifact_type=ArtifactType.TENDER,
        audience=ArtifactAudience.CUSTOMER,
        external_delivery=True,
    )
    text = "# 标题\n\n## 执行摘要\n\n正文内容。\n"
    result = await evaluate_delivery_package(
        text=text,
        spec=spec,
        evidence_packet=None,
        original_request="投标",
        customer_context={},
        organization_id="org-1",
        user_id="user-1",
    )
    assert result["judge"] is not None
    assert "llm_evidence_fidelity" in result["dimensions"]
