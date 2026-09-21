"""Run the golden contract against recorded JSON/JSONL model outputs.

Two modes:

* default - evaluate the given outputs and fail below the golden pass rate;
* ``--update-baseline`` - record the run as the versioned regression baseline
  (``nexus_backend/evals/artifact_output_baseline.json``).  A run below the
  golden minimum is refused, so a regression can never be blessed as the new
  baseline by accident.

Once a baseline exists the script also fails on per-case regressions
(pass -> fail), which is what catches a prompt or model change that trades one
document type for another.

Provenance is enforced, not decorative: ``--label live-model`` is refused
unless the recording carries a manifest proving it came from the real pipeline
(model id per case, latency, cost, evidence documents, output hash). Fixture
outputs stay ``contract-fixture`` and can never claim model quality.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"
BASELINE = BACKEND / "evals/artifact_output_baseline.json"
sys.path.insert(0, str(BACKEND))

from app.services.artifact_output_eval_service import evaluate_artifact_output_run
from app.services.artifact_output_recorder import (
    FIXTURE_SOURCE,
    LIVE_SOURCE,
    live_evidence_problems,
    load_recording,
)


def _load_baseline(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _compare_with_baseline(report: dict, baseline: dict) -> list[str]:
    """Return the regression descriptions; empty means no regression."""
    regressions: list[str] = []
    previous_rate = float(baseline.get("pass_rate") or 0)
    current_rate = float(report.get("pass_rate") or 0)
    if current_rate < previous_rate:
        regressions.append(
            f"pass_rate_dropped:{current_rate:.4f}<{previous_rate:.4f}"
        )
    previous_cases = baseline.get("cases") or {}
    for case in report.get("results") or []:
        case_id = str(case.get("case_id"))
        if previous_cases.get(case_id) is True and not case.get("passed"):
            regressions.append(f"case_regressed:{case_id}")
        if case.get("case_id") is not None and case_id not in previous_cases:
            regressions.append(f"case_added_without_baseline:{case_id}")
    return regressions


def _baseline_payload(
    report: dict, golden: dict, label: str, manifest: dict | None
) -> dict:
    models = sorted(
        {
            str(item.get("model") or "unknown")
            for item in report.get("results") or []
            if item.get("model")
        }
    )
    payload = {
        "version": int((_load_baseline(BASELINE) or {}).get("version") or 0) + 1,
        "source": label,
        "recorded_at": datetime.now(UTC).isoformat(),
        "golden_dataset": "nexus_backend/evals/datasets/artifact_delivery_golden.json",
        "minimum_pass_rate": float(golden["minimum_pass_rate"]),
        "pass_rate": float(report.get("pass_rate") or 0),
        "models": models or ["unknown"],
        "cases": {
            str(item.get("case_id")): bool(item.get("passed"))
            for item in report.get("results") or []
        },
    }
    if manifest:
        payload["recorded_outputs_sha256"] = manifest.get("records_sha256")
        payload["environment"] = manifest.get("environment")
        payload["evidence_document_ids"] = manifest.get("evidence_document_ids") or []
        payload["git_sha"] = manifest.get("git_sha")
        payload["orchestration_version"] = manifest.get("orchestration_version")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("outputs", type=Path, help="Recorded output JSON or JSONL")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=BASELINE,
        help="Versioned regression baseline to compare against",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Record this run as the new baseline (refused below the golden floor)",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Honest provenance of the outputs: contract-fixture or live-model",
    )
    args = parser.parse_args()
    golden_path = BACKEND / "evals/datasets/artifact_delivery_golden.json"
    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    case_ids = [str(case.get("id")) for case in golden["cases"]]
    outputs, manifest = load_recording(args.outputs)
    label = args.label
    if label is None:
        # Infer honestly: only a manifest that proves a real pipeline run may
        # be called live-model, everything else stays a fixture.
        label = (
            LIVE_SOURCE
            if manifest and str(manifest.get("source")) == LIVE_SOURCE
            else FIXTURE_SOURCE
        )

    if label == LIVE_SOURCE:
        problems = live_evidence_problems(outputs, manifest, case_ids)
        if problems:
            print("ARTIFACT_EVAL_PROVENANCE_FAIL")
            for problem in problems:
                print(f" - {problem}")
            print(
                "live-model evidence must come from scripts/record_artifact_outputs.py "
                "with real evidence documents"
            )
            return 1

    report = evaluate_artifact_output_run(golden["cases"], outputs)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    minimum = float(golden["minimum_pass_rate"])
    if report["pass_rate"] < minimum:
        print(
            f"ARTIFACT_OUTPUT_EVAL_FAIL pass_rate={report['pass_rate']} "
            f"< minimum={minimum}"
        )
        return 1
    if args.update_baseline:
        payload = _baseline_payload(report, golden, label, manifest)
        args.baseline.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"ARTIFACT_OUTPUT_BASELINE_WRITTEN {args.baseline}")
        return 0
    baseline = _load_baseline(args.baseline)
    if not baseline:
        print("ARTIFACT_OUTPUT_EVAL_OK (no baseline recorded yet)")
        return 0
    regressions = _compare_with_baseline(report, baseline)
    if regressions:
        print("ARTIFACT_OUTPUT_EVAL_REGRESSION")
        for item in regressions:
            print(f" - {item}")
        return 1
    print(
        f"ARTIFACT_OUTPUT_EVAL_OK pass_rate={report['pass_rate']} "
        f"baseline={baseline.get('pass_rate')} source={baseline.get('source')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
