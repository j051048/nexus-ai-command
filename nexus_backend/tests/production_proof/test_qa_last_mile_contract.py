from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def load_json(path: str):
    return json.loads(read(path))


def test_qa_last_mile_gate_covers_five_missing_controls():
    gate = read("scripts/qa_last_mile_gate.py")
    workflow = read(".github/workflows/test-full.yml")
    proof_gate = read("scripts/production_proof_gate.py")

    for token in [
        "staging golden path contract",
        "chat acceleration latency budget contract",
        "agent eval quality thresholds",
        "frontend core-page visual regression contract",
        "security severity policy contract",
    ]:
        assert token in gate

    assert "qa_last_mile_gate.py" in workflow
    assert "security_severity_gate.py" in workflow
    assert "visual-regression.spec.ts" in workflow
    assert "QA last-mile contract" in proof_gate


def test_staging_golden_paths_are_real_flow_contracts():
    flows = load_json(
        "nexus_backend/tests/production_proof/fixtures/golden_business_flows.json"
    )
    ids = {flow["id"] for flow in flows}
    assert len(flows) >= 5
    assert {
        "golden-login-crm-ai-approval-close",
        "golden-stale-customer-next-best-action",
        "golden-tender-score-to-boss-review",
        "golden-contract-renewal-risk",
        "golden-cross-tenant-deny",
    }.issubset(ids)
    for flow in flows:
        assert flow["steps"]
        for step in flow["steps"]:
            assert step["asserts"]


def test_agent_quality_threshold_fixture_is_release_gate_ready():
    thresholds = load_json(
        "nexus_backend/tests/production_proof/fixtures/agent_quality_thresholds.json"
    )
    values = thresholds["thresholds"]
    assert values["intent_accuracy_min"] >= 0.75
    assert values["tool_selection_accuracy_min"] >= 0.8
    assert values["groundedness_min"] >= 0.8
    assert values["tenant_context_accuracy_min"] >= 0.95
    assert values["cost_regression_max_pct"] <= 10
    assert values["latency_regression_max_pct"] <= 20


def test_visual_regression_is_opt_in_but_ci_wired():
    spec = read("e2e/visual-regression.spec.ts")
    workflow = read(".github/workflows/test-full.yml")
    assert "RUN_VISUAL_REGRESSION" in spec
    assert "toHaveScreenshot" in spec
    for route in ["/dashboard", "/crm", "/approval", "/contracts", "/ai-operating-system"]:
        assert route in spec
    assert "RUN_VISUAL_REGRESSION" in workflow


def test_security_severity_gate_keeps_critical_as_hard_fail():
    gate = read("scripts/security_severity_gate.py")
    assert '"critical": "fail"' in gate
    assert "npm audit --omit=dev --audit-level=critical" in gate
    assert "scan_hardcoded_secrets.py" in gate
    assert "Trivy critical filesystem gate" in gate
