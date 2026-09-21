#!/usr/bin/env python3
"""Budget test reruns so flakiness is tracked instead of masked.

`pytest --retries` keeps CI green when a test is flaky, which is useful but
hides the defect. `nexus_backend/tests/conftest.py` records every rerun into
`nexus_backend/test-retries.json`; this gate fails when a test needs more
reruns than the committed budget allows, and fails for any new flaky test.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETRY_REPORT = ROOT / "nexus_backend" / "test-retries.json"
BASELINE = ROOT / "docs" / "quality" / "flaky-test-baseline.json"


def main() -> int:
    if not RETRY_REPORT.exists():
        print("TEST_RETRY_BUDGET_SKIP no retry report (tests did not run in this job)")
        return 0

    report = json.loads(RETRY_REPORT.read_text(encoding="utf-8"))
    flaky: dict[str, int] = report.get("flaky_tests", {})

    allowed: dict[str, int] = {}
    if BASELINE.exists():
        allowed = json.loads(BASELINE.read_text(encoding="utf-8")).get("tests", {})

    failures: list[str] = []
    for nodeid, reruns in sorted(flaky.items()):
        limit = allowed.get(nodeid, 0)
        if reruns > limit:
            failures.append(f"{nodeid}: {reruns} rerun(s) exceeds budget {limit}")

    if failures:
        print("TEST_RETRY_BUDGET_FAIL")
        for failure in failures:
            print(f" - {failure}")
        print("Fix the flakiness or record a reviewed budget in docs/quality/flaky-test-baseline.json")
        return 1

    if flaky:
        print(f"TEST_RETRY_BUDGET_OK reruns={report.get('total_reruns', 0)} flaky={len(flaky)}")
        for nodeid, reruns in sorted(flaky.items()):
            print(f" - {reruns}x {nodeid}")
    else:
        print("TEST_RETRY_BUDGET_OK reruns=0 flaky=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
