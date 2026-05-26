from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_agent_eval_baseline_uses_real_router_helper():
    service = read("nexus_backend/app/services/agent_eval_baseline_service.py")
    tests = read("nexus_backend/tests/production_proof/test_agent_quality_baselines.py")

    assert "_intent_for" in service
    assert "run_router_baseline" in service
    assert "agent_eval_baseline_service" in tests


def test_schema_convergence_audit_is_gateable():
    script = read("scripts/audit_schema_convergence.py")
    gate = read("scripts/production_proof_gate.py")

    assert "SCHEMA_CONVERGENCE_OK" in script
    assert "agent_heartbeat_runs" in script
    assert "audit_schema_convergence.py" in gate
