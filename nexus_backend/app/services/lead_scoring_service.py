"""Lead Scoring Service — 线索评分算法

Scoring formula:
  score = recency×0.3 + engagement×0.3 + stage_weight×0.25 + completeness×0.15

Each sub-score is normalized to 0-100, final score is 0-100.
Win probability is derived from stage + score.
"""

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Stage weights: later stages = higher score
STAGE_WEIGHTS: dict[str, float] = {
    "initial": 10,
    "contacted": 25,
    "qualified": 45,
    "proposal": 65,
    "negotiation": 80,
    "won": 100,
    "lost": 0,
}

# Win probability base by stage
STAGE_WIN_PROBABILITY: dict[str, float] = {
    "initial": 0.05,
    "contacted": 0.10,
    "qualified": 0.25,
    "proposal": 0.45,
    "negotiation": 0.65,
    "won": 1.0,
    "lost": 0.0,
}

# Suggestion templates by stage
STAGE_SUGGESTIONS: dict[str, str] = {
    "initial": "建议尽快进行首次联系，了解客户需求",
    "contacted": "已建立联系，建议深入了解需求并安排产品演示",
    "qualified": "客户已确认需求，建议准备方案报价",
    "proposal": "方案已提交，建议跟进客户反馈并处理异议",
    "negotiation": "进入谈判阶段，建议关注价格和条款细节，推动签约",
    "won": "恭喜成交！建议做好交付和客户成功跟进",
    "lost": "线索已流失，建议分析原因并记录经验",
}


def _recency_score(lead: dict) -> float:
    """Score based on how recently the lead was updated. Max 100 for today, decays over 30 days."""
    updated = lead.get("updated_at") or lead.get("created_at")
    if not updated:
        return 0
    if isinstance(updated, str):
        try:
            updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return 0
    now = datetime.now(UTC)
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    days_ago = (now - updated).days
    if days_ago <= 0:
        return 100
    if days_ago >= 30:
        return 10
    return max(10, 100 - (days_ago * 3))


def _engagement_score(lead: dict) -> float:
    """Score based on data completeness as a proxy for engagement."""
    score = 0
    if lead.get("contact_person"):
        score += 25
    if lead.get("phone"):
        score += 25
    if lead.get("email"):
        score += 25
    if lead.get("notes") and len(str(lead["notes"])) > 10:
        score += 25
    return score


def _completeness_score(lead: dict) -> float:
    """Score based on how many fields are filled."""
    fields = ["customer_name", "contact_person", "phone", "email", "source", "notes"]
    filled = sum(1 for f in fields if lead.get(f))
    return (filled / len(fields)) * 100


def score_lead(lead: dict) -> dict:
    """Score a single lead. Returns dict with score, win_probability, ai_suggestion."""
    stage = lead.get("stage", "initial")

    recency = _recency_score(lead)
    engagement = _engagement_score(lead)
    stage_w = STAGE_WEIGHTS.get(stage, 10)
    completeness = _completeness_score(lead)

    score = round(recency * 0.3 + engagement * 0.3 + stage_w * 0.25 + completeness * 0.15, 1)

    # Win probability: base from stage, adjusted by score
    base_prob = STAGE_WIN_PROBABILITY.get(stage, 0.05)
    score_factor = score / 100  # 0-1
    win_probability = round(min(1.0, base_prob * 0.7 + score_factor * 0.3), 2)

    suggestion = STAGE_SUGGESTIONS.get(stage, "建议持续跟进")

    return {
        "score": score,
        "win_probability": win_probability,
        "ai_suggestion": suggestion,
        "last_scored_at": datetime.now(UTC).isoformat(),
    }


async def score_all_leads(db, org_id: str) -> dict:
    """Score all leads for an organization. Returns summary stats."""
    result = await db.table("sales_leads").select("*").eq("organization_id", org_id).execute()
    leads = result.data or []

    if not leads:
        return {"total": 0, "scored": 0}

    scored_count = 0
    for lead in leads:
        scoring = score_lead(lead)
        try:
            await (
                db.table("sales_leads")
                .update(scoring)
                .eq("id", lead["id"])
                .eq("organization_id", org_id)
                .execute()
            )
            scored_count += 1
        except Exception as e:
            logger.error(f"Failed to score lead {lead.get('id')}: {e}")

    return {"total": len(leads), "scored": scored_count}


async def score_single_lead(db, lead_id: str, org_id: str) -> dict | None:
    """Score a single lead by ID. Returns the scoring result or None."""
    result = (
        await db.table("sales_leads")
        .select("*")
        .eq("id", lead_id)
        .eq("organization_id", org_id)
        .maybe_single()
        .execute()
    )
    lead = result.data
    if not lead:
        return None

    scoring = score_lead(lead)
    await (
        db.table("sales_leads")
        .update(scoring)
        .eq("id", lead_id)
        .eq("organization_id", org_id)
        .execute()
    )
    return {**lead, **scoring}
