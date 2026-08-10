"""Explain whether tenant knowledge can support evidence-grounded delivery."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

CATEGORY_ALIASES = {
    "manual": "product",
    "specification": "product",
    "technical": "product",
    "regulation": "compliance",
    "policy": "compliance",
    "tender": "compliance",
    "proposal": "case",
    "customer_case": "case",
    "service": "service",
    "training": "service",
}

REQUIRED_CATEGORIES = {
    "customer_solution": ["product", "case", "competitor", "service"],
    "tender": ["product", "compliance", "case", "service"],
    "competitor_analysis": ["product", "competitor", "case"],
    "service_proposal": ["product", "service", "case"],
    "technical_report": ["product", "compliance"],
}

CATEGORY_LABELS = {
    "product": "产品参数与手册",
    "competitor": "竞品资料",
    "case": "客户案例与历史方案",
    "compliance": "法规、标准与招标要求",
    "service": "交付、培训与售后条款",
}


def _category(document: dict[str, Any]) -> str:
    raw = str(document.get("doc_type") or document.get("category") or "other").lower()
    return CATEGORY_ALIASES.get(raw, raw)


def score_document(document: dict[str, Any]) -> dict[str, Any]:
    """Score retrieval, governance, freshness and evidence usability."""
    status = str(document.get("status") or "")
    review_status = str(document.get("review_status") or "pending")
    quality = float(document.get("quality_score") or 0)
    valid_until = document.get("valid_until")
    expired = review_status == "expired"
    if valid_until:
        try:
            expired = expired or datetime.fromisoformat(
                str(valid_until).replace("Z", "+00:00")
            ) < datetime.now(UTC)
        except ValueError:
            expired = True
    checks = {
        "indexed": status in {"ready", "completed"} or bool(document.get("indexed_at")),
        "verified": review_status == "verified",
        "fresh": not expired,
        "versioned": bool(document.get("source_version")),
        "quality": quality >= 0.7,
    }
    score = round(
        int(checks["indexed"]) * 30
        + int(checks["verified"]) * 25
        + int(checks["fresh"]) * 15
        + int(checks["versioned"]) * 10
        + min(20.0, quality * 20),
        1,
    )
    blockers = []
    if not checks["indexed"]:
        blockers.append("尚未完成解析与索引")
    if not checks["verified"]:
        blockers.append("尚未由企业人员确认可信")
    if not checks["fresh"]:
        blockers.append("资料已过期或有效期异常")
    return {
        "document_id": str(document.get("id") or ""),
        "name": document.get("name"),
        "category": _category(document),
        "score": score,
        "ready": score >= 70 and not blockers,
        "checks": checks,
        "blockers": blockers,
    }


def build_knowledge_readiness(
    documents: list[dict[str, Any]],
    *,
    artifact_type: str = "customer_solution",
    product_count: int = 0,
) -> dict[str, Any]:
    required = REQUIRED_CATEGORIES.get(
        artifact_type, REQUIRED_CATEGORIES["customer_solution"]
    )
    scored = [score_document(document) for document in documents]
    ready_documents = [item for item in scored if item["ready"]]
    covered = {item["category"] for item in ready_documents}
    missing = [category for category in required if category not in covered]
    category_score = (len(required) - len(missing)) / max(1, len(required)) * 45
    document_score = (
        sum(float(item["score"]) for item in scored) / len(scored) * 0.35
        if scored
        else 0
    )
    catalog_score = 20 if product_count >= 3 else min(20, product_count * 6)
    score = round(category_score + document_score + catalog_score, 1)
    next_actions = [f"补充{CATEGORY_LABELS.get(item, item)}" for item in missing]
    if product_count == 0:
        next_actions.insert(0, "录入至少一个可验证的产品型号与参数")
    if scored and not ready_documents:
        next_actions.append("确认已上传资料的版本、有效期与可信状态")
    return {
        "artifact_type": artifact_type,
        "score": score,
        "ready": score >= 75 and not missing and product_count > 0,
        "document_count": len(scored),
        "ready_document_count": len(ready_documents),
        "product_count": product_count,
        "required_categories": [
            {
                "key": item,
                "label": CATEGORY_LABELS.get(item, item),
                "covered": item in covered,
            }
            for item in required
        ],
        "missing_categories": missing,
        "next_actions": next_actions[:5],
        "documents": scored,
        "schema_version": "knowledge-readiness.v1",
    }
