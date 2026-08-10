"""End-to-end generation pipeline for durable, evidence-grounded artifacts."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
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
from app.services.artifact_content_sanitizer import (
    contains_internal_markers,
    sanitize_artifact_content,
)
from app.services.artifact_evidence_compiler import compile_artifact_evidence
from app.services.artifact_llm_judge import evaluate_delivery_package
from app.services.artifact_quality_service import (
    evaluate_text_artifact,
    persist_artifact_quality_event,
)
from app.services.artifact_template_service import (
    build_template_system_prompt,
    get_optimal_template,
    record_template_usage,
)
from app.services.llm_gateway import llm_gateway

ARTIFACT_PIPELINE_VERSION = "artifact-pipeline.v3"
DEEP_ORCHESTRATION_VERSION = "artifact-deep-orchestration.v1"
SEMANTIC_DIMENSIONS = (
    "instruction_following",
    "customer_specificity",
    "evidence_synthesis",
    "decision_usefulness",
    "writing_quality",
    "section_coherence",
    "visual_structure",
)
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

ProgressCallback = Callable[[str, int, dict[str, Any]], Awaitable[None]]


class ArtifactGenerationCancelledError(RuntimeError):
    """Raised by a durable job callback when the user requests cancellation."""


async def _emit_progress(
    callback: ProgressCallback | None,
    stage: str,
    progress: int,
    details: dict[str, Any] | None = None,
) -> None:
    if callback:
        await callback(stage, max(0, min(100, progress)), details or {})


def _apply_template_to_spec(
    spec: ArtifactSpec, template: dict[str, Any] | None
) -> ArtifactSpec:
    """Merge a curated skeleton without dropping mandatory skill sections."""

    template_sections = [
        str(item).strip()
        for item in (template or {}).get("sections", [])
        if str(item).strip()
    ]
    if not template_sections:
        return spec
    merged_sections = list(dict.fromkeys([*template_sections, *spec.required_sections]))
    return spec.model_copy(update={"required_sections": merged_sections[:18]})


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


def _clean_title_candidate(value: Any) -> str:
    title = re.sub(r"^[#>*_`\s]+|[#>*_`\s]+$", "", str(value or "")).strip()
    title = re.sub(r"[\\/:*?\"<>|]+", " ", title)
    title = re.sub(r"\s+", " ", title)[:120].strip()
    if (
        len(title) < 6
        or contains_internal_markers(title)
        or re.search(
            r"load[_ -]?knowledge|tool|检索结果|企业资料$|^AI(?:生成)?成果$|"
            r"^专业报告$|^客户解决方案$|非常抱歉|无法完成|未(?:检索|找到)",
            title,
            re.I,
        )
    ):
        return ""
    return title


def _resolve_artifact_title(
    *,
    requested_title: str | None,
    generated_title: Any,
    spec: ArtifactSpec,
    customer_context: dict[str, Any],
) -> str:
    for candidate in (requested_title, generated_title):
        cleaned = _clean_title_candidate(candidate)
        if cleaned:
            return cleaned
    customer = _clean_title_candidate(customer_context.get("customer_name"))
    label = ARTIFACT_LABELS[spec.artifact_type]
    if customer:
        return f"{customer}{label}"
    return f"{label}-{datetime.now(UTC):%Y%m%d}"


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


def _evidence_payload(
    evidence: EvidencePacket,
    citation_ids: list[str] | None = None,
    *,
    limit: int = 16,
) -> list[dict[str, Any]]:
    requested = set(citation_ids or [])
    records = [
        item
        for item in evidence.records
        if not requested or item.citation_id in requested
    ]
    if not records:
        records = evidence.records
    return [
        {
            "citation_id": item.citation_id,
            "title": item.title,
            "doc_type": item.doc_type,
            "source_version": item.source_version,
            "purposes": item.purposes,
            "excerpt": item.excerpt[:1600],
        }
        for item in records[:limit]
    ]


def _merge_usage(responses: list[Any]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for response in responses:
        usage = getattr(response, "usage", None) or {}
        for key, value in usage.items():
            if isinstance(value, int):
                totals[key] = totals.get(key, 0) + value
    return totals


def _merge_usage_values(*usages: dict[str, Any] | None) -> dict[str, int]:
    totals: dict[str, int] = {}
    for usage in usages:
        for key, value in (usage or {}).items():
            if isinstance(value, int):
                totals[key] = totals.get(key, 0) + value
    return totals


def _record_generation_stage(
    generation: dict[str, Any], stage: str, response: Any | None = None
) -> None:
    stages = list(generation.get("stages") or [])
    stages.append(stage)
    generation["stages"] = list(dict.fromkeys(stages))
    generation["stage_count"] = int(generation.get("stage_count") or 0) + 1
    if response is None:
        return
    generation["usage"] = _merge_usage_values(
        generation.get("usage"), getattr(response, "usage", None)
    )
    model = str(getattr(response, "model_code", "") or "")
    current_models = [
        item for item in str(generation.get("model") or "").split(",") if item
    ]
    if model and model not in current_models:
        current_models.append(model)
    generation["model"] = ",".join(current_models)
    if getattr(response, "finish_reason", None) == "error":
        generation["degraded"] = True


def _plain_character_count(value: Any) -> int:
    return len(re.sub(r"[#|>*_`\s]", "", str(value or "")))


def _markdown_table_count(value: Any) -> int:
    return len(re.findall(r"^\s*\|?\s*:?-{3,}.*\|", str(value or ""), re.M))


def _merge_generated_draft(
    base: dict[str, Any], patch: dict[str, Any]
) -> dict[str, Any]:
    """Merge a critic patch without dropping chapters it did not rewrite."""

    merged = {**base}
    for key in ("title", "executive_summary", "verification_items", "source_analysis"):
        if patch.get(key) is not None:
            merged[key] = patch[key]

    existing = {
        str(item.get("title") or "").strip(): item
        for item in (base.get("sections") or [])
        if isinstance(item, dict) and item.get("title")
    }
    order = list(existing)
    for item in patch.get("sections") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        if title not in existing:
            order.append(title)
        existing[title] = {**existing.get(title, {}), **item, "title": title}
    merged["sections"] = [existing[title] for title in order]
    return merged


def _section_deficits(
    *,
    sections: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    minimum_characters: int,
) -> list[dict[str, Any]]:
    by_title = {
        str(item.get("title") or "").strip(): item
        for item in sections
        if isinstance(item, dict) and item.get("title")
    }
    deficits: list[dict[str, Any]] = []
    for plan in plans:
        title = str(plan.get("title") or "").strip()
        current = by_title.get(title) or {}
        character_count = _plain_character_count(current.get("content"))
        table_count = _markdown_table_count(current.get("content"))
        needs_table = bool(plan.get("use_table"))
        if character_count >= minimum_characters and (not needs_table or table_count):
            continue
        deficits.append(
            {
                **plan,
                "current_content": str(current.get("content") or ""),
                "current_evidence_refs": current.get("evidence_refs") or [],
                "deficit": {
                    "character_count": character_count,
                    "minimum_characters": minimum_characters,
                    "table_required": needs_table,
                    "table_count": table_count,
                },
            }
        )
    return deficits


async def _rewrite_section_batch(
    *,
    plans: list[dict[str, Any]],
    original_request: str,
    customer_context: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
    organization_id: str,
    user_id: str,
    minimum_characters: int,
    target_characters: int,
) -> tuple[list[dict[str, Any]], Any]:
    refs = list(
        dict.fromkeys(
            str(ref)
            for plan in plans
            for ref in (
                list(plan.get("evidence_refs") or [])
                + list(plan.get("current_evidence_refs") or [])
            )
            if str(ref).startswith("EVID:")
        )
    )
    response = await llm_gateway.chat(
        scene_code="artifact_section_rewrite",
        agent_code="scientific_artifact_editor",
        user_id=user_id,
        org_id=organization_id,
        system_prompt=f"""你是科学仪器企业的首席方案总编，负责补全不合格章节。
逐章重写，而不是追加空泛文字。每章正文不得少于 {minimum_characters} 个汉字，
目标 {target_characters} 个汉字；必须回答客户问题、比较证据、给出结论和下一步动作。
标记 use_table=true 的章节必须包含结构完整的 Markdown 表格。
只可使用 evidence_cards；缺少依据的参数、案例、政策、价格、交期和承诺写“待核验”。
严格返回 JSON {{"sections": [...]}}，章节 title 必须原样返回。

{build_writing_skill_prompt(spec)}""",
        messages=[
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "original_request": original_request,
                        "customer_context": customer_context,
                        "sections_to_rewrite": plans,
                        "evidence_cards": _evidence_payload(evidence, refs, limit=18),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            }
        ],
        temperature=0.08,
        max_tokens=min(4600, max(2200, target_characters * len(plans) * 2)),
    )
    parsed = (
        _parse_json_object(response.content)
        if response.finish_reason != "error"
        else None
    )
    sections = parsed.get("sections") if isinstance(parsed, dict) else None
    return (sections if isinstance(sections, list) else []), response


def _fallback_plan(
    *,
    original_request: str,
    customer_context: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
) -> dict[str, Any]:
    customer = str(customer_context.get("customer_name") or "").strip()
    label = ARTIFACT_LABELS[spec.artifact_type]
    title = f"{customer}{label}" if customer else label
    refs = [item.citation_id for item in evidence.records]
    plans = []
    for index, section_title in enumerate(spec.required_sections):
        plans.append(
            {
                "title": section_title,
                "objective": f"围绕{section_title}形成有证据的分析、结论与行动建议",
                "key_points": [],
                "evidence_refs": refs[index :: max(1, len(spec.required_sections))][:3],
                "use_table": any(
                    marker in section_title
                    for marker in ("矩阵", "配置", "参数", "对比", "实施", "计划")
                ),
            }
        )
    return {
        "title": title,
        "executive_summary": (
            "本成果基于企业已授权资料，围绕客户目标、推荐配置、技术证据、"
            "实施交付与风险边界形成可供人工审核的完整方案。"
        ),
        "source_analysis": [],
        "section_plan": plans,
        "verification_items": ["价格、交期、案例授权与对外承诺须由负责人确认"],
        "request_excerpt": original_request[:300],
    }


def _fallback_strategy(
    *,
    original_request: str,
    customer_context: dict[str, Any],
    spec: ArtifactSpec,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    customer = str(customer_context.get("customer_name") or "目标客户").strip()
    scenario = str(
        customer_context.get("application_scenario")
        or customer_context.get("industry")
        or "客户实际应用场景"
    ).strip()
    return {
        "audience_profile": f"{customer}的技术、业务与采购决策相关人员",
        "decision_thesis": (
            f"围绕{scenario}，以可核验证据说明需求、推荐配置、实施路径、"
            "验收方式和风险边界，使客户能够据此推进下一步决策。"
        ),
        "instruction_checklist": [
            original_request[:500],
            f"正文不少于 {spec.minimum_character_count} 字",
            f"至少 {spec.minimum_table_count} 个有业务意义的表格",
            "每个关键事实均可追溯到企业资料",
        ],
        "differentiation_axes": [
            "客户需求与产品能力匹配度",
            "可核验的参数与应用证据",
            "实施、验收和服务闭环",
        ],
        "narrative_flow": list(spec.required_sections),
        "chapter_guidance": analysis.get("section_plan") or [],
        "prohibited_shortcuts": [
            "复制聊天回答或资料原文",
            "用通用营销话术替代客户化分析",
            "把待核验信息写成确定事实",
            "重复同一段落凑字数",
        ],
    }


async def _develop_delivery_strategy(
    *,
    original_request: str,
    customer_context: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
    analysis: dict[str, Any],
    template_prompt: str,
    organization_id: str,
    user_id: str,
) -> tuple[dict[str, Any], Any]:
    """Turn the evidence inventory into a customer-specific editorial strategy."""

    fallback = _fallback_strategy(
        original_request=original_request,
        customer_context=customer_context,
        spec=spec,
        analysis=analysis,
    )
    response = await llm_gateway.chat(
        scene_code="artifact_delivery_strategy",
        agent_code="scientific_solution_strategist",
        user_id=user_id,
        org_id=organization_id,
        system_prompt=f"""你是科学仪器企业的首席售前策略师。你的任务不是写正文，
而是把客户指令和企业证据转化为一份可执行的交付策略。

必须完成：
1. 逐条提取用户的显式与隐式要求，形成 instruction_checklist。
2. 明确客户决策者、核心问题、方案主张、差异化依据和下一步决策动作。
3. 为每章规定必须回答的问题、应引用的证据和禁止出现的空泛内容。
4. 发现资料冲突时保留冲突，不得自行挑选更漂亮的参数。
5. 严格返回 JSON；不得撰写最终方案正文。

{build_writing_skill_prompt(spec)}

{template_prompt}""",
        messages=[
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "original_request": original_request,
                        "customer_context": customer_context,
                        "source_analysis": analysis.get("source_analysis") or [],
                        "section_plan": analysis.get("section_plan") or [],
                        "verification_items": analysis.get("verification_items") or [],
                        "evidence_cards": _evidence_payload(evidence, limit=24),
                        "output_schema": fallback,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            }
        ],
        temperature=0.05,
        max_tokens=2600,
    )
    parsed = (
        _parse_json_object(response.content)
        if response.finish_reason != "error"
        else None
    )
    if not parsed or not isinstance(parsed.get("instruction_checklist"), list):
        return fallback, response
    return {**fallback, **parsed}, response


async def _analyze_evidence(
    *,
    original_request: str,
    source_content: str,
    customer_context: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
    template_prompt: str,
    organization_id: str,
    user_id: str,
) -> tuple[dict[str, Any], Any]:
    system_prompt = f"""你是科学仪器企业的首席售前资料分析师。
先拆解企业资料，再规划成果；此阶段不要写最终正文。

规则：
1. 识别客户需求、产品能力、参数、政策、竞品、案例、实施和服务事实。
2. 合并重复信息；发现冲突时列入 conflicts，不得自行选择看似更好的数字。
3. 每个事实与章节计划必须绑定真实 citation_id；证据不足写入 missing_facts。
4. 标题必须是客户可理解的正式成果名，禁止使用 loadknowledge、工具名、文件名或系统术语。
5. 严格返回 JSON，不要代码围栏。

{build_writing_skill_prompt(spec)}

{template_prompt}
"""
    payload = {
        "original_request": original_request,
        "customer_context": customer_context,
        "existing_answer_as_user_intent_only": source_content[:5000],
        "artifact_spec": spec.model_dump(mode="json"),
        "evidence_cards": _evidence_payload(evidence, limit=24),
        "output_schema": {
            "title": "正式、具体、面向客户的成果标题",
            "executive_summary": "200-350字，说明目标、方案主线、价值和边界",
            "source_analysis": [
                {
                    "theme": "需求|产品|参数|政策|竞品|案例|实施|服务",
                    "findings": ["经过归并的事实"],
                    "evidence_refs": ["EVID:document_id:chunk_id"],
                    "conflicts": [],
                    "missing_facts": [],
                }
            ],
            "section_plan": [
                {
                    "title": "必须严格匹配 required_sections",
                    "objective": "本章要回答的客户问题",
                    "key_points": ["分析要点"],
                    "evidence_refs": ["EVID:document_id:chunk_id"],
                    "use_table": True,
                }
            ],
            "verification_items": ["需要人工确认的事实与承诺"],
        },
    }
    response = await llm_gateway.chat(
        scene_code="artifact_evidence_analysis",
        agent_code="scientific_evidence_analyst",
        user_id=user_id,
        org_id=organization_id,
        system_prompt=system_prompt,
        messages=[
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, default=str),
            }
        ],
        temperature=0,
        max_tokens=2200,
    )
    parsed = (
        _parse_json_object(response.content)
        if response.finish_reason != "error"
        else None
    )
    fallback = _fallback_plan(
        original_request=original_request,
        customer_context=customer_context,
        spec=spec,
        evidence=evidence,
    )
    if not parsed:
        return fallback, response
    by_title = {
        str(item.get("title") or "").strip(): item
        for item in (parsed.get("section_plan") or [])
        if isinstance(item, dict)
    }
    parsed["section_plan"] = [
        by_title.get(title)
        or next(item for item in fallback["section_plan"] if item["title"] == title)
        for title in spec.required_sections
    ]
    return parsed, response


async def _generate_section_batch(
    *,
    plans: list[dict[str, Any]],
    original_request: str,
    customer_context: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
    strategy: dict[str, Any],
    template_prompt: str,
    organization_id: str,
    user_id: str,
    section_target: int,
) -> tuple[list[dict[str, Any]], Any]:
    refs = list(
        dict.fromkeys(
            str(ref)
            for plan in plans
            for ref in (plan.get("evidence_refs") or [])
            if str(ref).startswith("EVID:")
        )
    )
    system_prompt = f"""你是科学仪器企业的资深售前方案作者。
根据资料分析计划撰写指定章节，不要输出标题之外的闲聊。

硬性规则：
1. 每章正文不得少于 {section_target} 个汉字，必须包含事实归纳、客户化分析、结论和下一步动作，禁止只写提纲。
2. 仅使用 evidence_cards；参数、政策、竞品、案例、价格、交期和承诺必须有 evidence_refs，否则写“待核验”。
3. use_table=true 时必须在 content 中生成结构完整的 Markdown 表格。
4. 引用标记只放在 evidence_refs，必要时也可放在相应事实句末；不得输出检索过程或工具名。
5. 不复制资料原文，必须综合多个片段后重写。
6. 必须服从 delivery_strategy 的客户主张、差异化逻辑和逐章要求；不得写成通用产品介绍。
7. 严格返回 JSON {{"sections": [...]}}，不要代码围栏。

{build_writing_skill_prompt(spec)}

{template_prompt}
"""
    payload = {
        "original_request": original_request,
        "customer_context": customer_context,
        "delivery_strategy": strategy,
        "section_target_characters": section_target,
        "section_plans": plans,
        "evidence_cards": _evidence_payload(evidence, refs, limit=16),
        "output_schema": {
            "sections": [
                {
                    "title": "与 section_plans.title 完全一致",
                    "content": "完整正文，可包含 Markdown 表格、短段落和清单",
                    "evidence_refs": ["EVID:document_id:chunk_id"],
                }
            ]
        },
    }
    response = await llm_gateway.chat(
        scene_code="artifact_section_writing",
        agent_code="scientific_artifact_writer",
        user_id=user_id,
        org_id=organization_id,
        system_prompt=system_prompt,
        messages=[
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, default=str),
            }
        ],
        temperature=0.12,
        max_tokens=min(3600, max(1800, section_target * len(plans) * 2)),
    )
    parsed = (
        _parse_json_object(response.content)
        if response.finish_reason != "error"
        else None
    )
    sections = parsed.get("sections") if isinstance(parsed, dict) else None
    return (sections if isinstance(sections, list) else []), response


async def _editorial_polish_batch(
    *,
    plans: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    all_sections: list[dict[str, Any]],
    original_request: str,
    customer_context: dict[str, Any],
    strategy: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
    organization_id: str,
    user_id: str,
    section_target: int,
) -> tuple[list[dict[str, Any]], Any]:
    refs = list(
        dict.fromkeys(
            str(ref)
            for item in [*plans, *sections]
            for ref in (item.get("evidence_refs") or [])
            if str(ref).startswith("EVID:")
        )
    )
    response = await llm_gateway.chat(
        scene_code="artifact_editorial_synthesis",
        agent_code="scientific_artifact_editorial_director",
        user_id=user_id,
        org_id=organization_id,
        system_prompt=f"""你是科学仪器行业客户方案的终审总编。
对指定章节做深度编辑，不是简单润色，也不得缩写成提纲。

编辑目标：
1. 消除章节间重复，把通用描述改成针对本客户、本场景的分析。
2. 保留并强化“客户问题 -> 企业证据 -> 方案判断 -> 交付动作”的逻辑。
3. 参数、政策、竞品、案例和承诺必须保留有效 evidence_refs；无证据改为待核验。
4. 保持章节正文不少于 {max(220, int(section_target * 0.88))} 个汉字，
   不得删除原有有效表格；use_table=true 的章节必须保留业务表格。
5. 服从 original_request 与 delivery_strategy，不增加资料中不存在的型号或事实。
6. 严格返回 JSON {{"sections": [...]}}，title 必须与输入完全一致。

{build_writing_skill_prompt(spec)}""",
        messages=[
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "original_request": original_request,
                        "customer_context": customer_context,
                        "delivery_strategy": strategy,
                        "section_plans": plans,
                        "sections_to_edit": sections,
                        "document_map": [
                            {
                                "title": item.get("title"),
                                "summary": str(item.get("content") or "")[:260],
                            }
                            for item in all_sections
                        ],
                        "evidence_cards": _evidence_payload(evidence, refs, limit=18),
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            }
        ],
        temperature=0.06,
        max_tokens=min(4600, max(2200, section_target * len(sections) * 2)),
    )
    parsed = (
        _parse_json_object(response.content)
        if response.finish_reason != "error"
        else None
    )
    polished = parsed.get("sections") if isinstance(parsed, dict) else None
    return (polished if isinstance(polished, list) else []), response


async def _polish_generated_sections(
    *,
    plans: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    original_request: str,
    customer_context: dict[str, Any],
    strategy: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
    organization_id: str,
    user_id: str,
    section_target: int,
) -> tuple[list[dict[str, Any]], list[Any], int]:
    by_title = {
        str(item.get("title") or "").strip(): item
        for item in sections
        if isinstance(item, dict) and item.get("title")
    }
    plan_batches = [plans[index : index + 3] for index in range(0, len(plans), 3)]
    results = await asyncio.gather(
        *[
            _editorial_polish_batch(
                plans=batch,
                sections=[
                    by_title.get(str(plan.get("title") or "").strip(), {})
                    for plan in batch
                ],
                all_sections=sections,
                original_request=original_request,
                customer_context=customer_context,
                strategy=strategy,
                spec=spec,
                evidence=evidence,
                organization_id=organization_id,
                user_id=user_id,
                section_target=section_target,
            )
            for batch in plan_batches
        ]
    )
    accepted = 0
    responses: list[Any] = []
    for polished_sections, response in results:
        responses.append(response)
        for candidate in polished_sections:
            if not isinstance(candidate, dict):
                continue
            title = str(candidate.get("title") or "").strip()
            original = by_title.get(title)
            if not original:
                continue
            original_content = str(original.get("content") or "")
            candidate_content = str(candidate.get("content") or "")
            minimum_length = max(
                200,
                int(_plain_character_count(original_content) * 0.86),
                int(section_target * 0.82),
            )
            if _plain_character_count(candidate_content) < minimum_length:
                continue
            if _markdown_table_count(candidate_content) < _markdown_table_count(
                original_content
            ):
                continue
            by_title[title] = {
                **original,
                **candidate,
                "title": title,
                "evidence_refs": list(
                    dict.fromkeys(
                        [
                            *list(original.get("evidence_refs") or []),
                            *list(candidate.get("evidence_refs") or []),
                        ]
                    )
                ),
            }
            accepted += 1
    ordered = [by_title.get(str(plan.get("title") or "").strip(), {}) for plan in plans]
    return ordered, responses, accepted


def _normalize_semantic_review(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("dimensions"), dict):
        return {
            "evaluator_version": "artifact-semantic-review.v1",
            "score": 0.0,
            "passed": False,
            "dimensions": {name: 0.0 for name in SEMANTIC_DIMENSIONS},
            "findings": [
                {
                    "severity": "high",
                    "code": "semantic_review_unavailable",
                    "message": "语义质量评审未完成，不能标记为精品成果",
                    "repairable": True,
                    "repair_instruction": "重新执行总编与语义评审阶段",
                }
            ],
            "strengths": [],
        }
    dimensions: dict[str, float] = {}
    for name in SEMANTIC_DIMENSIONS:
        raw = value.get("dimensions", {}).get(name)
        try:
            dimensions[name] = max(0.0, min(100.0, float(raw)))
        except (TypeError, ValueError):
            dimensions[name] = 0.0
    score = round(sum(dimensions.values()) / len(dimensions), 2)
    findings: list[dict[str, Any]] = []
    for item in value.get("findings") or []:
        if not isinstance(item, dict) or not str(item.get("message") or "").strip():
            continue
        severity = str(item.get("severity") or "medium").lower()
        findings.append(
            {
                "severity": (
                    severity if severity in {"low", "medium", "high"} else "medium"
                ),
                "code": str(item.get("code") or "semantic_quality_issue")[:80],
                "message": str(item.get("message"))[:500],
                "repairable": bool(item.get("repairable", True)),
                "repair_instruction": str(item.get("repair_instruction") or "")[:1000],
                "sections": list(item.get("sections") or [])[:8],
            }
        )
    low_dimensions = [
        name for name, dimension_score in dimensions.items() if dimension_score < 75
    ]
    if low_dimensions and not any(item["severity"] == "high" for item in findings):
        findings.append(
            {
                "severity": "high",
                "code": "semantic_dimensions_below_floor",
                "message": "成果在客户化、证据综合或决策价值方面仍未达到精品标准",
                "repairable": True,
                "repair_instruction": "针对低分维度重写相关章节，增加客户化判断和可执行结论",
                "sections": [],
            }
        )
    passed = score >= 85 and not any(item["severity"] == "high" for item in findings)
    return {
        "evaluator_version": "artifact-semantic-review.v1",
        "score": score,
        "passed": passed,
        "dimensions": dimensions,
        "findings": findings,
        "strengths": [str(item)[:300] for item in (value.get("strengths") or [])[:6]],
    }


async def _review_semantic_quality(
    *,
    content: str,
    original_request: str,
    customer_context: dict[str, Any],
    strategy: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
    deterministic_quality: dict[str, Any],
    organization_id: str,
    user_id: str,
) -> tuple[dict[str, Any], Any]:
    response = await llm_gateway.chat(
        scene_code="artifact_semantic_quality_review",
        agent_code="scientific_artifact_quality_judge",
        user_id=user_id,
        org_id=organization_id,
        system_prompt="""你是独立的科学仪器方案质量评审委员会，不参与写作。
请严格判断成果是否真的可交付，而不是因为字数和标题齐全就给高分。

逐项以零到一百分评分：
- instruction_following：是否完整执行用户指令和篇幅/格式要求
- customer_specificity：是否针对具体客户、行业、地区和预算，而非通用模板
- evidence_synthesis：是否真正比较、拆解和综合企业资料，而非堆砌引用
- decision_usefulness：是否有明确选型结论、理由、边界、验收和下一步动作
- writing_quality：是否专业、清晰、无重复凑字和机械化措辞
- section_coherence：章节之间是否形成一条完整叙事链
- visual_structure：表格和清单是否帮助决策，而非仅用于装饰

任一关键维度低于七十五分，或存在虚构事实、明显重复、答非所问，必须给出 high finding。
严格返回 JSON：score 可省略；必须包含 dimensions、findings、strengths。
findings 每项包含 severity、code、message、repair_instruction、sections。""",
        messages=[
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "original_request": original_request,
                        "customer_context": customer_context,
                        "delivery_strategy": strategy,
                        "artifact_contract": spec.model_dump(mode="json"),
                        "deterministic_quality": deterministic_quality,
                        "evidence_index": [
                            {
                                "citation_id": item.citation_id,
                                "title": item.title,
                                "purposes": item.purposes,
                                "excerpt": item.excerpt[:500],
                            }
                            for item in evidence.records
                        ],
                        "artifact_markdown": content,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            }
        ],
        temperature=0,
        max_tokens=2400,
    )
    parsed = (
        _parse_json_object(response.content)
        if response.finish_reason != "error"
        else None
    )
    return _normalize_semantic_review(parsed), response


def _combine_quality_reviews(
    deterministic: dict[str, Any], semantic: dict[str, Any]
) -> dict[str, Any]:
    combined = {**deterministic}
    dimensions = dict(deterministic.get("dimensions") or {})
    dimensions.update(
        {f"semantic_{key}": value for key, value in semantic["dimensions"].items()}
    )
    findings = [
        *list(deterministic.get("findings") or []),
        *list(semantic.get("findings") or []),
    ]
    combined_score = round(
        float(deterministic.get("score") or 0) * 0.6
        + float(semantic.get("score") or 0) * 0.4,
        2,
    )
    combined.update(
        {
            "score": combined_score,
            "ready": bool(deterministic.get("ready"))
            and bool(semantic.get("passed"))
            and combined_score >= 85,
            "dimensions": dimensions,
            "findings": findings,
            "metrics": {
                **dict(deterministic.get("metrics") or {}),
                "semantic_score": semantic.get("score"),
                "semantic_passed": semantic.get("passed"),
            },
            "semantic_review": semantic,
            "repair_guidance": "；".join(
                str(item.get("repair_instruction") or item.get("message") or "")
                for item in findings
                if item.get("repairable", True)
            )[:3000],
        }
    )
    return combined


async def _generate_draft(
    *,
    original_request: str,
    source_content: str,
    customer_context: dict[str, Any],
    spec: ArtifactSpec,
    evidence: EvidencePacket,
    template_prompt: str,
    organization_id: str,
    user_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    analysis, analysis_response = await _analyze_evidence(
        original_request=original_request,
        source_content=source_content,
        customer_context=customer_context,
        spec=spec,
        evidence=evidence,
        template_prompt=template_prompt,
        organization_id=organization_id,
        user_id=user_id,
    )
    strategy, strategy_response = await _develop_delivery_strategy(
        original_request=original_request,
        customer_context=customer_context,
        spec=spec,
        evidence=evidence,
        analysis=analysis,
        template_prompt=template_prompt,
        organization_id=organization_id,
        user_id=user_id,
    )
    plans = [
        item for item in (analysis.get("section_plan") or []) if isinstance(item, dict)
    ]
    if not plans:
        plans = _fallback_plan(
            original_request=original_request,
            customer_context=customer_context,
            spec=spec,
            evidence=evidence,
        )["section_plan"]
    # Generate with headroom because models commonly undershoot requested Chinese
    # character counts and Markdown syntax is excluded by the quality gate.
    generation_target = int(spec.target_character_count * 1.12)
    summary_budget = min(380, max(240, int(generation_target * 0.09)))
    section_target = max(
        240,
        int((generation_target - summary_budget) / max(1, len(plans))),
    )
    batches = [plans[index : index + 3] for index in range(0, len(plans), 3)]
    results = await asyncio.gather(
        *[
            _generate_section_batch(
                plans=batch,
                original_request=original_request,
                customer_context=customer_context,
                spec=spec,
                evidence=evidence,
                strategy=strategy,
                template_prompt=template_prompt,
                organization_id=organization_id,
                user_id=user_id,
                section_target=section_target,
            )
            for batch in batches
        ]
    )
    sections: list[dict[str, Any]] = []
    responses = [analysis_response, strategy_response]
    for batch_sections, response in results:
        sections.extend(item for item in batch_sections if isinstance(item, dict))
        responses.append(response)

    # One targeted rewrite pass is cheaper and more reliable than asking a
    # single critic to regenerate the whole document after truncation.
    section_minimum = max(200, int(section_target * 0.88))
    deficits = _section_deficits(
        sections=sections,
        plans=plans,
        minimum_characters=section_minimum,
    )
    if deficits:
        rewrite_results = await asyncio.gather(
            *[
                _rewrite_section_batch(
                    plans=deficits[index : index + 2],
                    original_request=original_request,
                    customer_context=customer_context,
                    spec=spec,
                    evidence=evidence,
                    organization_id=organization_id,
                    user_id=user_id,
                    minimum_characters=section_minimum,
                    target_characters=section_target,
                )
                for index in range(0, len(deficits), 2)
            ]
        )
        replacements: dict[str, dict[str, Any]] = {}
        for rewritten, response in rewrite_results:
            responses.append(response)
            for item in rewritten:
                title = str(item.get("title") or "").strip()
                if title:
                    replacements[title] = item
        sections = [
            replacements.get(str(item.get("title") or "").strip(), item)
            for item in sections
        ]
        existing_titles = {str(item.get("title") or "").strip() for item in sections}
        sections.extend(
            item for title, item in replacements.items() if title not in existing_titles
        )

    polished_sections, editorial_responses, editorial_accept_count = (
        await _polish_generated_sections(
            plans=plans,
            sections=sections,
            original_request=original_request,
            customer_context=customer_context,
            strategy=strategy,
            spec=spec,
            evidence=evidence,
            organization_id=organization_id,
            user_id=user_id,
            section_target=section_target,
        )
    )
    responses.extend(editorial_responses)
    if any(item.get("title") for item in polished_sections):
        sections = polished_sections
    by_title = {
        str(item.get("title") or "").strip(): item
        for item in sections
        if item.get("title")
    }
    ordered = []
    for plan in plans:
        section_title = str(plan.get("title") or "").strip()
        ordered.append(
            by_title.get(section_title)
            or {
                "title": section_title,
                "content": "待核验：本章节生成未完成，请补充资料后重新生成。",
                "evidence_refs": [],
            }
        )
    parsed = {
        "title": analysis.get("title"),
        "executive_summary": analysis.get("executive_summary"),
        "sections": ordered,
        "verification_items": analysis.get("verification_items") or [],
        "source_analysis": analysis.get("source_analysis") or [],
        "delivery_strategy": strategy,
    }
    models = list(
        dict.fromkeys(
            str(getattr(response, "model_code", "") or "")
            for response in responses
            if getattr(response, "model_code", None)
        )
    )
    return parsed, {
        "model": models[0] if len(models) == 1 else ",".join(models),
        "usage": _merge_usage(responses),
        "degraded": any(
            getattr(response, "finish_reason", None) == "error"
            for response in responses
        )
        or len(by_title) < len(plans),
        "stage_count": len(responses),
        "source_analysis_count": len(parsed["source_analysis"]),
        "section_rewrite_count": len(deficits),
        "editorial_accept_count": editorial_accept_count,
        "orchestration_version": DEEP_ORCHESTRATION_VERSION,
        "stages": [
            "evidence_analysis",
            "delivery_strategy",
            "section_writing",
            "targeted_section_rewrite",
            "editorial_synthesis",
        ],
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
    target_character_count: int | None = None,
    generation_mode: str = "deep",
    session_id: str | None = None,
    review_confirmed: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run the deep delivery orchestration and persist one durable version."""

    overrides: dict[str, Any] = {
        "audience": audience,
        "requested_formats": requested_formats or ["docx", "pdf"],
        "external_delivery": str(audience) != ArtifactAudience.INTERNAL.value,
        "strict_quality": True,
    }
    if artifact_type:
        overrides["artifact_type"] = artifact_type
    if target_character_count:
        overrides["target_character_count"] = target_character_count
        overrides["minimum_character_count"] = target_character_count
    normalized_context = dict(customer_context or {})
    spec = enrich_artifact_spec(
        infer_artifact_spec(f"{original_request}\n{source_content[:1000]}", overrides)
    )
    spec = spec.model_copy(
        update={
            "instrument_line": spec.instrument_line
            or normalized_context.get("instrument_line")
            or normalized_context.get("instrument_line_code"),
            "industry": spec.industry or normalized_context.get("industry"),
            "region": spec.region or normalized_context.get("region"),
        }
    )
    template = await get_optimal_template(
        db,
        organization_id=organization_id,
        artifact_type=spec.artifact_type.value,
        instrument_line=spec.instrument_line,
        industry=spec.industry,
    )
    spec = _apply_template_to_spec(spec, template)
    template_prompt = build_template_system_prompt(template, spec)
    await _emit_progress(
        progress_callback,
        "template_selection",
        8,
        {"template_key": (template or {}).get("template_key")},
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
    await _emit_progress(
        progress_callback,
        "evidence_compilation",
        22,
        {
            "evidence_count": len(evidence.records),
            "coverage": evidence.coverage,
            "missing_topics": evidence.missing_topics,
        },
    )
    generated, generation = await _generate_draft(
        original_request=original_request,
        source_content=safe_source,
        customer_context=normalized_context,
        spec=spec,
        evidence=evidence,
        template_prompt=template_prompt,
        organization_id=organization_id,
        user_id=user_id,
    )
    await _emit_progress(
        progress_callback,
        "deep_writing",
        66,
        {"stages": generation.get("stages") or []},
    )
    artifact_title = _resolve_artifact_title(
        requested_title=title,
        generated_title=generated.get("title"),
        spec=spec,
        customer_context=normalized_context,
    )
    content, verification_items = _artifact_markdown(
        title=artifact_title,
        generated=generated,
        spec=spec,
        fallback_source=safe_source,
    )
    deterministic_quality = evaluate_text_artifact(
        content, spec, evidence.model_dump(mode="json")
    )
    semantic_quality, semantic_response = await _review_semantic_quality(
        content=content,
        original_request=original_request,
        customer_context=normalized_context,
        strategy=generated.get("delivery_strategy") or {},
        spec=spec,
        evidence=evidence,
        deterministic_quality=deterministic_quality,
        organization_id=organization_id,
        user_id=user_id,
    )
    _record_generation_stage(generation, "semantic_quality_review", semantic_response)
    quality = await evaluate_delivery_package(
        text=content,
        spec=spec,
        evidence_packet=evidence.model_dump(mode="json"),
        original_request=original_request,
        customer_context=normalized_context,
        organization_id=organization_id,
        user_id=user_id,
        llm_result=semantic_quality,
    )
    quality["semantic_review"] = semantic_quality
    await _emit_progress(
        progress_callback,
        "quality_review",
        78,
        {"score": quality.get("score"), "ready": quality.get("ready")},
    )
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
                + "\n你是最终交付总编。按质量报告修复缺失章节、篇幅不足、空洞段落、"
                "表格不足、重复内容和无效引用。保持真实证据边界，必须达到硬性最低篇幅。"
                "只返回严格 JSON，至少包含 sections；需要时可同时返回 executive_summary。"
            ),
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "draft": generated,
                            "delivery_strategy": generated.get("delivery_strategy")
                            or {},
                            "quality_findings": quality.get("findings") or [],
                            "semantic_review": quality.get("semantic_review") or {},
                            "target_character_count": spec.target_character_count,
                            "minimum_character_count": spec.minimum_character_count,
                            "minimum_table_count": spec.minimum_table_count,
                            "enterprise_evidence": evidence.prompt_context,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            ],
            temperature=0.05,
            max_tokens=6144,
        )
        repaired = (
            _parse_json_object(response.content)
            if response.finish_reason != "error"
            else None
        )
        if not repaired:
            break
        _record_generation_stage(generation, f"quality_repair_{repair_count}", response)
        generated = _merge_generated_draft(generated, repaired)
        content, verification_items = _artifact_markdown(
            title=artifact_title,
            generated=generated,
            spec=spec,
            fallback_source=safe_source,
        )
        deterministic_quality = evaluate_text_artifact(
            content, spec, evidence.model_dump(mode="json")
        )
        semantic_quality, semantic_response = await _review_semantic_quality(
            content=content,
            original_request=original_request,
            customer_context=normalized_context,
            strategy=generated.get("delivery_strategy") or {},
            spec=spec,
            evidence=evidence,
            deterministic_quality=deterministic_quality,
            organization_id=organization_id,
            user_id=user_id,
        )
        _record_generation_stage(
            generation,
            f"semantic_quality_review_after_repair_{repair_count}",
            semantic_response,
        )
        quality = await evaluate_delivery_package(
            text=content,
            spec=spec,
            evidence_packet=evidence.model_dump(mode="json"),
            original_request=original_request,
            customer_context=normalized_context,
            organization_id=organization_id,
            user_id=user_id,
            llm_result=semantic_quality,
        )
        quality["semantic_review"] = semantic_quality
        await _emit_progress(
            progress_callback,
            "quality_repair",
            min(90, 78 + repair_count * 6),
            {
                "repair_count": repair_count,
                "score": quality.get("score"),
                "ready": quality.get("ready"),
            },
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
        "generation_mode": generation_mode,
        "orchestration_version": DEEP_ORCHESTRATION_VERSION,
        "artifact_label": ARTIFACT_LABELS[spec.artifact_type],
        "session_id": session_id,
        "requested_formats": spec.requested_formats,
        "customer_context": customer_context or {},
        "selected_document_ids": selected_document_ids or [],
        "template": {
            "template_key": (template or {}).get("template_key"),
            "version": (template or {}).get("version"),
            "instrument_line": (template or {}).get("instrument_line"),
            "industry": (template or {}).get("industry"),
        },
        "content_contract": {
            "target_character_count": spec.target_character_count,
            "minimum_character_count": spec.minimum_character_count,
            "minimum_table_count": spec.minimum_table_count,
        },
        "generation": {**generation, "repair_count": repair_count},
        "verification_items": verification_items,
        "sanitization": {
            "source_was_sanitized": safe_source != source_content.strip(),
        },
    }
    await _emit_progress(
        progress_callback,
        "persistence",
        94,
        {"quality_score": quality.get("score"), "ready": quality.get("ready")},
    )
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
        template_key=(template or {}).get("template_key"),
        judge_snapshot=quality.get("judge") or semantic_quality,
    )
    if template and template.get("template_key"):
        await record_template_usage(
            db,
            organization_id=organization_id,
            template_key=str(template["template_key"]),
            quality=quality,
        )
    await _emit_progress(
        progress_callback,
        "completed",
        100,
        {"artifact_id": artifact_id, "quality_score": quality.get("score")},
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
        "orchestration": {
            "mode": generation_mode,
            "version": DEEP_ORCHESTRATION_VERSION,
            "stage_count": generation.get("stage_count", 0),
            "stages": generation.get("stages") or [],
            "semantic_score": semantic_quality.get("score", 0),
            "semantic_passed": semantic_quality.get("passed", False),
            "repair_count": repair_count,
        },
    }
