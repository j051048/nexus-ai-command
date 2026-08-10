"""Feedback loop for generated artifacts: edit-diff learning, failure-mode
summaries and customer-outcome回流 (write-back).

The pipeline is deliberately read-mostly and recommendation-only:
- ``record_learning_candidate`` never mutates a production template or skill;
  it only marks a human-edited artifact as eligible for expert review.
- ``summarize_failure_modes`` aggregates deterministic quality findings so
  teams can see which failure classes drive rework.
- ``record_customer_outcome`` attaches the business result (won/lost/used/
  edited/discarded) to the same artifact so quality scores can be validated
  against commercial outcomes.
"""

from __future__ import annotations

import logging
from datetime import UTC
from difflib import SequenceMatcher
from typing import Any

from app.services.artifact_feedback_service import build_artifact_feedback_candidate

logger = logging.getLogger(__name__)


def compute_artifact_diff(
    original_content: str, revised_content: str
) -> dict[str, Any]:
    """Return a paragraph-level diff summary between generated and final copy."""
    original = str(original_content or "")
    revised = str(revised_content or "")
    similarity = (
        SequenceMatcher(None, original, revised).ratio() if original or revised else 1.0
    )
    original_paragraphs = [p.strip() for p in original.splitlines() if p.strip()]
    revised_paragraphs = [p.strip() for p in revised.splitlines() if p.strip()]
    matcher = SequenceMatcher(None, original_paragraphs, revised_paragraphs)
    added = 0
    removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added += j2 - j1
        elif tag == "delete":
            removed += i2 - i1
        elif tag == "replace":
            added += j2 - j1
            removed += i2 - i1
    return {
        "similarity": round(similarity, 4),
        "paragraphs_added": added,
        "paragraphs_removed": removed,
        "paragraphs_changed": (
            min(added, removed) if added and removed else max(added, removed)
        ),
        "total_paragraphs_original": len(original_paragraphs),
        "total_paragraphs_revised": len(revised_paragraphs),
    }


async def record_learning_candidate(
    db: Any,
    *,
    organization_id: str,
    user_id: str,
    artifact_id: str,
    artifact_version_id: str,
    change_type: str,
    rating: int | None,
    comment: str | None,
    original_content: str | None,
    revised_content: str | None,
    quality_before: dict[str, Any] | None,
    quality_after: dict[str, Any] | None,
    evidence_fingerprint: str | None,
) -> dict[str, Any]:
    """Persist a recommendation-only learning candidate into
    ``artifact_feedback_events``.  Never auto-applies."""
    candidate = build_artifact_feedback_candidate(
        change_type=change_type,
        rating=rating,
        original_content=original_content,
        revised_content=revised_content,
        quality_before=quality_before,
        quality_after=quality_after,
        evidence_fingerprint=evidence_fingerprint,
    )
    diff_summary = compute_artifact_diff(original_content or "", revised_content or "")
    payload = {
        "organization_id": organization_id,
        "artifact_id": artifact_id,
        "artifact_version_id": artifact_version_id,
        "user_id": user_id,
        "rating": rating,
        "comment": comment,
        "change_type": change_type,
        "quality_snapshot": {
            "before": quality_before or {},
            "after": quality_after or {},
        },
        "evidence_fingerprint": evidence_fingerprint,
        "diff_summary": diff_summary,
        "learning_status": candidate["learning_status"],
    }
    try:
        result = await db.table("artifact_feedback_events").insert(payload).execute()
        return {
            "ok": True,
            "learning_status": candidate["learning_status"],
            "data": result.data,
        }
    except Exception as exc:  # broad-except: intentional
        logger.warning("[FeedbackLoop] learning candidate not persisted: %s", exc)
        return {"ok": False, "learning_status": "recorded", "error": str(exc)}


async def summarize_failure_modes(
    db: Any, *, organization_id: str, days: int = 30
) -> dict[str, Any]:
    """Aggregate deterministic quality findings into a failure-mode ranking."""
    from datetime import datetime, timedelta

    since = (datetime.now(UTC) - timedelta(days=max(1, days))).isoformat()
    try:
        result = (
            await db.table("agent_artifact_quality_events")
            .select("artifact_type,score,ready,findings,created_at")
            .eq("organization_id", organization_id)
            .gte("created_at", since)
            .limit(500)
            .execute()
        )
    except Exception as exc:  # broad-except: intentional
        logger.warning("[FeedbackLoop] failure-mode scan failed: %s", exc)
        return {"available": False, "sample_size": 0, "failure_modes": []}

    events = result.data or []
    counts: dict[str, int] = {}
    by_type: dict[str, int] = {}
    score_sum = 0.0
    ready_count = 0
    for event in events:
        score_sum += float(event.get("score") or 0)
        ready_count += int(bool(event.get("ready")))
        artifact_type = str(event.get("artifact_type") or "unknown")
        by_type[artifact_type] = by_type.get(artifact_type, 0) + 1
        for finding in event.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            code = str(finding.get("code") or "unknown")
            counts[code] = counts.get(code, 0) + 1
    total = len(events)
    failure_modes = [
        {"code": code, "count": count, "share": round(count / total, 4) if total else 0}
        for code, count in sorted(counts.items(), key=lambda item: -item[1])
    ][:15]
    return {
        "available": True,
        "sample_size": total,
        "ready_rate": round(ready_count / total, 4) if total else 0.0,
        "avg_score": round(score_sum / total, 2) if total else 0.0,
        "by_artifact_type": by_type,
        "failure_modes": failure_modes,
    }


async def record_customer_outcome(
    db: Any,
    *,
    organization_id: str,
    user_id: str,
    artifact_id: str,
    artifact_version_id: str,
    outcome: str,
    rating: int | None = None,
    comment: str | None = None,
) -> dict[str, Any]:
    """Attach the business outcome to an artifact for commercial validation."""
    allowed = {"used", "edited", "discarded", "won", "lost"}
    if outcome not in allowed:
        return {"ok": False, "error": f"outcome must be one of {sorted(allowed)}"}
    payload = {
        "organization_id": organization_id,
        "artifact_id": artifact_id,
        "artifact_version_id": artifact_version_id,
        "user_id": user_id,
        "outcome": outcome,
        "rating": rating,
        "comment": comment,
        "learning_status": "recorded",
    }
    try:
        result = await db.table("artifact_feedback_events").insert(payload).execute()
        await record_delivery_event(
            db,
            organization_id=organization_id,
            artifact_id=artifact_id,
            artifact_version_id=artifact_version_id,
            user_id=user_id,
            event_type=outcome,
            metadata={"rating": rating, "source": "quality-platform"},
        )
        return {"ok": True, "data": result.data}
    except Exception as exc:  # broad-except: intentional
        logger.warning("[FeedbackLoop] customer outcome not persisted: %s", exc)
        return {"ok": False, "error": str(exc)}


async def record_delivery_event(
    db: Any,
    *,
    organization_id: str,
    artifact_id: str,
    event_type: str,
    artifact_version_id: str | None = None,
    user_id: str | None = None,
    output_format: str | None = None,
    estimated_value: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Best-effort outcome telemetry; delivery must not fail when telemetry does."""
    try:
        await db.table("artifact_delivery_events").insert(
            {
                "organization_id": organization_id,
                "artifact_id": artifact_id,
                "artifact_version_id": artifact_version_id,
                "user_id": user_id,
                "event_type": event_type,
                "output_format": output_format,
                "estimated_value": estimated_value,
                "metadata": metadata or {},
            }
        ).execute()
        return True
    except Exception as exc:  # broad-except: telemetry is non-blocking
        logger.info("[FeedbackLoop] delivery event skipped: %s", exc)
        return False


async def build_artifact_value_report(
    db: Any, *, organization_id: str, days: int = 30
) -> dict[str, Any]:
    """Connect generated files to downloads, adoption and commercial outcomes."""
    from datetime import datetime, timedelta

    since = (datetime.now(UTC) - timedelta(days=max(1, days))).isoformat()
    try:
        result = (
            await db.table("artifact_delivery_events")
            .select("artifact_id,event_type,estimated_value,created_at")
            .eq("organization_id", organization_id)
            .gte("created_at", since)
            .limit(2000)
            .execute()
        )
        rows = result.data or []
    except Exception as exc:  # broad-except: migration may not be deployed yet
        logger.warning("[FeedbackLoop] value report unavailable: %s", exc)
        return {
            "available": False,
            "window_days": days,
            "events": 0,
            "by_event": {},
        }

    by_event: dict[str, int] = {}
    artifact_ids: set[str] = set()
    downloaded_ids: set[str] = set()
    adopted_ids: set[str] = set()
    won_ids: set[str] = set()
    estimated_value = 0.0
    for row in rows:
        event_type = str(row.get("event_type") or "unknown")
        artifact_id = str(row.get("artifact_id") or "")
        by_event[event_type] = by_event.get(event_type, 0) + 1
        if artifact_id:
            artifact_ids.add(artifact_id)
        if event_type == "downloaded":
            downloaded_ids.add(artifact_id)
        if event_type in {"used", "edited", "won"}:
            adopted_ids.add(artifact_id)
        if event_type == "won":
            won_ids.add(artifact_id)
        estimated_value += float(row.get("estimated_value") or 0)
    generated = max(by_event.get("generated", 0), len(artifact_ids))
    return {
        "available": bool(rows),
        "window_days": days,
        "events": len(rows),
        "unique_artifacts": len(artifact_ids),
        "by_event": by_event,
        "download_rate": round(len(downloaded_ids) / generated, 4) if generated else 0,
        "adoption_rate": round(len(adopted_ids) / generated, 4) if generated else 0,
        "won_count": len(won_ids),
        "estimated_value": round(estimated_value, 2),
    }
