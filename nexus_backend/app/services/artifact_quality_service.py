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
    contains_internal_markers,
    contains_internal_trace_markers,
    duplicate_paragraph_ratio,
)

ARTIFACT_EVALUATOR_VERSION = "artifact-quality.v3"
_CITATION_RE = re.compile(r"\[EVID:([^:\]\s]+):([^\]\s]+)\]")
_NUMBER_RE = re.compile(
    r"(?<![\w-])\d+(?:\.\d+)?\s*(?:%|万|万元|元|天|小时|年|个月|台|套|pp[mb]|mg|μg|nm)?",
    re.I,
)
_ABSOLUTE_CLAIMS = ("保证", "绝对", "百分之百", "行业第一", "零风险", "100%")
_PROMISE_HINTS = ("保证响应", "永久", "终身免费", "无条件", "当天修复")
_POLICY_HINTS = ("政策", "法规", "标准", "办法", "条例", "规范")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}.*\|", re.M)
_GENERIC_TITLE_RE = re.compile(
    r"^(?:AI成果|专业报告|客户解决方案|企业资料|load[_ -]?knowledge)$", re.I
)


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
    metrics: dict[str, Any] = Field(default_factory=dict)
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


def _plain_character_count(text: str) -> int:
    without_citations = _CITATION_RE.sub("", str(text or ""))
    return len(re.sub(r"[#|>*_`\s]", "", without_citations))


def _first_title(text: str) -> str:
    match = re.search(r"^#\s+(.+)$", str(text or ""), re.M)
    return match.group(1).strip() if match else ""


def _section_bodies(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", str(text or ""), re.M))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[match.end() : end].strip()
    return sections


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

    title = _first_title(text)
    normalized_title = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9_-]", "", title)
    title_quality = 100.0
    if (
        len(title) < 6
        or contains_internal_markers(title)
        or _GENERIC_TITLE_RE.match(normalized_title)
    ):
        title_quality = 0.0
        findings.append(
            QualityFinding(
                severity="high" if spec.requires_quality_gate else "medium",
                code="title_missing_or_generic",
                message="成果缺少面向客户的正式标题，或标题仍是工具名/通用占位名",
                details={"title": title},
            )
        )

    section_bodies = _section_bodies(text)
    summary_length = _plain_character_count(section_bodies.get("执行摘要", ""))
    if spec.requires_quality_gate and summary_length < 140:
        findings.append(
            QualityFinding(
                severity="high",
                code="executive_summary_insufficient",
                message="执行摘要缺失或未形成可供客户快速决策的完整摘要",
                details={"character_count": summary_length, "minimum": 140},
            )
        )
    section_minimum = max(
        120,
        int(spec.minimum_character_count / max(1, len(required)) * 0.48),
    )
    short_sections = [
        section_title
        for section_title in required
        if _plain_character_count(section_bodies.get(section_title, ""))
        < section_minimum
    ]
    if spec.requires_quality_gate and short_sections:
        findings.append(
            QualityFinding(
                severity="high",
                code="section_depth_insufficient",
                message="部分必需章节仍是提纲或内容过浅",
                details={
                    "sections": short_sections,
                    "minimum_characters_per_section": section_minimum,
                },
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

    plain_length = _plain_character_count(text)
    if spec.requires_quality_gate and plain_length < spec.minimum_character_count:
        findings.append(
            QualityFinding(
                severity="high",
                code="content_too_short",
                message="正文未达到用户要求的最低篇幅",
                details={
                    "character_count": plain_length,
                    "minimum": spec.minimum_character_count,
                    "target": spec.target_character_count,
                    "deficit": max(0, spec.minimum_character_count - plain_length),
                },
            )
        )
    elif spec.requires_quality_gate and plain_length < spec.target_character_count:
        findings.append(
            QualityFinding(
                severity="medium",
                code="content_depth_low",
                message="成果已达到最低标准，但尚未达到目标篇幅",
                details={
                    "character_count": plain_length,
                    "target": spec.target_character_count,
                },
            )
        )

    table_count = len(_TABLE_SEPARATOR_RE.findall(text))
    visual_structure = (
        100.0
        if spec.minimum_table_count == 0
        else min(100.0, table_count / spec.minimum_table_count * 100)
    )
    if spec.requires_quality_gate and table_count < spec.minimum_table_count:
        findings.append(
            QualityFinding(
                severity="high",
                code="structured_components_missing",
                message="缺少需求、配置、参数、竞品或实施等结构化表格",
                details={
                    "table_count": table_count,
                    "minimum": spec.minimum_table_count,
                },
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
        "content_depth": round(
            min(100.0, plain_length / max(1, spec.minimum_character_count) * 100),
            2,
        ),
        "instruction_following": round(
            min(100.0, plain_length / max(1, spec.target_character_count) * 100),
            2,
        ),
        "visual_structure": round(visual_structure, 2),
        "title_quality": round(title_quality, 2),
    }
    score = round(
        dimensions["structure"] * 0.15
        + dimensions["evidence_coverage"] * 0.2
        + dimensions["citation_validity"] * 0.15
        + dimensions["claim_safety"] * 0.08
        + dimensions["policy_currency"] * 0.05
        + dimensions["originality"] * 0.06
        + dimensions["export_hygiene"] * 0.06
        + dimensions["content_depth"] * 0.12
        + dimensions["instruction_following"] * 0.08
        + dimensions["visual_structure"] * 0.03
        + dimensions["title_quality"] * 0.02,
        2,
    )
    blockers = [item for item in findings if item.severity == "high"]
    ready = bool(text.strip()) and score >= 85 and not blockers
    repairable = [item.message for item in findings if item.repairable]
    result = ArtifactQualityResult(
        score=score,
        ready=ready,
        dimensions=dimensions,
        metrics={
            "character_count": plain_length,
            "target_character_count": spec.target_character_count,
            "minimum_character_count": spec.minimum_character_count,
            "table_count": table_count,
            "minimum_table_count": spec.minimum_table_count,
            "required_section_count": len(required),
            "short_section_count": len(short_sections),
            "executive_summary_character_count": summary_length,
        },
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
    template_key: str | None = None,
    judge_snapshot: dict[str, Any] | None = None,
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
                "template_key": template_key,
                "judge_snapshot": judge_snapshot or quality.get("judge") or {},
                "created_at": datetime.now(UTC).isoformat(),
            }
        ).execute()
    except Exception:  # broad-except: intentional
        # The migration can be rolled out independently of application code.
        return
