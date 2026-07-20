"""Tender handoff and Bid/No-Bid readiness derived from a solution project."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def build_tender_readiness(project: dict[str, Any]) -> dict[str, Any]:
    workspace = project.get("workspace") or {}
    requirements = workspace.get("requirements") or []
    must = [item for item in requirements if item.get("priority") == "must"]
    covered = [item for item in requirements if item.get("status") == "verified"]
    deviations = [
        {
            "requirement_id": item.get("id"),
            "requirement": item.get("title"),
            "severity": "major" if item.get("priority") == "must" else "minor",
            "reason": "未核验或缺少应答证据",
        }
        for item in requirements
        if item.get("status") != "verified" or not item.get("evidence_ref")
    ]
    budget_max = float(project.get("budget_max") or 0)
    recommended = next(
        (
            item
            for item in workspace.get("packages") or []
            if item.get("id") == "recommended"
        ),
        {},
    )
    quoted = float((recommended.get("commercial") or {}).get("list_price") or 0)
    deadline = project.get("deadline")
    deadline_days: int | None = None
    if deadline:
        try:
            parsed = datetime.fromisoformat(str(deadline).replace("Z", "+00:00"))
            deadline_days = (parsed.astimezone(UTC) - datetime.now(UTC)).days
        except ValueError:
            deadline_days = None
    factors = {
        "must_coverage": (
            round(
                sum(item.get("status") == "verified" for item in must)
                / len(must)
                * 100,
                2,
            )
            if must
            else 100.0
        ),
        "evidence_coverage": (
            round(
                sum(bool(item.get("evidence_ref")) for item in requirements)
                / len(requirements)
                * 100,
                2,
            )
            if requirements
            else 0.0
        ),
        "budget_fit": (
            100.0
            if not budget_max or not quoted or quoted <= budget_max
            else max(0.0, round(budget_max / quoted * 100, 2))
        ),
        "time_fit": (
            100.0
            if deadline_days is None or deadline_days >= 14
            else max(0.0, deadline_days / 14 * 100)
        ),
    }
    score = round(
        factors["must_coverage"] * 0.4
        + factors["evidence_coverage"] * 0.25
        + factors["budget_fit"] * 0.2
        + factors["time_fit"] * 0.15,
        2,
    )
    major_deviations = sum(item["severity"] == "major" for item in deviations)
    decision = (
        "bid"
        if score >= 75 and not major_deviations
        else "review" if score >= 55 else "no_bid"
    )
    return {
        "score": score,
        "decision": decision,
        "factors": factors,
        "coverage_percent": (
            round(len(covered) / len(requirements) * 100, 2) if requirements else 0.0
        ),
        "deviations": deviations,
        "major_deviations": major_deviations,
        "deadline_days": deadline_days,
    }
