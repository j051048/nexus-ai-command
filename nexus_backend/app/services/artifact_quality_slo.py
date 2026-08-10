"""Document-quality SLO evaluation and monthly reporting.

SLOs are deliberately simple and tenant-scoped:
- external ready rate >= 90%  (一次通过率)
- average quality score >= 85
- average evidence coverage >= 90%

``build_monthly_report`` aggregates the same event table into a structured
monthly digest (by type, by template, failure modes) that the observability
router exposes and a future report job can persist.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

SLO_CONFIG: dict[str, dict[str, float]] = {
    "ready_rate": {"target": 0.90, "description": "外发文档一次通过率"},
    "avg_score": {"target": 85.0, "description": "平均质量分"},
    "evidence_coverage": {"target": 90.0, "description": "平均证据覆盖度"},
}

_METRIC_KEY = {
    "ready_rate": "ready_rate",
    "avg_score": "avg_score",
    "evidence_coverage": "avg_evidence_coverage",
}


def _aggregate(events: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(events)
    if not total:
        return {
            "sample_size": 0,
            "ready_rate": 0.0,
            "avg_score": 0.0,
            "avg_evidence_coverage": 0.0,
            "avg_repair_count": 0.0,
            "by_artifact_type": {},
            "by_template": {},
            "failure_modes": [],
        }
    ready = sum(int(bool(event.get("ready"))) for event in events)
    score_sum = sum(float(event.get("score") or 0) for event in events)
    coverage_sum = 0.0
    repair_sum = sum(int(event.get("repair_count") or 0) for event in events)
    coverage_count = 0
    by_type: dict[str, int] = {}
    by_template: dict[str, int] = {}
    failure_counts: dict[str, int] = {}
    for event in events:
        dimensions = event.get("dimensions") or {}
        coverage = float(dimensions.get("evidence_coverage") or 0)
        if coverage:
            coverage_sum += coverage
            coverage_count += 1
        artifact_type = str(event.get("artifact_type") or "unknown")
        by_type[artifact_type] = by_type.get(artifact_type, 0) + 1
        template_key = event.get("template_key")
        if template_key:
            by_template[str(template_key)] = by_template.get(str(template_key), 0) + 1
        for finding in event.get("findings") or []:
            if isinstance(finding, dict):
                code = str(finding.get("code") or "unknown")
                failure_counts[code] = failure_counts.get(code, 0) + 1
    return {
        "sample_size": total,
        "ready_rate": round(ready / total, 4),
        "avg_score": round(score_sum / total, 2),
        "avg_evidence_coverage": (
            round(coverage_sum / coverage_count, 2) if coverage_count else 0.0
        ),
        "avg_repair_count": round(repair_sum / total, 2),
        "by_artifact_type": by_type,
        "by_template": by_template,
        "failure_modes": [
            {"code": code, "count": count}
            for code, count in sorted(failure_counts.items(), key=lambda item: -item[1])
        ][:8],
    }


async def _load_quality_events(
    db: Any, *, organization_id: str, since: str, until: str | None = None
) -> list[dict[str, Any]]:
    try:
        query = (
            db.table("agent_artifact_quality_events")
            .select("*")
            .eq("organization_id", organization_id)
            .gte("created_at", since)
        )
        if until:
            query = query.lt("created_at", until)
        result = await query.limit(1000).execute()
        return result.data or []
    except Exception as exc:  # broad-except: intentional
        logger.warning("[SLO] quality events load failed: %s", exc)
        return []


async def evaluate_slo(
    db: Any, *, organization_id: str, days: int = 30
) -> dict[str, Any]:
    """Evaluate SLOs over the trailing window."""
    since = (datetime.now(UTC) - timedelta(days=max(1, days))).isoformat()
    events = await _load_quality_events(
        db, organization_id=organization_id, since=since
    )
    metrics = _aggregate(events)
    if not metrics["sample_size"]:
        return {
            "available": False,
            "window_days": days,
            "slo": {},
            "metrics": metrics,
        }
    slo: dict[str, Any] = {}
    overall = "ok"
    for name, config in SLO_CONFIG.items():
        value = metrics[_METRIC_KEY[name]]
        ok = value >= config["target"]
        slo[name] = {
            "value": value,
            "target": config["target"],
            "description": config["description"],
            "ok": ok,
        }
        if not ok:
            overall = "warn"
    return {
        "available": True,
        "window_days": days,
        "overall": overall,
        "slo": slo,
        "metrics": metrics,
    }


async def build_monthly_report(
    db: Any, *, organization_id: str, year: int, month: int
) -> dict[str, Any]:
    """Build a structured monthly quality report."""
    if not (1 <= month <= 12):
        return {"available": False, "error": "month must be 1..12"}
    start = datetime(year, month, 1, tzinfo=UTC)
    end = (
        datetime(year + 1, 1, 1, tzinfo=UTC)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=UTC)
    )
    events = await _load_quality_events(
        db,
        organization_id=organization_id,
        since=start.isoformat(),
        until=end.isoformat(),
    )
    metrics = _aggregate(events)
    metrics["period"] = f"{year:04d}-{month:02d}"
    slo = {}
    for name, config in SLO_CONFIG.items():
        value = metrics[_METRIC_KEY[name]]
        slo[name] = {
            "value": value,
            "target": config["target"],
            "description": config["description"],
            "ok": bool(metrics["sample_size"]) and value >= config["target"],
        }
    metrics["slo"] = slo
    return {
        "available": bool(metrics["sample_size"]),
        "period": f"{year:04d}-{month:02d}",
        "report": metrics,
    }
