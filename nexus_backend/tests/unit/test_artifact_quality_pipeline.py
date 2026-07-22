import json
from pathlib import Path

from app.agent.artifact_contract import (
    ArtifactAudience,
    ArtifactSpec,
    ArtifactType,
    infer_artifact_spec,
)
from app.agent.scientific_writing_skills import enrich_artifact_spec
from app.services.artifact_feedback_service import (
    build_artifact_feedback_candidate,
)
from app.services.artifact_quality_service import evaluate_text_artifact
from app.services.scientific_artifact_eval_service import (
    scientific_artifact_eval_service,
)


def _grounded_artifact(artifact_type: ArtifactType):
    spec = enrich_artifact_spec(
        ArtifactSpec(
            artifact_type=artifact_type,
            audience=ArtifactAudience.CUSTOMER,
            external_delivery=True,
            strict_quality=True,
        )
    )
    records = [
        {
            "document_id": f"doc-{index}",
            "chunk_id": f"chunk-{index}",
            "source_version": "2026.1",
            "valid_until": "2027-12-31",
        }
        for index, _topic in enumerate(spec.retrieval_topics, 1)
    ]
    packet = {
        "records": records,
        "coverage": 1.0,
        "sufficient": True,
        "missing_topics": [],
        "fingerprint": "evidence-fingerprint",
    }
    citation = "[EVID:doc-1:chunk-1]"
    target_per_section = max(
        260,
        spec.target_character_count // max(1, len(spec.required_sections)) + 80,
    )
    parts = [
        f"# 科学仪器{artifact_type.value}专业交付方案",
        "## 执行摘要",
        (
            "本成果基于企业已授权资料，完整说明客户目标、技术依据、实施路径、"
            "验收口径和风险边界。未被企业资料覆盖的参数、价格、交期、案例授权"
            "与服务承诺均须人工复核，确保最终外发版本可执行、可追溯并适合客户决策。"
            "交付负责人还应确认资料版本、适用条件和下一步动作，并在正式交付前完成"
            f"技术、商务与合规三方确认，避免未经核验的内容进入客户版本。{citation}"
        ),
    ]
    for index, title in enumerate(spec.required_sections, 1):
        body = (
            f"本节围绕“{title}”展开，说明第{index}项客户输入、企业能力、证据状态、"
            "实施动作、责任边界与验收输出。内容只采用已授权资料中的可核验事实，"
            "对尚未覆盖的信息明确标记为待确认，不将推断写成参数或商务承诺。"
            f"项目组应记录资料版本、适用条件、验证方法和下一步动作。{citation}"
        )
        while len(body) < target_per_section:
            body += (
                f" 对于{title}，还需由对应负责人复核证据与交付边界，"
                "使客户能够理解推荐依据并据此执行。"
            )
        parts.extend([f"## {title}", body])
    for index in range(spec.minimum_table_count):
        parts.extend(
            [
                f"### 核验矩阵 {index + 1}",
                "| 核验维度 | 当前结论 | 证据状态 | 下一步动作 |",
                "| --- | --- | --- | --- |",
                "| 客户需求 | 已完成场景归纳 | 已核验 | 确认验收口径 |",
                "| 企业能力 | 具备交付基础 | 已核验 | 完成配置复核 |",
            ]
        )
    text = "\n\n".join(parts)
    return spec, packet, text


def test_infers_external_scientific_solution_contract():
    spec = enrich_artifact_spec(
        infer_artifact_spec("给客户生成液相色谱解决方案并导出 PDF")
    )

    assert spec.artifact_type == ArtifactType.CUSTOMER_SOLUTION
    assert spec.audience == ArtifactAudience.CUSTOMER
    assert spec.external_delivery is True
    assert spec.instrument_line == "chromatography"
    assert spec.requested_formats == ["pdf"]
    assert spec.skill_id == "scientific.customer_solution"
    assert len(spec.required_sections) >= 8

    plain_export = infer_artifact_spec("导出 Excel")
    assert plain_export.artifact_type == ArtifactType.SPREADSHEET
    assert plain_export.requires_quality_gate is False


def test_grounded_artifact_passes_and_missing_evidence_fails_closed():
    spec, packet, text = _grounded_artifact(ArtifactType.TENDER)

    accepted = evaluate_text_artifact(text, spec, packet)
    rejected = evaluate_text_artifact(text, spec, {})

    assert accepted["ready"] is True
    assert accepted["score"] >= 85
    assert rejected["ready"] is False
    assert {item["code"] for item in rejected["findings"]} >= {
        "evidence_insufficient",
        "citation_invalid",
    }


def test_unsafe_service_commitment_requires_human_review():
    spec, packet, text = _grounded_artifact(ArtifactType.SERVICE_PROPOSAL)

    quality = evaluate_text_artifact(text + "\n我们保证响应并当天修复。", spec, packet)

    assert quality["ready"] is False
    assert "unsafe_service_commitment" in {item["code"] for item in quality["findings"]}


def test_feedback_is_recommendation_only_and_requires_grounded_improvement():
    candidate = build_artifact_feedback_candidate(
        change_type="edited",
        rating=5,
        original_content="原始内容",
        revised_content="修订后内容 [EVID:doc-1:chunk-1]",
        quality_before={"score": 82, "ready": False},
        quality_after={"score": 92, "ready": True},
        evidence_fingerprint="fingerprint",
    )

    assert candidate["promote_eligible"] is True
    assert candidate["learning_status"] == "review_candidate"
    assert candidate["auto_apply"] is False

    ungrounded = build_artifact_feedback_candidate(
        change_type="edited",
        rating=5,
        original_content="a",
        revised_content="b",
        quality_before={"score": 80, "ready": False},
        quality_after={"score": 95, "ready": False},
        evidence_fingerprint="fingerprint",
    )
    assert ungrounded["promote_eligible"] is False


def test_scientific_artifact_matrix_covers_125_combinations():
    path = (
        Path(__file__).resolve().parents[2]
        / "evals"
        / "datasets"
        / "scientific_artifact_quality_matrix.json"
    )
    matrix = json.loads(path.read_text(encoding="utf-8"))

    result = scientific_artifact_eval_service.evaluate(matrix)

    assert result["case_count"] == 125
    assert result["expected_case_count"] == 125
    assert result["accuracy"] == 1.0
