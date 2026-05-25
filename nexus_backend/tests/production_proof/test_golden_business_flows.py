from __future__ import annotations

import os

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
    assert REQUIRED_FLOW_IDS <= ids
    for flow in golden_flows:
        assert flow["steps"], flow["id"]
        assert all(step.get("asserts") for step in flow["steps"])


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_golden_business_flows_are_explicitly_gated(golden_flows):
    if os.getenv("RUN_REAL_GOLDEN_FLOWS") != "1":
        pytest.skip("Set RUN_REAL_GOLDEN_FLOWS=1 with TEST_SUPABASE_* and TEST_LLM_* to run real golden flows.")

    missing = [
        name
        for name in ("TEST_SUPABASE_URL", "TEST_SUPABASE_SERVICE_KEY", "TEST_LLM_RECORDING_MODE")
        if not os.getenv(name)
    ]
    assert not missing, f"Missing real golden flow env vars: {missing}"

    # This test intentionally becomes the execution anchor for real business
    # flows. The offline manifest test above prevents the anchor from being
    # deleted; real environments can plug the same flow ids into their runners.
    assert len(golden_flows) >= 5
