"""Deterministic quality gate for externally usable Agent artifacts."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.agent.artifact_contract import ArtifactSpec, ArtifactType
from app.agent.scientific_writing_skills import (
    enrich_artifact_spec,
)
from app.services.artifact_content_sanitizer import (
    contains_internal_trace_markers,
    duplicate_paragraph_ratio,
)

ARTIFACT_EVALUATOR_VERSION = "artifact-quality.v2"
_CITATION_RE = re.compile(r"\[EVID:([^:\]\s]+):([^\]\s]+)\]")
_NUMBER_RE = re.compile(
    r"(?<![\w-])\d+(?:\.\d+)?\s*(?:%|万|万元|元|天|小时|年|个月|台|套|pp[mb]|mg|μg|nm)?",
    re.I,
)
_ABSOLUTE_CLAIMS = ("保证", "绝对", "百分之百", "行业第一", "零风险", "100%")
_PROMISE_HINTS = ("保证响应", "永久", "终身免费", "无条件", "当天修复")
_POLICY_HINTS = ("政策", "法规", "标准", "办法", "条例", "规范")


class QualityFinding(BaseModel):
    severity: str
    code: str
    message: str
    repairable: bool = True
    details: dict[str, Any] = Field(default_factory=dict)


class ArtifactQualityResult(BaseModel):
    evaluator_version: str = ARTIFACT_EVALUATOR_VERSION
    score: float
    ready: bool
    dimensions: dict[str, float]
    findings: list[QualityFinding]
    repair_guidance: str = ""
    output_hash: str


def _heading_present(text: str, title: str) -> bool:
    normalized = re.sub(r"[\s、，,：:（）()/_-]", "", title).lower()
    compact_text = re.sub(r"[\s、，,：:（）()/_-]", "", text).lower()
    if normalized in compact_text:
        return True
    terms = [
        term
        for term in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", title)
        if len(term) >= 2
    ]
    return bool(terms) and sum(term.lower() in compact_text for term in terms) >= max(
        1, len(terms) // 2
    )


def _evidence_ids(evidence_packet: dict[str, Any] | None) -> set[tuple[str, str]]:
    records = (evidence_packet or {}).get("records") or []
    return {
        (str(item.get("document_id") or ""), str(item.get("chunk_id") or ""))
        for item in records
        if item.get("document_id") and item.get("chunk_id")
    }


def evaluate_text_artifact(
    text: str,
    spec: ArtifactSpec | dict[str, Any],
    evidence_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate structure, grounding, freshness, and promise safety."""

    spec = enrich_artifact_spec(spec)
    text = str(text or "")
    findings: list[QualityFinding] = []
    required = spec.required_sections
    matched_sections = [title for title in required if _heading_present(text, title)]
    structure_score = (
        100.0 if not required else len(matched_sections) / len(required) * 100
    )
    missing_sections = [title for title in required if title not in matched_sections]
    if missing_sections:
        findings.append(
            QualityFinding(
                severity="high" if spec.requires_quality_gate else "medium",
                code="required_sections_missing",
                message="交付物缺少必需章节",
                details={"sections": missing_sections},
            )
        )

    valid_ids = _evidence_ids(evidence_packet)
    citations = set(_CITATION_RE.findall(text))
    valid_citations = citations & valid_ids
    evidence_coverage = float((evidence_packet or {}).get("coverage") or 0) * 100
    if valid_ids and citations:
        citation_validity = len(valid_citations) / len(citations) * 100
    elif spec.requires_quality_gate:
        citation_validity = 0.0
    else:
        citation_validity = 100.0
    evidence_sufficient = bool((evidence_packet or {}).get("sufficient"))
    if spec.requires_quality_gate and (
        evidence_coverage < spec.min_evidence_coverage * 100 or not evidence_sufficient
    ):
        findings.append(
            QualityFinding(
                severity="high",
                code="evidence_insufficient",
                message="企业知识证据不足，不能作为正式外发依据",
                repairable=False,
                details={
                    "coverage": round(evidence_coverage, 2),
                    "record_count": len(valid_ids),
                    "minimum_record_count": (evidence_packet or {}).get(
                        "minimum_record_count", 0
                    ),
                    "missing_topics": (evidence_packet or {}).get("missing_topics", []),
                },
            )
        )
    if spec.requires_quality_gate and citation_validity < 90:
        findings.append(
            QualityFinding(
                severity="high",
                code="citation_invalid",
                message="引用缺失或引用了不在本次证据包中的资料",
                details={"valid": len(valid_citations), "total": len(citations)},
            )
        )

    duplicate_ratio = duplicate_paragraph_ratio(text)
    if duplicate_ratio > 0.22:
        findings.append(
            QualityFinding(
                severity="high" if spec.requires_quality_gate else "medium",
                code="duplicate_content",
                message="正文存在较多重复段落，需要整合后再交付",
                details={"duplicate_ratio": duplicate_ratio},
            )
        )
    trace_leakage = contains_internal_trace_markers(text)
    if trace_leakage:
        findings.append(
            QualityFinding(
                severity="high",
                code="internal_trace_leakage",
                message="成果中包含工具日志或内部检索标记",
            )
        )

    plain_length = len(re.sub(r"[#|>*_`\s]", "", text))
    if spec.requires_quality_gate and plain_length < 220:
        findings.append(
            QualityFinding(
                severity="high",
                code="content_too_short",
                message="正文不足以形成可交付成果",
                details={"character_count": plain_length, "minimum": 220},
            )
        )
    elif spec.requires_quality_gate and plain_length < 800:
        findings.append(
            QualityFinding(
                severity="medium",
                code="content_depth_low",
                message="成果深度偏低，建议补充需求、配置、实施和风险说明",
                details={"character_count": plain_length, "recommended": 800},
            )
        )

    numeric_claims = _NUMBER_RE.findall(_CITATION_RE.sub("", text))
    if spec.requires_quality_gate and numeric_claims and not valid_citations:
        findings.append(
            QualityFinding(
                severity="high",
                code="numeric_claims_unsupported",
                message="正文包含缺少有效来源的数字、性能或商务事实",
                details={"examples": numeric_claims[:8]},
            )
        )

    unsafe_claims = [marker for marker in _ABSOLUTE_CLAIMS if marker in text]
    if unsafe_claims and not valid_citations:
        findings.append(
            QualityFinding(
                severity="high",
                code="unsupported_absolute_claim",
                message="存在缺少证据支持的绝对化表述",
                details={"markers": unsafe_claims},
            )
        )
    if spec.artifact_type == ArtifactType.SERVICE_PROPOSAL:
        promises = [marker for marker in _PROMISE_HINTS if marker in text]
        if promises:
            findings.append(
                QualityFinding(
                    severity="high",
                    code="unsafe_service_commitment",
                    message="服务承诺需要负责人确认后才能外发",
                    repairable=False,
                    details={"markers": promises},
                )
            )
    policy_currency = 100.0
    if spec.artifact_type == ArtifactType.POLICY_BRIEF or any(
        hint in text for hint in _POLICY_HINTS
    ):
        records = (evidence_packet or {}).get("records") or []
        dated = [
            item
            for item in records
            if item.get("source_version") or item.get("valid_until")
        ]
        policy_currency = 100.0 if dated else 0.0
        if spec.requires_quality_gate and not dated:
            findings.append(
                QualityFinding(
                    severity="high",
                    code="policy_freshness_unknown",
                    message="政策或标准资料缺少版本/有效期信息",
                    repairable=False,
                )
            )

    claim_safety = max(0.0, 100.0 - 25.0 * len(unsafe_claims))
    dimensions = {
        "structure": round(structure_score, 2),
        "evidence_coverage": round(evidence_coverage, 2),
        "citation_validity": round(citation_validity, 2),
        "claim_safety": round(claim_safety, 2),
        "policy_currency": round(policy_currency, 2),
        "originality": round(max(0.0, 100.0 - duplicate_ratio * 200), 2),
        "export_hygiene": 0.0 if trace_leakage else 100.0,
        "content_depth": round(min(100.0, plain_length / 8), 2),
    }
    score = round(
        dimensions["structure"] * 0.22
        + dimensions["evidence_coverage"] * 0.24
        + dimensions["citation_validity"] * 0.19
        + dimensions["claim_safety"] * 0.1
        + dimensions["policy_currency"] * 0.07
        + dimensions["originality"] * 0.07
        + dimensions["export_hygiene"] * 0.06
        + dimensions["content_depth"] * 0.05,
        2,
    )
    blockers = [item for item in findings if item.severity == "high"]
    ready = bool(text.strip()) and score >= 85 and not blockers
    repairable = [item.message for item in findings if item.repairable]
    result = ArtifactQualityResult(
        score=score,
        ready=ready,
        dimensions=dimensions,
        findings=findings,
        repair_guidance="；".join(repairable[:5]),
        output_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    return result.model_dump(mode="json")


async def persist_artifact_quality_event(
    *,
    quality: dict[str, Any],
    spec: ArtifactSpec | dict[str, Any],
    org_id: str | None,
    user_id: str | None,
    session_id: str | None,
    repair_count: int = 0,
    evidence_count: int = 0,
) -> None:
    """Best-effort persistence; quality gating never depends on telemetry."""

    if not org_id:
        return
    try:
        from app.core.database import supabase

        if not supabase:
            return
        spec = enrich_artifact_spec(spec)
        await supabase.table("agent_artifact_quality_events").insert(
            {
                "organization_id": org_id,
                "user_id": user_id,
                "session_id": session_id,
                "artifact_type": spec.artifact_type.value,
                "skill_id": spec.skill_id,
                "skill_version": spec.skill_version,
                "score": quality.get("score", 0),
                "ready": quality.get("ready", False),
                "dimensions": quality.get("dimensions", {}),
                "findings": quality.get("findings", []),
                "evidence_count": evidence_count,
                "repair_count": repair_count,
                "output_hash": quality.get("output_hash"),
                "created_at": datetime.now(UTC).isoformat(),
            }
        ).execute()
    except Exception:
        # The migration can be rolled out independently of application code.
        return
