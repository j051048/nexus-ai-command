from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_aeon_inspired_agent_ops_backend_contract():
    service = read("nexus_backend/app/services/agent_ops_runtime_service.py")
    router = read("nexus_backend/app/routers/ai_operating_system.py")
    inbox = read("nexus_backend/app/routers/inbox.py")
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
        "register_heartbeat_schedule",
        "action_events",
        "trigger_actions",
    ]:
        assert token in service

    assert "/aeon-inspired-ops" in router
    assert "/aeon-inspired-ops/run-heartbeat" in router
    assert "/aeon-inspired-ops/register-heartbeat-schedule" in router
    assert "agent_ops_runtime_service" in router
    assert "_load_system_actions" in inbox
    assert "Reactive trigger fired" in inbox
    assert "agent_heartbeat_runs" in migration
    assert "agent_external_capabilities" in migration


def test_aeon_inspired_agent_ops_frontend_contract():
    hook = read("src/hooks/useAIOperatingSystem.ts")
    page = read("src/pages/AgentImprovementCenterPage.tsx")
    runtime = read("src/components/agent-ops/AgentOpsRuntime.tsx")

    assert "useAeonInspiredOps" in hook
    assert "useRunAeonInspiredHeartbeat" in hook
    assert "useRegisterAeonHeartbeatSchedule" in hook
    assert "AeonInspiredOpsResult" in hook
    assert "aeon-inspired-ops" in hook
    assert "AgentOpsRuntime" in page
    assert 'value="runtime"' in page
    assert "onRunHeartbeat" in page
    assert "onRegisterSchedule" in page
    assert "onClick={onRunHeartbeat}" in runtime
    assert "onClick={onRegisterSchedule}" in runtime


def test_agent_improvement_center_visible_text_is_utf8_clean():
    page = read("src/pages/AgentImprovementCenterPage.tsx")
    service = read("nexus_backend/app/services/agent_ops_runtime_service.py")

    for content in (page, service):
        assert "\ufffd" not in content
        for token in ["鍐", "杩", "姣", "鏆", "绔炲搧", "棰勭畻"]:
            assert token not in content

    assert "Agent 运营中心" in page
    assert "科学仪器" in service
