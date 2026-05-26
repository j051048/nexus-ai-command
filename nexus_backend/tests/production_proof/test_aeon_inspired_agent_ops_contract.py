from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_aeon_inspired_agent_ops_backend_contract():
    service = read("nexus_backend/app/services/agent_ops_runtime_service.py")
    router = read("nexus_backend/app/routers/ai_operating_system.py")
    migration = read("supabase/migrations/20260526_agent_ops_runtime.sql")

    for token in [
        "build_heartbeat",
        "build_skill_health",
        "build_reactive_triggers",
        "build_self_repair",
        "build_skill_chains",
        "build_universal_var",
        "build_operating_memory",
        "build_instance_fleet",
        "build_persona_soul",
        "build_external_capabilities",
        "persist_dashboard",
    ]:
        assert token in service

    assert "/aeon-inspired-ops" in router
    assert "/aeon-inspired-ops/run-heartbeat" in router
    assert "agent_ops_runtime_service" in router
    assert "agent_heartbeat_runs" in migration
    assert "agent_external_capabilities" in migration


def test_aeon_inspired_agent_ops_frontend_contract():
    hook = read("src/hooks/useAIOperatingSystem.ts")
    page = read("src/pages/AgentImprovementCenterPage.tsx")

    assert "useAeonInspiredOps" in hook
    assert "AeonInspiredOpsResult" in hook
    assert "aeon-inspired-ops" in hook
    assert "Aeon-style Agent Ops Runtime" in page
    assert "Heartbeat Supervisor" in page
    assert "MCP / A2A Capabilities" in page
