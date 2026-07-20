"""Human-reviewable learning recommendations from solution outcomes."""

from __future__ import annotations

from collections import Counter
from typing import Any


def build_learning_insights(
    projects: list[dict[str, Any]], feedback: list[dict[str, Any]]
) -> dict[str, Any]:
    won = [item for item in projects if item.get("status") == "won"]
    lost = [item for item in projects if item.get("status") == "lost"]
    edited = [item for item in feedback if item.get("change_type") == "edited"]
    rejected = [item for item in feedback if item.get("change_type") == "rejected"]
    winning_lines = Counter(
        str(item.get("instrument_line_code") or "未分类") for item in won
    )
    edited_sections = Counter(
        str(item.get("section_id") or "整份方案") for item in edited
    )
    recommendations: list[dict[str, Any]] = []
    if edited_sections:
        section, count = edited_sections.most_common(1)[0]
        recommendations.append(
            {
                "code": "frequent_manual_edit",
                "title": f"优先复核章节：{section}",
                "reason": f"该章节发生 {count} 次人工改写",
                "action": "review_prompt_or_template",
                "auto_apply": False,
            }
        )
    if lost:
        recommendations.append(
            {
                "code": "lost_case_review",
                "title": "复盘近期丢单方案",
                "reason": f"已有 {len(lost)} 个丢单样本可供人工归因",
                "action": "review_lost_cases",
                "auto_apply": False,
            }
        )
    return {
        "sample_size": len(projects),
        "won": len(won),
        "lost": len(lost),
        "edited": len(edited),
        "rejected": len(rejected),
        "winning_instrument_lines": dict(winning_lines.most_common(5)),
        "recommendations": recommendations,
        "policy": "recommendation_only",
    }
