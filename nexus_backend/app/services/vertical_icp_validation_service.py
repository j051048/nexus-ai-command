"""Evidence-based go/no-go checks for the scientific-instrument vertical.

The service deliberately stores no customer names or interview text. Callers
provide anonymized evidence records and artifact references; the evaluator
only determines whether discovery and commercialization gates are supported.
"""

from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VerticalReadinessThresholds:
    interviews: int = 8
    repeated_workflows: int = 2
    candidates_per_workflow: int = 3
    design_partners: int = 2
    device_data_access: int = 1
    domain_experts: int = 1
    paid_pilots: int = 1


PILOT_METRICS = {
    "calibration_and_maintenance": [
        "overdue_calibration_rate",
        "unplanned_downtime_hours",
        "work_order_cycle_time_hours",
    ],
    "service_operations": [
        "first_time_fix_rate",
        "mean_time_to_repair_hours",
        "service_evidence_completeness",
    ],
    "compliance_reporting": [
        "report_preparation_hours",
        "audit_evidence_completeness",
        "human_override_rate",
    ],
    "experiment_workflow": [
        "workflow_cycle_time_hours",
        "manual_data_entry_minutes",
        "result_traceability_rate",
    ],
}


def build_vertical_pilot_plan(readiness: dict[str, Any]) -> dict[str, Any]:
    """Build a constrained pilot plan from validated evidence only."""
    repeated = list(readiness.get("repeated_workflows") or [])
    selected = repeated[:2]
    metrics = {
        workflow: PILOT_METRICS.get(
            workflow,
            ["cycle_time", "manual_touch_count", "evidence_completeness"],
        )
        for workflow in selected
    }
    blockers = [
        name for name, passed in readiness.get("checks", {}).items() if not passed
    ]
    return {
        "eligible": bool(readiness.get("discovery_ready")) and bool(selected),
        "selected_workflows": selected,
        "success_metrics": metrics,
        "duration_weeks": 6,
        "required_controls": [
            "sandbox tenant with synthetic or consented data",
            "human approval for instrument commands and compliance conclusions",
            "baseline captured before enabling automation",
            "weekly go/no-go review with a named domain owner",
        ],
        "blockers": blockers,
        "exit_criteria": {
            "workflow_completion_rate_min": 0.9,
            "evidence_completeness_min": 0.95,
            "critical_safety_incidents_max": 0,
            "design_partner_signoff_required": True,
        },
    }


def evaluate_vertical_readiness(
    evidence: list[dict[str, Any]],
    thresholds: VerticalReadinessThresholds | None = None,
) -> dict[str, Any]:
    """Evaluate anonymized validation evidence without inventing customer proof."""
    thresholds = thresholds or VerticalReadinessThresholds()
    by_type: dict[str, set[str]] = {}
    workflow_candidates: dict[str, set[str]] = {}
    invalid_records = 0

    for row in evidence:
        evidence_type = str(row.get("evidence_type") or "").strip().lower()
        candidate_id = str(row.get("candidate_id") or "").strip()
        artifact_ref = str(row.get("artifact_ref") or "").strip()
        if not evidence_type or not candidate_id or not artifact_ref:
            invalid_records += 1
            continue
        by_type.setdefault(evidence_type, set()).add(candidate_id)
        workflow_key = str(row.get("workflow_key") or "").strip().lower()
        if evidence_type == "pain_point" and workflow_key:
            workflow_candidates.setdefault(workflow_key, set()).add(candidate_id)

    repeated = sorted(
        workflow
        for workflow, candidates in workflow_candidates.items()
        if len(candidates) >= thresholds.candidates_per_workflow
    )
    counts = Counter({key: len(value) for key, value in by_type.items()})
    checks = {
        "interviews": counts["interview"] >= thresholds.interviews,
        "repeated_workflows": len(repeated) >= thresholds.repeated_workflows,
        "design_partners": counts["design_partner"] >= thresholds.design_partners,
        "device_data_access": counts["device_data_access"]
        >= thresholds.device_data_access,
        "domain_experts": counts["domain_expert"] >= thresholds.domain_experts,
    }
    commercial_check = counts["paid_pilot"] >= thresholds.paid_pilots

    result = {
        "discovery_ready": all(checks.values()),
        "commercial_ready": all(checks.values()) and commercial_check,
        "checks": checks,
        "paid_pilot": commercial_check,
        "counts": dict(counts),
        "repeated_workflows": repeated,
        "invalid_records": invalid_records,
        "decision": (
            "proceed_to_vertical_build"
            if all(checks.values())
            else "continue_customer_discovery"
        ),
    }
    result["pilot_plan"] = build_vertical_pilot_plan(result)
    return result
