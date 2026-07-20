"""Evidence-preserving AI rewrite for a single solution section."""

from __future__ import annotations

import json
from typing import Any, Literal


async def rewrite_solution_section(
    *,
    section: dict[str, Any],
    instruction: str,
    mode: Literal["concise", "technical", "executive", "proofread"],
    evidence_catalog: list[dict[str, Any]],
    user_id: str,
    organization_id: str,
) -> dict[str, Any]:
    from app.services.llm_gateway import llm_gateway

    references = set(str(value) for value in section.get("evidence_refs") or [])
    allowed_evidence = [
        item
        for item in evidence_catalog
        if str(item.get("title") or item.get("source") or item.get("document_id"))
        in references
    ]
    response = await llm_gateway.chat(
        scene_code="solution_section_rewrite",
        agent_code="scientific_solution_editor",
        user_id=user_id,
        org_id=organization_id,
        system_prompt=(
            "你是科学仪器售前方案编辑。只改写给定章节，不新增参数、价格、资质或案例。"
            "必须保留原有事实含义和证据编号；证据不足的内容标记为‘待核验’。只返回改写后的正文。"
        ),
        messages=[
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "mode": mode,
                        "instruction": instruction,
                        "section": section,
                        "allowed_evidence": allowed_evidence,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            }
        ],
        temperature=0.1,
        max_tokens=1200,
    )
    if response.finish_reason == "error" or not response.content.strip():
        raise RuntimeError("章节改写服务暂不可用")
    return {
        "section_id": section.get("id"),
        "original_content": section.get("content") or "",
        "revised_content": response.content.strip(),
        "evidence_refs": list(references),
        "model": response.model_code,
        "usage": response.usage,
    }
