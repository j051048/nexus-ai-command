from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_frontend_source_size_guard_is_wired_to_ci_and_package_scripts():
    size_gate = read("scripts/check_source_size.mjs")
    package_json = read("package.json")
    workflow = read(".github/workflows/test-full.yml")

    assert "SOURCE_SIZE_GATE_OK" in size_gate
    assert "MANAGED_DEBT" in size_gate
    assert "src/pages/OACenter.tsx" in size_gate
    assert '"check:size"' in package_json
    assert "npm run check:size" in workflow


def test_agent_eval_regression_gate_is_pr_ready():
    gate = read("scripts/agent_eval_regression_gate.py")
    workflow = read(".github/workflows/test-full.yml")
    proof_gate = read("scripts/production_proof_gate.py")

    assert "AGENT_EVAL_REGRESSION_OK" in gate
    assert "regression_tolerance = 0.02" in gate
    assert "baseline_scores.json" in gate
    assert "agent_quality_thresholds.json" in gate
    assert "python scripts/agent_eval_regression_gate.py" in workflow
    assert "Agent eval regression gate" in proof_gate


def test_security_gate_no_longer_requires_pip_audit_report_only_mode():
    policy = read("scripts/security_severity_gate.py")
    workflow = read(".github/workflows/test-full.yml")

    assert "pip-audit -r nexus_backend/requirements.txt --strict" in policy
    assert "pip-audit -r nexus_backend/requirements.txt --strict || true" not in policy
    assert "pip-audit -r nexus_backend/requirements.txt --strict" in workflow
    assert "pip-audit -r nexus_backend/requirements.txt --strict || true" not in workflow


def test_agent_slo_cost_is_visible_to_backend_and_frontend():
    service = read("nexus_backend/app/services/agent_slo_cost_service.py")
    dashboard = read("nexus_backend/app/routers/dashboard.py")
    hook = read("src/hooks/useAgentSloCost.ts")
    unit_test = read("nexus_backend/tests/unit/test_agent_slo_cost_service.py")

    for token in (
        "agent_success_rate_min",
        "agent_p95_duration_ms_max",
        "expensive_model_share_max",
        "daily_cost_usd_max",
    ):
        assert token in service
        assert token in hook
    assert '"/agent-slo-cost"' in dashboard
    assert "summarize_agent_slo_cost" in dashboard
    assert "gemini-3.1-pro-preview" in unit_test

