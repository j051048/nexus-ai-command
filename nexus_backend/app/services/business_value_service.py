"""Transparent business-value attribution for Agent actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ValueAssumptions:
    labor_cost_cny_per_hour: float = 180.0
    completed_action_minutes: float = 18.0
    accepted_action_minutes: float = 8.0
    crm_followup_value_cny: float = 120.0
    risk_review_value_cny: float = 300.0
    instrument_downtime_cny_per_hour: float = 1200.0


def summarize_business_value(
    *,
    completed_actions: int,
    accepted_actions: int,
    automated_followups: int,
    risk_reviews: int,
    events: list[dict[str, Any]] | None = None,
    assumptions: ValueAssumptions | None = None,
) -> dict[str, Any]:
    """Separate measured value from assumption-based estimates."""
    assumptions = assumptions or ValueAssumptions()
    events = events or []

    estimated_minutes = (
        completed_actions * assumptions.completed_action_minutes
        + max(accepted_actions - completed_actions, 0)
        * assumptions.accepted_action_minutes
    )
    estimated_process_value = (
        estimated_minutes / 60 * assumptions.labor_cost_cny_per_hour
        + automated_followups * assumptions.crm_followup_value_cny
        + risk_reviews * assumptions.risk_review_value_cny
    )

    verified_minutes = 0.0
    verified_value = 0.0
    downtime_minutes_avoided = 0.0
    evidence_refs: set[str] = set()
    for event in events:
        metadata = (
            event.get("metadata") if isinstance(event.get("metadata"), dict) else event
        )
        if str(metadata.get("value_evidence_status") or "").lower() != "verified":
            continue
        verified_minutes += float(metadata.get("minutes_saved") or 0)
        verified_value += float(metadata.get("value_cny") or 0)
        downtime_minutes_avoided += float(metadata.get("downtime_minutes_avoided") or 0)
        if metadata.get("evidence_ref"):
            evidence_refs.add(str(metadata["evidence_ref"]))

    verified_value += (
        downtime_minutes_avoided / 60 * assumptions.instrument_downtime_cny_per_hour
    )
    estimated_hours = round(estimated_minutes / 60, 2)
    verified_hours = round(verified_minutes / 60, 2)
    total_value = round(estimated_process_value + verified_value, 2)
    return {
        "verified": {
            "saved_hours": verified_hours,
            "downtime_hours_avoided": round(downtime_minutes_avoided / 60, 2),
            "value_cny": round(verified_value, 2),
            "evidence_refs": sorted(evidence_refs),
        },
        "estimated": {
            "saved_hours": estimated_hours,
            "automated_followups": automated_followups,
            "risk_reviews": risk_reviews,
            "value_cny": round(estimated_process_value, 2),
        },
        "total_value_cny": total_value,
        "evidence_coverage": round(len(evidence_refs) / max(completed_actions, 1), 4),
        "methodology": {
            "currency": "CNY",
            "assumptions": asdict(assumptions),
            "verified_and_estimated_are_reported_separately": True,
        },
        "story": (
            f"AI 估算节省 {estimated_hours} 小时；已有证据核验 {verified_hours} 小时，"
            f"可归因价值合计约 ¥{total_value}。"
        ),
    }
