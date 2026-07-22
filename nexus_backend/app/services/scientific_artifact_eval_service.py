"""Offline regression harness for scientific-instrument deliverables.

The matrix deliberately avoids LLM calls.  It verifies that every supported
instrument line, customer industry, and artifact type resolves to the same
typed contract, evidence rules, and fail-closed quality behavior used in
production.
"""

from __future__ import annotations

from itertools import product
from typing import Any

from app.agent.artifact_contract import (
    ArtifactAudience,
    ArtifactSpec,
    ArtifactType,
)
from app.agent.scientific_writing_skills import enrich_artifact_spec
from app.services.artifact_quality_service import evaluate_text_artifact


def _grounded_fixture_text(
    spec: ArtifactSpec,
    *,
    instrument_line: str,
    industry: str,
) -> str:
    """Build a deterministic full-depth fixture that mirrors the delivery contract."""

    citation = "[EVID:doc-1:chunk-1]"
    target_per_section = max(
        260,
        spec.target_character_count // max(1, len(spec.required_sections)) + 80,
    )
    parts = [
        f"# {instrument_line} {industry} {spec.artifact_type.value} 专业交付方案",
        "## 执行摘要",
        (
            f"本成果面向 {industry} 场景，围绕 {instrument_line} 的客户目标、技术依据、"
            "交付路径、验收口径和风险边界形成完整闭环。所有事实均来自本次证据包，"
            "未被资料覆盖的参数、价格、交期、案例授权和服务承诺必须保留为人工核验项。"
            "交付团队应先确认场景与验收方式，再依据企业能力完成配置、实施和复核，"
            f"确保最终成果可执行、可追溯并适合客户决策。{citation}"
        ),
    ]
    for index, section in enumerate(spec.required_sections, 1):
        sentence = (
            f"本节围绕“{section}”展开，针对 {instrument_line} 在 {industry} 的实际需求，"
            "分别说明客户输入、企业能力、证据状态、实施动作、责任边界与验收输出。"
            "内容只采用已授权资料中的可核验事实；尚未覆盖的信息明确列为待确认，"
            "不得将推断写成产品参数、商务承诺或真实案例。"
            f"这是第{index}个交付章节，其结论需要在外发前由对应负责人完成复核。{citation}"
        )
        body = sentence
        while len(body) < target_per_section:
            body += (
                f" 对于{section}，项目组还应记录资料版本、适用条件、验证方法和下一步动作，"
                "使客户能够理解推荐依据，也使内部团队能够据此执行和追责。"
            )
        parts.extend([f"## {section}", body])

    for index in range(spec.minimum_table_count):
        parts.extend(
            [
                f"### 核验矩阵 {index + 1}",
                "| 核验维度 | 已核验结论 | 证据状态 | 下一步动作 |",
                "| --- | --- | --- | --- |",
                f"| 客户场景 | 已完成第{index + 1}轮归纳 | 已核验 | 确认验收口径 |",
                "| 企业能力 | 具备交付基础 | 已核验 | 完成配置复核 |",
                "| 商务边界 | 以审批版本为准 | 待核验 | 负责人签字确认 |",
            ]
        )
    return "\n\n".join(parts)


class ScientificArtifactEvalService:
    """Expand and evaluate a compact, versioned artifact matrix."""

    def evaluate(self, matrix: dict[str, Any]) -> dict[str, Any]:
        instrument_lines = matrix.get("instrument_lines") or []
        industries = matrix.get("industries") or []
        artifact_types = matrix.get("artifact_types") or []
        results: list[dict[str, Any]] = []

        for instrument_line, industry, artifact_type_value in product(
            instrument_lines,
            industries,
            artifact_types,
        ):
            result = self._evaluate_case(
                instrument_line=str(instrument_line),
                industry=str(industry),
                artifact_type_value=str(artifact_type_value),
            )
            results.append(result)

        passed = sum(int(item["passed"]) for item in results)
        total = len(results)
        return {
            "runner": "scientific_artifact_contract_v1",
            "matrix_version": matrix.get("schema_version"),
            "case_count": total,
            "expected_case_count": int(matrix.get("expected_case_count") or 0),
            "passed": passed,
            "accuracy": round(passed / total, 4) if total else 0.0,
            "results": results,
        }

    @staticmethod
    def _evaluate_case(
        *,
        instrument_line: str,
        industry: str,
        artifact_type_value: str,
    ) -> dict[str, Any]:
        failures: list[str] = []
        try:
            artifact_type = ArtifactType(artifact_type_value)
            spec = enrich_artifact_spec(
                ArtifactSpec(
                    artifact_type=artifact_type,
                    audience=ArtifactAudience.CUSTOMER,
                    external_delivery=True,
                    strict_quality=True,
                    instrument_line=instrument_line,
                    industry=industry,
                )
            )
        except (TypeError, ValueError) as exc:
            return {
                "id": f"{instrument_line}:{industry}:{artifact_type_value}",
                "passed": False,
                "failures": [f"invalid_contract:{exc}"],
            }

        if not spec.skill_id or not spec.skill_version:
            failures.append("writing_skill_missing")
        if len(spec.required_sections) < 5:
            failures.append("section_contract_too_shallow")
        if len(spec.retrieval_topics) < 4:
            failures.append("retrieval_contract_too_shallow")

        records = [
            {
                "document_id": f"doc-{index}",
                "chunk_id": f"chunk-{index}",
                "title": topic,
                "excerpt": f"{instrument_line} / {industry} / {topic}",
                "source_version": "2026.1",
                "valid_until": "2027-12-31",
                "purposes": [topic],
            }
            for index, topic in enumerate(spec.retrieval_topics, 1)
        ]
        text = _grounded_fixture_text(
            spec,
            instrument_line=instrument_line,
            industry=industry,
        )
        evidence_packet = {
            "records": records,
            "coverage": 1.0,
            "sufficient": True,
            "missing_topics": [],
        }
        positive = evaluate_text_artifact(text, spec, evidence_packet)
        negative = evaluate_text_artifact(text, spec, {})
        if not positive.get("ready"):
            failures.append("grounded_artifact_rejected")
        if negative.get("ready"):
            failures.append("ungrounded_artifact_accepted")

        return {
            "id": f"{instrument_line}:{industry}:{artifact_type.value}",
            "passed": not failures,
            "skill_id": spec.skill_id,
            "skill_version": spec.skill_version,
            "positive_score": positive.get("score"),
            "failures": failures,
        }


scientific_artifact_eval_service = ScientificArtifactEvalService()
