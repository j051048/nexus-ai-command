"""Deterministic quality evaluation for generated customer solutions."""

from __future__ import annotations

from typing import Any

EVALUATOR_VERSION = "solution-quality.v1"


def _percent(numerator: int, denominator: int) -> float:
    return round((numerator / denominator * 100) if denominator else 0, 2)


def evaluate_solution(workspace: dict[str, Any]) -> dict[str, Any]:
    requirements = workspace.get("requirements") or []
    sections = workspace.get("sections") or []
    packages = workspace.get("packages") or []
    must = [item for item in requirements if item.get("priority") == "must"]
    verified = [item for item in requirements if item.get("status") == "verified"]
    evidenced = [item for item in requirements if item.get("evidence_ref")]
    approved = [item for item in sections if item.get("status") == "approved"]
    cited_sections = [item for item in sections if item.get("evidence_refs")]
    unsupported_markers = ("保证", "绝对", "百分之百", "行业第一", "零风险")
    unsupported_claims = [
        {"section_id": item.get("id"), "marker": marker}
        for item in sections
        for marker in unsupported_markers
        if marker in str(item.get("content") or "") and not item.get("evidence_refs")
    ]
    commercial = (workspace.get("extension_data") or {}).get(
        "commercial_validation", {}
    )
    compatibility_errors = sum(
        len((item.get("commercial") or {}).get("validation_errors") or [])
        for item in packages
    )
    dimensions = {
        "requirement_coverage": _percent(len(verified), len(requirements)),
        "must_requirement_coverage": _percent(
            sum(item.get("status") == "verified" for item in must), len(must)
        ),
        "evidence_coverage": _percent(len(evidenced), len(requirements)),
        "section_approval": _percent(len(approved), len(sections)),
        "section_citation": _percent(len(cited_sections), len(sections)),
        "commercial_integrity": 100.0 if commercial.get("valid", True) else 0.0,
        "compatibility": max(0.0, 100.0 - compatibility_errors * 25),
        "claim_safety": max(0.0, 100.0 - len(unsupported_claims) * 25),
    }
    weights = {
        "requirement_coverage": 0.15,
        "must_requirement_coverage": 0.2,
        "evidence_coverage": 0.2,
        "section_approval": 0.1,
        "section_citation": 0.1,
        "commercial_integrity": 0.1,
        "compatibility": 0.1,
        "claim_safety": 0.05,
    }
    score = round(sum(dimensions[key] * weights[key] for key in weights), 2)
    findings: list[dict[str, Any]] = []
    if dimensions["must_requirement_coverage"] < 100:
        findings.append(
            {
                "severity": "high",
                "code": "must_requirements_open",
                "message": "仍有必选需求未核验",
            }
        )
    if dimensions["evidence_coverage"] < 80:
        findings.append(
            {
                "severity": "high",
                "code": "evidence_gap",
                "message": "需求证据覆盖率低于 80%",
            }
        )
    if not commercial.get("valid", True):
        findings.append(
            {
                "severity": "high",
                "code": "commercial_invalid",
                "message": "报价或产品目录校验未通过",
            }
        )
    if compatibility_errors:
        findings.append(
            {
                "severity": "high",
                "code": "compatibility_error",
                "message": "产品兼容性或目录校验存在错误",
                "count": compatibility_errors,
            }
        )
    if unsupported_claims:
        findings.append(
            {
                "severity": "high",
                "code": "unsupported_claim",
                "message": "存在缺少证据的绝对化承诺",
                "items": unsupported_claims,
            }
        )
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "score": score,
        "dimensions": dimensions,
        "findings": findings,
        "ready": score >= 85
        and not any(item["severity"] == "high" for item in findings),
    }
