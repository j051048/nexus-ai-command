"""LLM-as-judge engine for artifact quality (hybrid scoring).

The deterministic rule evaluator in ``artifact_quality_service`` checks
structure, grounding and freshness.  This module adds the second engine: an
independent LLM review that scores the four product dimensions that rules
cannot measure - evidence fidelity, customer value, logical coherence and
language professionalism - and combines it with the rule score.

The module is intentionally standalone so the feedback loop, SLO reporting
and observability dashboard can reuse it without touching the deep
generation pipeline (which carries its own semantic review).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

LLM_JUDGE_VERSION = "artifact-llm-judge.v1"

# The four product dimensions.  When the upstream model answers in the older
# seven-dimension vocabulary these are mapped via ``_map_legacy_dimensions``.
LLM_JUDGE_DIMENSIONS: tuple[str, ...] = (
    "evidence_fidelity",  # 证据忠实度:关键数据/参数/结论均可溯源
    "customer_value",  # 客户价值:针对具体客户、行业、地区、预算形成可决策结论
    "logical_coherence",  # 逻辑连贯:章节构成完整叙事链、前后一致
    "language_professionalism",  # 语言专业度:术语准确、无凑字、无 AI 腔
)

_JUDGE_SYSTEM_PROMPT = """你是独立的科学仪器交付物质量评审委员会，不参与写作。
请对给定的交付物按四个维度各评 0-100 分：
- evidence_fidelity：文中的关键数据、型号、参数、结论是否都能在提供的证据索引中溯源；虚构或无法溯源即为低分。
- customer_value：是否针对具体客户/行业/地区/预算，给出可决策的选型结论、理由、边界与下一步，而非通用模板。
- logical_coherence：章节之间是否形成完整叙事链，前后是否一致、无重复冲突。
- language_professionalism：术语是否准确、表达是否专业清晰、有无凑字与机械化措辞。

任一维度低于 70 分，或存在虚构事实、答非所问，必须给出 severity=high 的 finding。
严格返回 JSON：{"score": 0-100, "dimensions": {...}, "findings": [...], "strengths": [...]}。
findings 每项含 severity/code/message/repair_instruction/sections。"""


def _parse_json_object(content: str) -> dict[str, Any] | None:
    value = str(content or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.IGNORECASE)
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        match = re.search(r"\{.*\}", value, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except (TypeError, ValueError):
            return None
    return parsed if isinstance(parsed, dict) else None


def _clamp_score(raw: Any) -> float:
    try:
        return max(0.0, min(100.0, float(raw)))
    except (TypeError, ValueError):
        return 0.0


def _map_legacy_dimensions(dimensions: dict[str, Any]) -> dict[str, float]:
    """Map the older seven-dimension vocabulary onto the four product axes."""
    if "evidence_fidelity" in dimensions:
        return {
            name: _clamp_score(dimensions.get(name)) for name in LLM_JUDGE_DIMENSIONS
        }
    synthesis = _clamp_score(dimensions.get("evidence_synthesis"))
    specificity = _clamp_score(dimensions.get("customer_specificity"))
    usefulness = _clamp_score(dimensions.get("decision_usefulness"))
    coherence = _clamp_score(dimensions.get("section_coherence"))
    writing = _clamp_score(dimensions.get("writing_quality"))
    return {
        "evidence_fidelity": synthesis,
        "customer_value": round((specificity + usefulness) / 2, 2),
        "logical_coherence": coherence,
        "language_professionalism": writing,
    }


def normalize_llm_judge(value: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize a raw LLM judge response into a stable contract."""
    if not isinstance(value, dict) or not isinstance(value.get("dimensions"), dict):
        return {
            "evaluator_version": LLM_JUDGE_VERSION,
            "score": 0.0,
            "passed": False,
            "dimensions": {name: 0.0 for name in LLM_JUDGE_DIMENSIONS},
            "findings": [
                {
                    "severity": "high",
                    "code": "llm_judge_unavailable",
                    "message": "LLM 评审未完成，不能确认交付物达到精品标准",
                    "repairable": True,
                    "repair_instruction": "重新执行评审阶段",
                    "sections": [],
                }
            ],
            "strengths": [],
        }
    dimensions = _map_legacy_dimensions(value.get("dimensions") or {})
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
                "code": str(item.get("code") or "llm_quality_issue")[:80],
                "message": str(item.get("message"))[:500],
                "repairable": bool(item.get("repairable", True)),
                "repair_instruction": str(item.get("repair_instruction") or "")[:1000],
                "sections": list(item.get("sections") or [])[:8],
            }
        )
    low_dimensions = [name for name, dim_score in dimensions.items() if dim_score < 70]
    if low_dimensions and not any(item["severity"] == "high" for item in findings):
        findings.append(
            {
                "severity": "high",
                "code": "llm_dimensions_below_floor",
                "message": "交付物在证据忠实度、客户价值、逻辑或语言维度未达外发标准",
                "repairable": True,
                "repair_instruction": "针对低分维度重写相关章节并补充证据",
                "sections": [],
            }
        )
    passed = score >= 80 and not any(item["severity"] == "high" for item in findings)
    return {
        "evaluator_version": LLM_JUDGE_VERSION,
        "score": score,
        "passed": passed,
        "dimensions": dimensions,
        "findings": findings,
        "strengths": list(value.get("strengths") or [])[:5],
    }


async def evaluate_artifact_with_llm(
    *,
    text: str,
    spec: Any,
    evidence_packet: dict[str, Any] | None,
    original_request: str,
    customer_context: dict[str, Any] | None,
    organization_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    """Run the independent LLM judge.  Returns None on any failure so callers
    can fall back to the deterministic rule score (never blocks delivery)."""
    try:
        from app.services.llm_gateway import llm_gateway

        response = await llm_gateway.chat(
            scene_code="artifact_llm_judge",
            agent_code="scientific_artifact_quality_judge",
            user_id=user_id,
            org_id=organization_id,
            system_prompt=_JUDGE_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "original_request": original_request,
                            "customer_context": customer_context or {},
                            "artifact_contract": (
                                spec.model_dump(mode="json")
                                if hasattr(spec, "model_dump")
                                else dict(spec or {})
                            ),
                            "evidence_index": [
                                {
                                    "citation_id": item.get("citation_id"),
                                    "title": item.get("title"),
                                    "excerpt": str(item.get("excerpt") or "")[:500],
                                }
                                for item in (evidence_packet or {}).get("records", [])
                            ],
                            "artifact_markdown": text,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            ],
            temperature=0,
            max_tokens=2400,
        )
        if response.finish_reason == "error":
            logger.warning("[LLMJudge] judge call failed, degrading to rule-only")
            return None
        return normalize_llm_judge(_parse_json_object(response.content))
    except Exception as exc:  # broad-except: intentional
        logger.warning("[LLMJudge] judge unavailable (%s); rule score used", exc)
        return None


def combine_rule_and_llm(
    rule_result: dict[str, Any],
    llm_result: dict[str, Any] | None,
    *,
    external_delivery: bool,
) -> dict[str, Any]:
    """Combine deterministic rule score with the LLM judge score."""
    if not llm_result or not llm_result.get("dimensions"):
        return {**rule_result, "judge": None}
    rule_weight = 0.5 if external_delivery else 0.6
    llm_weight = 1.0 - rule_weight
    combined_score = round(
        float(rule_result.get("score") or 0) * rule_weight
        + float(llm_result.get("score") or 0) * llm_weight,
        2,
    )
    dimensions = dict(rule_result.get("dimensions") or {})
    dimensions.update(
        {f"llm_{key}": value for key, value in llm_result["dimensions"].items()}
    )
    findings = [
        *list(rule_result.get("findings") or []),
        *list(llm_result.get("findings") or []),
    ]
    ready = bool(rule_result.get("ready")) and bool(llm_result.get("passed"))
    return {
        **rule_result,
        "score": combined_score,
        "ready": ready,
        "dimensions": dimensions,
        "findings": findings,
        "metrics": {
            **dict(rule_result.get("metrics") or {}),
            "semantic_score": float(llm_result.get("score") or 0),
            "semantic_passed": bool(llm_result.get("passed")),
        },
        "judge": {
            "evaluator_version": llm_result.get("evaluator_version"),
            "score": llm_result.get("score"),
            "passed": llm_result.get("passed"),
            "strengths": llm_result.get("strengths", []),
        },
    }


async def evaluate_delivery_package(
    *,
    text: str,
    spec: Any,
    evidence_packet: dict[str, Any] | None,
    original_request: str,
    customer_context: dict[str, Any] | None,
    organization_id: str,
    user_id: str,
    llm_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One-shot quality gate: deterministic rules + format lint + delivery
    safety scan + (best-effort) LLM judge.

    The LLM judge is best-effort: when it is unavailable the deterministic
    engines still produce a usable verdict.  This is the intended integration
    point for generation pipelines that want the full quality platform.
    """
    from app.services.artifact_delivery_scan import scan_delivery_safety
    from app.services.artifact_format_lint import lint_markdown_format
    from app.services.artifact_quality_service import evaluate_text_artifact

    rule_result = evaluate_text_artifact(text, spec, evidence_packet)
    format_result = lint_markdown_format(text)
    safety_result = scan_delivery_safety(text)

    # Merge deterministic findings into the rule result.
    merged_findings = [
        *list(rule_result.get("findings") or []),
        *list(format_result.get("findings") or []),
        *list(safety_result.get("findings") or []),
    ]
    merged = {
        **rule_result,
        "findings": merged_findings,
        "dimensions": {
            **dict(rule_result.get("dimensions") or {}),
            "format_score": format_result["score"],
            "delivery_safety_score": safety_result["score"],
        },
        "metrics": {
            **dict(rule_result.get("metrics") or {}),
            "format_score": format_result["score"],
            "delivery_safety_score": safety_result["score"],
        },
    }
    if format_result["findings"] or safety_result["findings"]:
        merged["ready"] = False

    if llm_result is None:
        llm_result = await evaluate_artifact_with_llm(
            text=text,
            spec=spec,
            evidence_packet=evidence_packet,
            original_request=original_request,
            customer_context=customer_context,
            organization_id=organization_id,
            user_id=user_id,
        )
    elif "evidence_fidelity" not in dict(llm_result.get("dimensions") or {}):
        # The deep generation pipeline uses a richer seven-dimension judge.
        # Normalize it here so every delivery path shares one final contract
        # without paying for a second LLM review.
        llm_result = normalize_llm_judge(llm_result)
    combined = combine_rule_and_llm(
        merged,
        llm_result,
        external_delivery=bool(
            getattr(spec, "external_delivery", False)
            or getattr(spec, "requires_quality_gate", False)
        ),
    )
    combined["format_lint"] = format_result
    combined["delivery_scan"] = safety_result
    return combined
