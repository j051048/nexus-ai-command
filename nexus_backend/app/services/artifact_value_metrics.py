"""Observed artifact economics, not billing or assumed business value."""

import math


def artifact_value_metrics(rows):
    latest_outcomes = {}
    generated = {}
    for row in sorted(rows, key=lambda row: str(row.get("created_at") or "")):
        identity = row.get("artifact_id")
        if not identity:
            continue
        if row.get("event_type") == "generated":
            generated[identity] = row
        elif row.get("event_type") in {"used", "edited", "won", "lost", "discarded"}:
            latest_outcomes[identity] = row
    adopted = sum(
        row["event_type"] in {"used", "edited", "won"}
        for row in latest_outcomes.values()
    )
    costs = []
    for row in generated.values():
        cost = ((row.get("metadata") or {}).get("usage") or {}).get("call_cost")
        if (
            isinstance(cost, int | float)
            and not isinstance(cost, bool)
            and math.isfinite(cost)
            and cost >= 0
        ):
            costs.append(cost)
    rework = [
        (row.get("metadata") or {}).get("rework_minutes")
        for row in latest_outcomes.values()
    ]
    rework = [
        value
        for value in rework
        if isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= 10080
    ]
    return {
        "measurement_scope": "window_events_retained_stages_not_billing",
        "generated_artifacts": len(generated),
        "latest_adopted_artifacts": adopted,
        "cost_sample_count": len(costs),
        "rework_sample_count": len(rework),
        "retained_stage_cost_usd": round(sum(costs), 6) if costs else None,
        "retained_cost_per_adopted_artifact_usd": (
            round(sum(costs) / adopted, 6)
            if adopted
            and generated
            and len(costs) == len(generated)
            and set(latest_outcomes) <= set(generated)
            else None
        ),
        "mean_reported_rework_minutes": (
            round(sum(rework) / len(rework), 1) if rework else None
        ),
    }
