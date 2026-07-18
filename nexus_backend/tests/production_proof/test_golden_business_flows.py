from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REQUIRED_FLOW_IDS = {
    "golden-login-crm-ai-approval-close",
    "golden-stale-customer-next-best-action",
    "golden-tender-score-to-boss-review",
    "golden-contract-renewal-risk",
    "golden-cross-tenant-deny",
}


def test_golden_business_flow_manifest_covers_five_paths(golden_flows):
    ids = {flow["id"] for flow in golden_flows}
    assert ids >= REQUIRED_FLOW_IDS
    for flow in golden_flows:
        assert flow["steps"], flow["id"]
        assert all(step.get("asserts") for step in flow["steps"])


def test_five_golden_business_flows_execute_with_evidence(golden_flows):
    from app.services.golden_flow_runner import golden_flow_runner

    reports = [golden_flow_runner.run(flow) for flow in golden_flows]
    assert len(reports) >= 5
    assert all(report["passed"] for report in reports)
    assert all(report["audit_count"] == report["step_count"] for report in reports)


@pytest.mark.integration
def test_real_golden_business_flows_are_explicitly_gated(golden_flows):
    if os.getenv("RUN_REAL_GOLDEN_FLOWS") != "1":
        pytest.skip("Set RUN_REAL_GOLDEN_FLOWS=1 with isolated STAGING_* credentials.")

    missing = [
        name
        for name in (
            "STAGING_API_URL",
            "STAGING_GOLDEN_ORG_ID",
            "STAGING_EMPLOYEE_TOKEN",
            "STAGING_BOSS_TOKEN",
            "STAGING_OTHER_ORG_CUSTOMER_ID",
        )
        if not os.getenv(name)
    ]
    assert not missing, f"Missing real golden flow env vars: {missing}"
    root = Path(__file__).resolve().parents[3]
    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_staging_golden_flows.py")],
        cwd=root,
        env={**os.environ, "ALLOW_TEST_NETWORK": "1"},
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
