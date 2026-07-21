"""Typed contract for user-visible Agent deliverables.

The contract separates ordinary conversational answers from artifacts that may
be sent to customers, regulators, or other external parties.  Downstream
retrieval, prompting, critic, and export gates all consume the same object.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ArtifactType(StrEnum):
    ANSWER = "answer"
    CUSTOMER_SOLUTION = "customer_solution"
    TENDER = "tender"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    POLICY_BRIEF = "policy_brief"
    SERVICE_PROPOSAL = "service_proposal"
    TECHNICAL_REPORT = "technical_report"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"


class ArtifactAudience(StrEnum):
    INTERNAL = "internal"
    CUSTOMER = "customer"
    REGULATOR = "regulator"
    PUBLIC = "public"


class ArtifactSpec(BaseModel):
    """Stable input contract for a generated artifact."""

    schema_version: str = "artifact-spec.v1"
    artifact_type: ArtifactType = ArtifactType.ANSWER
    audience: ArtifactAudience = ArtifactAudience.INTERNAL
    requested_formats: list[str] = Field(default_factory=lambda: ["text"])
    external_delivery: bool = False
    strict_quality: bool = False
    instrument_line: str | None = None
    industry: str | None = None
    region: str | None = None
    required_sections: list[str] = Field(default_factory=list)
    retrieval_topics: list[str] = Field(default_factory=list)
    min_evidence_coverage: float = Field(default=0.9, ge=0.0, le=1.0)
    max_repair_cycles: int = Field(default=2, ge=0, le=3)
    skill_id: str | None = None
    skill_version: str | None = None

    @property
    def requires_quality_gate(self) -> bool:
        return self.strict_quality or self.external_delivery


_TYPE_RULES: tuple[tuple[ArtifactType, tuple[str, ...]], ...] = (
    (
        ArtifactType.TENDER,
        ("标书", "投标文件", "招标响应", "技术偏离表", "bid document", "tender"),
    ),
    (
        ArtifactType.COMPETITOR_ANALYSIS,
        ("竞品", "竞争对手", "横向对比", "battlecard", "competitor"),
    ),
    (
        ArtifactType.POLICY_BRIEF,
        ("政策解读", "法规解读", "合规报告", "监管报告", "policy brief"),
    ),
    (
        ArtifactType.SERVICE_PROPOSAL,
        ("售后方案", "维保方案", "服务方案", "校准方案", "service proposal"),
    ),
    (
        ArtifactType.CUSTOMER_SOLUTION,
        ("解决方案", "客户方案", "产品方案", "配置方案", "solution proposal"),
    ),
    (
        ArtifactType.TECHNICAL_REPORT,
        ("技术报告", "分析报告", "验证报告", "实验报告", "technical report"),
    ),
)

_FORMAT_RULES: dict[str, tuple[str, ...]] = {
    "pdf": ("pdf",),
    "docx": ("word", "docx", "文档"),
    "xlsx": ("excel", "xlsx", "表格"),
    "pptx": ("ppt", "pptx", "演示文稿"),
    "image": ("图片", "海报", "png", "jpg"),
}

_EXTERNAL_HINTS = (
    "发给客户",
    "给客户",
    "对外",
    "正式版",
    "提交投标",
    "监管",
    "公开发布",
    "外发",
    "customer-facing",
    "external",
)

_INSTRUMENT_LINES: dict[str, tuple[str, ...]] = {
    "spectroscopy": ("光谱", "拉曼", "红外", "紫外", "荧光", "原子吸收"),
    "chromatography": ("色谱", "液相", "气相", "离子色谱"),
    "mass_spectrometry": ("质谱", "lc-ms", "gc-ms", "maldi"),
    "energy_spectroscopy": ("能谱", "xps", "eds", "edx", "xrf"),
    "electronic_instruments": ("电子仪器", "示波器", "频谱分析仪", "电源", "万用表"),
}


def _detect_artifact_type(text: str) -> ArtifactType:
    lowered = text.lower()
    for artifact_type, hints in _TYPE_RULES:
        if any(hint in lowered for hint in hints):
            return artifact_type
    if any(hint in lowered for hint in _FORMAT_RULES["xlsx"]):
        return ArtifactType.SPREADSHEET
    if any(hint in lowered for hint in _FORMAT_RULES["pptx"]):
        return ArtifactType.PRESENTATION
    return ArtifactType.ANSWER


def _detect_formats(text: str) -> list[str]:
    lowered = text.lower()
    formats = [
        output_format
        for output_format, hints in _FORMAT_RULES.items()
        if any(hint in lowered for hint in hints)
    ]
    return formats or ["text"]


def _detect_instrument_line(text: str) -> str | None:
    lowered = text.lower()
    for line, hints in _INSTRUMENT_LINES.items():
        if any(hint in lowered for hint in hints):
            return line
    return None


def infer_artifact_spec(
    text: str,
    overrides: dict[str, Any] | ArtifactSpec | None = None,
) -> ArtifactSpec:
    """Infer a conservative artifact contract from the user request."""

    if isinstance(overrides, ArtifactSpec):
        return overrides
    text = str(text or "")
    artifact_type = _detect_artifact_type(text)
    requested_formats = _detect_formats(text)
    lowered = text.lower()
    external = any(hint in lowered for hint in _EXTERNAL_HINTS)
    # Substantive authored deliverables are evidence-sensitive.  A plain
    # "export this existing table" command is not forced through the writing
    # critic, but still bypasses semantic cache at the cache boundary.
    high_stakes_type = artifact_type in {
        ArtifactType.CUSTOMER_SOLUTION,
        ArtifactType.TENDER,
        ArtifactType.COMPETITOR_ANALYSIS,
        ArtifactType.POLICY_BRIEF,
        ArtifactType.SERVICE_PROPOSAL,
        ArtifactType.TECHNICAL_REPORT,
    }
    audience = ArtifactAudience.INTERNAL
    if "监管" in text or "合规报告" in text:
        audience = ArtifactAudience.REGULATOR
    elif external or "客户" in text:
        audience = ArtifactAudience.CUSTOMER
    elif "公开" in text:
        audience = ArtifactAudience.PUBLIC

    inferred = ArtifactSpec(
        artifact_type=artifact_type,
        audience=audience,
        requested_formats=requested_formats,
        external_delivery=external,
        strict_quality=external or high_stakes_type,
        instrument_line=_detect_instrument_line(text),
        min_evidence_coverage=0.95 if external or high_stakes_type else 0.8,
    )
    if overrides:
        update = {key: value for key, value in overrides.items() if value is not None}
        inferred = inferred.model_copy(update=update)
    return inferred


def is_strict_artifact(value: ArtifactSpec | dict[str, Any] | None) -> bool:
    if not value:
        return False
    try:
        spec = (
            value
            if isinstance(value, ArtifactSpec)
            else ArtifactSpec.model_validate(value)
        )
    except (TypeError, ValueError):
        return False
    return spec.requires_quality_gate


def extract_explicit_region(text: str) -> str | None:
    match = re.search(
        r"(?:地区|区域|地域)[:：]?\s*([\u4e00-\u9fffA-Za-z-]{2,20})", text or ""
    )
    return match.group(1) if match else None
