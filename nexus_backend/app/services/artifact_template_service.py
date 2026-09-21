"""Golden template library for artifact generation.

Templates are stored per tenant and keyed by artifact type x instrument line
x industry.  ``get_optimal_template`` performs the A/B pick: among active
templates matching the request, the one with the best measured quality
(avg score / ready rate / usage, nudged by the customer win rate) wins.
``record_template_usage`` folds real quality events in, ``record_template_outcome``
folds the commercial result in, and ``promote_template`` is the gate a draft
must pass before it can be used as a golden template.

The service never mutates a production writing skill; templates are a
separate, versioned, human-curated asset that the generation pipeline can
inject as a skeleton (``build_template_system_prompt``).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# A template's commercial record only moves the A/B ranking once there is
# enough signal to be meaningful; below this the deterministic quality
# metrics decide on their own.  Promotion, by contrast, is a hard gate.
MIN_OUTCOME_SAMPLE = 5
PROMOTION_MIN_SCORE = 85.0
PROMOTION_MIN_READY_RATE = 0.90
PROMOTION_OUTCOME_WEIGHT = 20.0


def _metric_score(template: dict[str, Any]) -> float:
    metrics = template.get("metrics") or {}
    avg_score = float(metrics.get("avg_score") or 0)
    ready_rate = float(metrics.get("ready_rate") or 0)
    usage = int(metrics.get("usage_count") or 0)
    base = avg_score * 0.5 + ready_rate * 100 * 0.3 + min(usage, 20) / 20 * 100 * 0.2
    outcome_sample = int(metrics.get("outcome_sample") or 0)
    if outcome_sample >= MIN_OUTCOME_SAMPLE:
        win_rate = float(metrics.get("win_rate") or 0)
        base += (win_rate - 0.5) * PROMOTION_OUTCOME_WEIGHT
    return round(base, 2)


def evaluate_template_promotion(template: dict[str, Any]) -> dict[str, Any]:
    """Return the promotion verdict for a draft template.

    A template becomes golden only when the deterministic quality record and
    the commercial record agree; either one alone is not evidence that the
    skeleton is worth standardising on.
    """
    metrics = template.get("metrics") or {}
    avg_score = float(metrics.get("avg_score") or 0)
    ready_rate = float(metrics.get("ready_rate") or 0)
    usage = int(metrics.get("usage_count") or 0)
    outcome_sample = int(metrics.get("outcome_sample") or 0)
    win_rate = float(metrics.get("win_rate") or 0)
    blockers: list[str] = []
    if usage <= 0:
        blockers.append("no_usage_sample")
    if avg_score < PROMOTION_MIN_SCORE:
        blockers.append("avg_score_below_target")
    if ready_rate < PROMOTION_MIN_READY_RATE:
        blockers.append("ready_rate_below_target")
    if outcome_sample < MIN_OUTCOME_SAMPLE:
        blockers.append("customer_outcome_sample_too_small")
    elif win_rate < 0.5:
        blockers.append("customer_win_rate_below_half")
    return {
        "eligible": not blockers,
        "blockers": blockers,
        "metrics": {
            "usage_count": usage,
            "avg_score": avg_score,
            "ready_rate": ready_rate,
            "outcome_sample": outcome_sample,
            "win_rate": win_rate,
        },
        "thresholds": {
            "min_avg_score": PROMOTION_MIN_SCORE,
            "min_ready_rate": PROMOTION_MIN_READY_RATE,
            "min_outcome_sample": MIN_OUTCOME_SAMPLE,
            "min_win_rate": 0.5,
        },
    }


def _profile_score(
    template: dict[str, Any],
    *,
    instrument_line: str | None,
    industry: str | None,
) -> float:
    """Prefer exact profiles while retaining tenant-wide fallback templates."""

    template_line = str(template.get("instrument_line") or "").strip()
    template_industry = str(template.get("industry") or "").strip()
    if template_line and template_line != str(instrument_line or "").strip():
        return -1.0
    if template_industry and template_industry != str(industry or "").strip():
        return -1.0
    specificity = 0.0
    if template_line and instrument_line:
        specificity += 12.0
    if template_industry and industry:
        specificity += 8.0
    return _metric_score(template) + specificity


async def list_templates(
    db: Any,
    *,
    organization_id: str,
    artifact_type: str | None = None,
    instrument_line: str | None = None,
    industry: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    try:
        query = (
            db.table("artifact_templates")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("status", status)
        )
        if artifact_type:
            query = query.eq("artifact_type", artifact_type)
        if instrument_line:
            query = query.eq("instrument_line", instrument_line)
        if industry:
            query = query.eq("industry", industry)
        result = await query.order("created_at", desc=True).limit(100).execute()
        return {"ok": True, "templates": result.data or []}
    except Exception as exc:  # broad-except: intentional
        logger.warning("[Templates] list failed: %s", exc)
        return {"ok": False, "error": str(exc), "templates": []}


async def get_optimal_template(
    db: Any,
    *,
    organization_id: str,
    artifact_type: str,
    instrument_line: str | None = None,
    industry: str | None = None,
) -> dict[str, Any] | None:
    """Pick the best active template (A/B) for a request profile."""
    try:
        query = (
            db.table("artifact_templates")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("artifact_type", artifact_type)
            .eq("status", "active")
        )
        result = await query.limit(50).execute()
    except Exception as exc:  # broad-except: intentional
        logger.warning("[Templates] optimal lookup failed: %s", exc)
        return None

    candidates = [
        item
        for item in (result.data or [])
        if _profile_score(
            item,
            instrument_line=instrument_line,
            industry=industry,
        )
        >= 0
    ]
    if not candidates:
        return None
    best = max(
        candidates,
        key=lambda item: _profile_score(
            item,
            instrument_line=instrument_line,
            industry=industry,
        ),
    )
    return dict(best)


async def save_template(
    db: Any,
    *,
    organization_id: str,
    user_id: str,
    template_key: str,
    artifact_type: str,
    title: str,
    sections: list[str] | None = None,
    content_markdown: str = "",
    instrument_line: str | None = None,
    industry: str | None = None,
    version: str = "1.0.0",
    status: str = "active",
) -> dict[str, Any]:
    payload = {
        "organization_id": organization_id,
        "template_key": template_key,
        "artifact_type": artifact_type,
        "instrument_line": instrument_line,
        "industry": industry,
        "title": title,
        "sections": sections or [],
        "content_markdown": content_markdown,
        "version": version,
        "status": status,
        "created_by": user_id,
    }
    try:
        result = await db.table("artifact_templates").insert(payload).execute()
        return {"ok": True, "template": (result.data or [{}])[0]}
    except Exception as exc:  # broad-except: intentional
        logger.warning("[Templates] save failed: %s", exc)
        return {"ok": False, "error": str(exc)}


async def record_template_usage(
    db: Any,
    *,
    organization_id: str,
    template_key: str,
    quality: dict[str, Any] | None,
) -> dict[str, Any]:
    """Fold one quality event into the template's A/B metrics."""
    return await _update_template_metrics(
        db,
        organization_id=organization_id,
        template_key=template_key,
        mutate=_fold_quality_metric,
        payload=quality or {},
    )


def _fold_quality_metric(
    metrics: dict[str, Any], quality: dict[str, Any]
) -> dict[str, Any]:
    usage = int(metrics.get("usage_count") or 0) + 1
    avg_score = float(metrics.get("avg_score") or 0)
    ready_total = int(metrics.get("ready_total") or 0)
    score = float(quality.get("score") or 0)
    ready = bool(quality.get("ready"))
    return {
        **metrics,
        "usage_count": usage,
        "avg_score": round((avg_score * (usage - 1) + score) / usage, 2),
        "ready_rate": round((ready_total + int(ready)) / usage, 4),
        "ready_total": ready_total + int(ready),
        "last_usage_at": datetime.now(UTC).isoformat(),
    }


def _fold_outcome_metric(
    metrics: dict[str, Any], quality: dict[str, Any]
) -> dict[str, Any]:
    outcome = str(quality.get("outcome") or "").strip().lower()
    won = int(metrics.get("won_count") or 0)
    lost = int(metrics.get("lost_count") or 0)
    adoption = int(metrics.get("adoption_count") or 0)
    if outcome == "won":
        won += 1
    elif outcome == "lost":
        lost += 1
    if outcome in {"used", "edited", "won"}:
        adoption += 1
    sample = won + lost
    return {
        **metrics,
        "won_count": won,
        "lost_count": lost,
        "outcome_sample": sample,
        "win_rate": round(won / sample, 4) if sample else 0.0,
        "adoption_count": adoption,
        "last_outcome_at": datetime.now(UTC).isoformat(),
    }


async def _load_latest_template(
    db: Any, *, organization_id: str, template_key: str
) -> dict[str, Any] | None:
    """Read the newest row for a template key; template I/O is best-effort."""
    try:
        result = (
            await db.table("artifact_templates")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("template_key", template_key)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # broad-except: intentional
        logger.warning("[Templates] template lookup failed: %s", exc)
        return None
    return (result.data or [None])[0]


async def _apply_template_update(
    db: Any,
    *,
    organization_id: str,
    template_key: str,
    update: dict[str, Any],
) -> dict[str, Any]:
    try:
        await (
            db.table("artifact_templates")
            .update(update)
            .eq("organization_id", organization_id)
            .eq("template_key", template_key)
            .execute()
        )
    except Exception as exc:  # broad-except: intentional
        logger.warning("[Templates] template update failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    return {"ok": True, **update}


async def _update_template_metrics(
    db: Any,
    *,
    organization_id: str,
    template_key: str,
    mutate: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Read-modify-write one template's metrics with a graceful failure path."""
    row = await _load_latest_template(
        db, organization_id=organization_id, template_key=template_key
    )
    if not row:
        return {"ok": False, "error": "template not found"}
    updated = mutate(dict(row.get("metrics") or {}), payload)
    return await _apply_template_update(
        db,
        organization_id=organization_id,
        template_key=template_key,
        update={"metrics": updated},
    )


async def record_template_outcome(
    db: Any,
    *,
    organization_id: str,
    template_key: str,
    outcome: str,
) -> dict[str, Any]:
    """Fold a commercial result (won/lost/used/edited/discarded) into the
    template's A/B metrics so the golden library learns from closed deals."""
    return await _update_template_metrics(
        db,
        organization_id=organization_id,
        template_key=template_key,
        mutate=_fold_outcome_metric,
        payload={"outcome": outcome},
    )


async def promote_template(
    db: Any,
    *,
    organization_id: str,
    template_key: str,
    actor_id: str,
    force: bool = False,
) -> dict[str, Any]:
    """Promote a draft template to ``active`` once it clears the gate.

    ``force`` exists for the case where a domain expert accepts a template
    before a deal has closed; the override and the actor are recorded in the
    template metrics so the decision stays auditable.
    """
    row = await _load_latest_template(
        db, organization_id=organization_id, template_key=template_key
    )
    if not row:
        return {"ok": False, "error": "template not found"}
    if str(row.get("status") or "") == "active":
        return {"ok": True, "already_active": True, "gate": None}
    verdict = evaluate_template_promotion(row)
    if not verdict["eligible"] and not force:
        return {
            "ok": False,
            "error": "promotion_gate_failed",
            "gate": verdict,
        }
    metrics = {
        **(row.get("metrics") or {}),
        "promoted_at": datetime.now(UTC).isoformat(),
        "promoted_by": actor_id,
        "promotion_forced": bool(force and not verdict["eligible"]),
        "promotion_gate": verdict,
    }
    written = await _apply_template_update(
        db,
        organization_id=organization_id,
        template_key=template_key,
        update={"status": "active", "metrics": metrics},
    )
    if not written.get("ok"):
        return written
    return {"ok": True, "already_active": False, "gate": verdict, "forced": force}


def build_template_system_prompt(template: dict[str, Any] | None, spec: Any) -> str:
    """Return a generation-time skeleton prompt from the winning template."""
    if not template:
        return ""
    sections = list(template.get("sections") or [])
    title = str(template.get("title") or "")
    content = str(template.get("content_markdown") or "")
    lines = ["【黄金模板参考】", f"模板：{title}"]
    if sections:
        lines.append("建议章节骨架：" + " → ".join(sections))
    if content:
        lines.append("参考框架：" + content[:2000])
    lines.append("请基于企业资料与证据，按上述骨架产出定制内容，不要照抄模板文字。")
    return "\n".join(lines)
