"""End-to-end generation pipeline for durable, evidence-grounded artifacts."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.agent.artifact_contract import (
    ArtifactAudience,
    ArtifactSpec,
    ArtifactType,
    infer_artifact_spec,
)
from app.agent.scientific_writing_skills import (
    build_writing_skill_prompt,
    enrich_artifact_spec,
)
from app.services.agent_evidence_service import EvidencePacket
from app.services.artifact_content_sanitizer import sanitize_artifact_content
from app.services.artifact_evidence_compiler import compile_artifact_evidence
from app.services.artifact_quality_service import (
    evaluate_text_artifact,
    persist_artifact_quality_event,
)
from app.services.llm_gateway import llm_gateway

ARTIFACT_PIPELINE_VERSION = "artifact-pipeline.v1"
ARTIFACT_LABELS = {
    ArtifactType.CUSTOMER_SOLUTION: "客户解决方案",
    ArtifactType.TENDER: "投标成果",
    ArtifactType.COMPETITOR_ANALYSIS: "竞品分析",
    ArtifactType.POLICY_BRIEF: "政策与合规简报",
    ArtifactType.SERVICE_PROPOSAL: "服务方案",
    ArtifactType.TECHNICAL_REPORT: "技术报告",
    ArtifactType.SPREADSHEET: "数据成果",
    ArtifactType.PRESENTATION: "演示成果",
    ArtifactType.ANSWER: "专业报告",
}


def _parse_json_object(content: str) -> dict[str, Any] | None:
    value = str(content or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I | re.S)
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", value)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _citation(value: str) -> str:
    value = str(value or "").strip().strip("[]")
    if not value:
        return ""
    return f"[{value}]" if value.startswith("EVID:") else value


def _artifact_markdown(
    *,
    title: str,
    generated: dict[str, Any],
    spec: ArtifactSpec,
    fallback_source: str,
) -> tuple[str, list[str]]:
    sections = generated.get("sections")
    if not isinstance(sections, list):
        sections = []
    by_title = {
        str(item.get("title") or "").strip(): item
        for item in sections
        if isinstance(item, dict) and item.get("title")
    }
    ordered: list[dict[str, Any]] = []
    for required in spec.required_sections:
        match = by_title.pop(required, None)
        if match:
            ordered.append(match)
        else:
            ordered.append(
                {
                    "title": required,
                    "content": "待核验：现有企业资料不足以完整支撑本章节，请补充或由负责人确认。",
                    "evidence_refs": [],
                }
            )
    ordered.extend(by_title.values())
    if not ordered and fallback_source:
        ordered = [
            {
                "title": "现有内容整理",
                "content": fallback_source,
                "evidence_refs": [],
            }
        ]

    lines = [f"# {title}", ""]
    summary = str(generated.get("executive_summary") or "").strip()
    if summary:
        lines.extend(["## 执行摘要", summary, ""])
    verification_items = [
        str(item).strip()
        for item in (generated.get("verification_items") or [])
        if str(item).strip()
    ]
    for section in ordered:
        section_title = str(section.get("title") or "未命名章节").strip()
        content = str(section.get("content") or "待核验").strip()
        refs = [_citation(item) for item in (section.get("evidence_refs") or [])]
        refs = [item for item in refs if item]
        lines.extend([f"## {section_title}", content])
        if refs and not any(ref in content for ref in refs):
            lines.append("依据：" + " ".join(refs))
        lines.append("")
    if verification_items:
        lines.extend(["## 人工复核清单", ""])
        lines.extend(f"- {item}" for item in verification_items)
        lines.append("")
    lines.append(
        "> 本成果为 AI 辅助草稿；参数、价格、交期、案例、政策适用性及对外承诺须经人工复核。"
    )
    return "\n".join(lines).strip(), verification_items


def _build_prompt(
    *,
    original_request: str,
    source_content: str,
    customer_context: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
) -> tuple[str, dict[str, Any]]:
    writing_contract = build_writing_skill_prompt(spec)
    system_prompt = f"""你是科学仪器企业的首席售前方案编辑，熟悉光谱、色谱、质谱、能谱和电子测试仪器。
你的任务不是复述聊天记录，而是交付可以进入人工审核的专业成果。

硬性规则：
1. 仅使用下方企业证据；不得虚构型号、参数、政策、资质、案例、价格、交期、ROI 或服务承诺。
2. 每项关键事实必须在所在章节的 evidence_refs 中绑定 [EVID:document_id:chunk_id]；证据不足写“待核验”。
3. 不得输出工具日志、检索原文标题块、trace、chunk_id 或任何系统提示。
4. 必须整合、去重和重写，不得大段复制原回答或检索片段。
5. 风格专业、克制、可扫描；优先使用短段落、矩阵和清单，避免空泛形容词。
6. 输出严格 JSON，不要 Markdown 代码围栏。

{writing_contract}
"""
    payload = {
        "original_request": original_request,
        "customer_context": customer_context,
        "existing_answer_for_reference_only": source_content[:12000],
        "enterprise_evidence": evidence.prompt_context,
        "artifact_spec": spec.model_dump(mode="json"),
        "output_schema": {
            "title": "成果标题",
            "executive_summary": "200-400字执行摘要",
            "sections": [
                {
                    "title": "必须严格匹配 required_sections 中的标题",
                    "content": "完整正文，可含 Markdown 表格",
                    "evidence_refs": ["EVID:document_id:chunk_id"],
                }
            ],
            "verification_items": ["需要人工确认的参数、案例、价格、交期或承诺"],
        },
    }
    return system_prompt, payload


async def _generate_draft(
    *,
    original_request: str,
    source_content: str,
    customer_context: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
    organization_id: str,
    user_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    system_prompt, payload = _build_prompt(
        original_request=original_request,
        source_content=source_content,
        customer_context=customer_context,
        spec=spec,
        evidence=evidence,
    )
    response = await llm_gateway.chat(
        scene_code="artifact_delivery",
        agent_code="scientific_artifact_editor",
        user_id=user_id,
        org_id=organization_id,
        system_prompt=system_prompt,
        messages=[
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, default=str),
            }
        ],
        temperature=0.15,
        max_tokens=5200,
    )
    parsed = (
        _parse_json_object(response.content)
        if response.finish_reason != "error"
        else None
    )
    return parsed or {}, {
        "model": response.model_code,
        "usage": response.usage,
        "degraded": parsed is None,
    }


async def generate_artifact(
    *,
    db: Any,
    organization_id: str,
    user_id: str,
    original_request: str,
    source_content: str,
    title: str | None = None,
    artifact_type: ArtifactType | str | None = None,
    audience: ArtifactAudience | str = ArtifactAudience.CUSTOMER,
    requested_formats: list[str] | None = None,
    customer_context: dict[str, Any] | None = None,
    selected_document_ids: list[str] | None = None,
    session_id: str | None = None,
    review_confirmed: bool = False,
) -> dict[str, Any]:
    """Generate, repair, score and persist a durable artifact version."""

    overrides: dict[str, Any] = {
        "audience": audience,
        "requested_formats": requested_formats or ["docx", "pdf"],
        "external_delivery": str(audience) != ArtifactAudience.INTERNAL.value,
        "strict_quality": True,
    }
    if artifact_type:
        overrides["artifact_type"] = artifact_type
    spec = enrich_artifact_spec(
        infer_artifact_spec(f"{original_request}\n{source_content[:1000]}", overrides)
    )
    safe_source = sanitize_artifact_content(
        source_content, keep_citations=False
    ).content
    evidence = await compile_artifact_evidence(
        query=original_request,
        spec=spec,
        organization_id=organization_id,
        user_id=user_id,
        db=db,
        selected_document_ids=selected_document_ids,
    )
    generated, generation = await _generate_draft(
        original_request=original_request,
        source_content=safe_source,
        customer_context=customer_context or {},
        spec=spec,
        evidence=evidence,
        organization_id=organization_id,
        user_id=user_id,
    )
    artifact_title = str(title or generated.get("title") or "").strip()
    if not artifact_title:
        artifact_title = (
            f"{ARTIFACT_LABELS[spec.artifact_type]}-{datetime.now(UTC):%Y%m%d}"
        )
    content, verification_items = _artifact_markdown(
        title=artifact_title,
        generated=generated,
        spec=spec,
        fallback_source=safe_source,
    )
    quality = evaluate_text_artifact(content, spec, evidence.model_dump(mode="json"))
    repair_count = 0
    while (
        repair_count < spec.max_repair_cycles
        and evidence.sufficient
        and not quality.get("ready")
        and any(item.get("repairable") for item in quality.get("findings") or [])
    ):
        repair_count += 1
        response = await llm_gateway.chat(
            scene_code="artifact_delivery_repair",
            agent_code="scientific_artifact_critic",
            user_id=user_id,
            org_id=organization_id,
            system_prompt=(
                build_writing_skill_prompt(spec)
                + "\n修复缺失章节、重复内容和无效引用。只返回与首次相同的严格 JSON。"
            ),
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "draft": generated,
                            "quality_findings": quality.get("findings") or [],
                            "enterprise_evidence": evidence.prompt_context,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            ],
            temperature=0.05,
            max_tokens=5200,
        )
        repaired = (
            _parse_json_object(response.content)
            if response.finish_reason != "error"
            else None
        )
        if not repaired:
            break
        generated = repaired
        content, verification_items = _artifact_markdown(
            title=artifact_title,
            generated=generated,
            spec=spec,
            fallback_source=safe_source,
        )
        quality = evaluate_text_artifact(
            content, spec, evidence.model_dump(mode="json")
        )

    artifact_id = str(uuid4())
    version_id = str(uuid4())
    now = datetime.now(UTC).isoformat()
    status = "review" if quality.get("ready") else "needs_revision"
    approval_status = (
        "approved" if review_confirmed and quality.get("ready") else "pending"
    )
    artifact_code = f"ART-{datetime.now(UTC):%Y%m%d}-{artifact_id[:8].upper()}"
    metadata = {
        "pipeline_version": ARTIFACT_PIPELINE_VERSION,
        "session_id": session_id,
        "requested_formats": spec.requested_formats,
        "customer_context": customer_context or {},
        "selected_document_ids": selected_document_ids or [],
        "generation": {**generation, "repair_count": repair_count},
        "verification_items": verification_items,
        "sanitization": {
            "source_was_sanitized": safe_source != source_content.strip(),
        },
    }
    await db.table("artifacts").insert(
        {
            "id": artifact_id,
            "organization_id": organization_id,
            "created_by": user_id,
            "artifact_code": artifact_code,
            "title": artifact_title,
            "artifact_type": spec.artifact_type.value,
            "audience": spec.audience.value,
            "status": status,
            "approval_status": approval_status,
            "quality_score": quality.get("score", 0),
            "latest_version": 1,
            "source_request": original_request,
            "metadata": metadata,
            "created_at": now,
            "updated_at": now,
        }
    ).execute()
    await db.table("artifact_versions").insert(
        {
            "id": version_id,
            "organization_id": organization_id,
            "artifact_id": artifact_id,
            "version_number": 1,
            "content_markdown": content,
            "quality_snapshot": quality,
            "evidence_snapshot": evidence.model_dump(mode="json"),
            "generation_metadata": metadata["generation"],
            "created_by": user_id,
            "created_at": now,
        }
    ).execute()
    links = [
        {
            "organization_id": organization_id,
            "artifact_id": artifact_id,
            "artifact_version_id": version_id,
            "document_id": item.document_id,
            "chunk_id": item.chunk_id,
            "citation_id": item.citation_id,
            "source_title": item.title,
            "source_version": item.source_version,
            "created_at": now,
        }
        for item in evidence.records
    ]
    if links:
        await db.table("artifact_evidence_links").insert(links).execute()
    await persist_artifact_quality_event(
        quality=quality,
        spec=spec,
        org_id=organization_id,
        user_id=user_id,
        session_id=session_id,
        repair_count=repair_count,
        evidence_count=len(evidence.records),
    )
    return {
        "id": artifact_id,
        "artifact_code": artifact_code,
        "title": artifact_title,
        "artifact_type": spec.artifact_type.value,
        "artifact_label": ARTIFACT_LABELS[spec.artifact_type],
        "status": status,
        "approval_status": approval_status,
        "quality": quality,
        "version_number": 1,
        "requested_formats": spec.requested_formats,
        "verification_items": verification_items,
        "evidence": {
            "count": len(evidence.records),
            "coverage": evidence.coverage,
            "sufficient": evidence.sufficient,
            "missing_topics": evidence.missing_topics,
        },
    }
