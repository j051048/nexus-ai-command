"""Deterministic Agent eval regression gate.

This is intentionally offline and cheap: PRs can run it without calling an LLM.
Nightly jobs can still run the heavier eval matrix, but this gate prevents
router quality from silently drifting below the checked-in baseline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "nexus_backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> int:
    from app.services.agent_eval_baseline_service import agent_eval_baseline_service

    cases_path = (
        BACKEND_ROOT
        / "tests"
        / "production_proof"
        / "fixtures"
        / "agent_eval_cases_200.json"
    )
    thresholds_path = (
        BACKEND_ROOT
        / "tests"
        / "production_proof"
        / "fixtures"
        / "agent_quality_thresholds.json"
    )
    baselines_path = BACKEND_ROOT / "evals" / "baseline_scores.json"

    cases = _load_json(cases_path)
    thresholds = _load_json(thresholds_path)["thresholds"]
    baselines = _load_json(baselines_path)["baselines"]

    router_supported = {
        "approval_decision",
        "battlecard",
        "crm_followup",
        "renewal_or_contract",
        "tender_support",
        "general_assistant",
    }
    smoke_cases = [
        case for case in cases if case.get("expected_intent") in router_supported
    ][:120]

    result = agent_eval_baseline_service.run_router_baseline(smoke_cases)
    accuracy = float(result["accuracy"])
    release_min = float(thresholds["intent_accuracy_min"])
    baseline = float(baselines["router_accuracy"])
    regression_tolerance = 0.02

    failures: list[str] = []
    if result["case_count"] < 70:
        failures.append(f"case_count {result['case_count']} is below 70")
    if accuracy < release_min:
        failures.append(
            f"intent accuracy {_pct(accuracy)} is below release minimum {_pct(release_min)}"
        )
    if accuracy < baseline - regression_tolerance:
        failures.append(
            "router accuracy regressed more than 2pp: "
            f"baseline {_pct(baseline)}, current {_pct(accuracy)}"
        )

    report = {
        "gate": "agent_eval_regression",
        "runner": result["runner"],
        "case_count": result["case_count"],
        "accuracy": accuracy,
        "release_min": release_min,
        "baseline": baseline,
        "regression_tolerance": regression_tolerance,
        "failed_cases": [
            item for item in result["results"] if not item.get("passed")
        ][:20],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if failures:
        print("AGENT_EVAL_REGRESSION_FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("AGENT_EVAL_REGRESSION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
