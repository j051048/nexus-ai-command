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
        citation = "[EVID:doc-1:chunk-1]"
        text = "\n\n".join(
            f"## {section}\n{instrument_line} 面向 {industry} 的已核验内容。{citation}"
            for section in spec.required_sections
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
