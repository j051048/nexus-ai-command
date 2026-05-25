from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_kingdee_auth_runs_before_tenant_and_integration_checks():
    kingdee = read("nexus_backend/app/routers/kingdee.py")
    assert "_kingdee_identity" in kingdee
    assert "Depends(get_current_user_id)" in kingdee
    assert "await get_current_org_id(request)" in kingdee
    assert "identity: tuple[str, str] = Depends(_kingdee_identity)" in kingdee


def test_prompt_firewall_test_environment_cannot_call_live_llm_judge():
    firewall = read("nexus_backend/app/core/prompt_firewall.py")
    tests = read("nexus_backend/tests/unit/test_prompt_firewall_fast_path.py")
    assert "PROMPT_FIREWALL_LLM_JUDGE" in firewall
    assert "PYTEST_CURRENT_TEST" in firewall
    assert "enable_llm_judge = False" in firewall
    assert "test_pytest_environment_disables_llm_judge" in tests


def test_customer_acceptance_selectors_match_runtime_components():
    sidebar = read("src/components/layout/Sidebar.tsx")
    chat_input = read("src/components/ai/chat/ChatInputArea.tsx")
    acceptance = read("e2e/customer-business-acceptance.spec.ts")
    app = read("src/App.tsx")
    boss_dashboard = read("src/components/dashboard/BossDashboard.tsx")

    assert 'data-testid="sidebar-main"' in sidebar
    assert 'data-testid="chat-input"' in chat_input
    assert "page.getByTestId('chat-input')" in acceptance
    assert "page.getByTestId('sidebar-main')" in acceptance
    assert '<Navigate to="/dashboard" replace />' in app
    assert '<Navigate to="/dashboard" replace />' in boss_dashboard
