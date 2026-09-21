"""Keep artifact-quality evidence honest.

The committed baseline in ``nexus_backend/evals/artifact_output_baseline.json``
is what the SLO payload and the monthly report point at. Two failure modes are
worth guarding:

* a fixture run relabelled as ``live-model``, which would let the product claim
  real document quality that was never measured;
* a ``live-model`` baseline that lost the provenance needed to trust it (no
  recorded-output hash, no evidence documents, unknown model, stale beyond the
  review window).

Default mode checks internal consistency and always runs in CI. ``--require-live``
(or ``REQUIRE_LIVE_ARTIFACT_BASELINE=1``) is the release/customer-acceptance
profile: it refuses a baseline that cannot back a quality claim.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "nexus_backend" / "evals" / "artifact_output_baseline.json"

FIXTURE_SOURCE = "contract-fixture"
LIVE_SOURCE = "live-model"
VALID_SOURCES = {FIXTURE_SOURCE, LIVE_SOURCE}

#: A live baseline older than this no longer describes the shipped product.
MAX_LIVE_AGE_DAYS = int(os.getenv("ARTIFACT_EVAL_MAX_EVIDENCE_AGE_DAYS", "90"))

REQUIRED_KEYS = (
    "version",
    "source",
    "recorded_at",
    "pass_rate",
    "minimum_pass_rate",
    "cases",
    "models",
)

LIVE_REQUIRED_KEYS = (
    "recorded_outputs_sha256",
    "environment",
    "evidence_document_ids",
)


def check(
    baseline: dict, *, require_live: bool = False, now: datetime | None = None
) -> list[str]:
    """Return the reasons this baseline may not be used as evidence."""
    failures: list[str] = []
    missing = [key for key in REQUIRED_KEYS if key not in baseline]
    if missing:
        return ["baseline_missing_keys:" + ",".join(missing)]

    source = str(baseline.get("source") or "")
    if source not in VALID_SOURCES:
        failures.append(f"unknown_source:{source}")

    pass_rate = float(baseline.get("pass_rate") or 0)
    minimum = float(baseline.get("minimum_pass_rate") or 0)
    if pass_rate < minimum:
        failures.append(f"pass_rate_below_floor:{pass_rate}<{minimum}")

    cases = baseline.get("cases") or {}
    if not cases:
        failures.append("no_cases_recorded")
    elif not all(bool(value) for value in cases.values()):
        failing = [name for name, value in cases.items() if not value]
        failures.append("cases_not_passing:" + ",".join(sorted(failing)))

    models = [str(item) for item in (baseline.get("models") or [])]
    if not models or any(model in {"", "unknown"} for model in models):
        failures.append("unknown_model")

    if source == LIVE_SOURCE:
        for key in LIVE_REQUIRED_KEYS:
            value = baseline.get(key)
            if value in (None, "", [], {}):
                failures.append(f"live_baseline_missing:{key}")
        recorded_at = _parse(baseline.get("recorded_at"))
        if recorded_at is None:
            failures.append("live_baseline_recorded_at_invalid")
        else:
            age = (now or datetime.now(UTC)) - recorded_at
            if age > timedelta(days=MAX_LIVE_AGE_DAYS):
                failures.append(
                    f"live_baseline_stale:{age.days}d>{MAX_LIVE_AGE_DAYS}d"
                )
    elif source == FIXTURE_SOURCE:
        # A fixture that carries live-only provenance is a relabelling bug in
        # the other direction and means one of the two fields is lying.
        for key in LIVE_REQUIRED_KEYS:
            if baseline.get(key) not in (None, "", [], {}):
                failures.append(f"fixture_baseline_carries_live_evidence:{key}")
        if models != [FIXTURE_SOURCE]:
            failures.append("fixture_baseline_claims_model:" + ",".join(models))

    if require_live and source != LIVE_SOURCE:
        failures.append(f"live_baseline_required_but_source_is:{source}")
    return failures


def _parse(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-live",
        action="store_true",
        default=os.getenv("REQUIRE_LIVE_ARTIFACT_BASELINE", "").lower()
        in {"1", "true", "yes"},
        help="Refuse a baseline that cannot back a real-model quality claim",
    )
    args = parser.parse_args()

    if not BASELINE.exists():
        print("ARTIFACT_EVAL_PROVENANCE_FAIL")
        print(f" - baseline missing at {BASELINE}")
        return 1
    try:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print("ARTIFACT_EVAL_PROVENANCE_FAIL")
        print(f" - baseline is not valid JSON: {exc}")
        return 1

    failures = check(baseline, require_live=args.require_live)
    if failures:
        print("ARTIFACT_EVAL_PROVENANCE_FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1

    suffix = " claims_live_quality=true" if baseline.get("source") == LIVE_SOURCE else ""
    print(
        f"ARTIFACT_EVAL_PROVENANCE_OK source={baseline.get('source')} "
        f"pass_rate={baseline.get('pass_rate')}{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
