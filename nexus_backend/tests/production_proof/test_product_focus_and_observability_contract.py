from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_core_product_focus_is_guarded_by_module_tiers():
    flags = read("src/config/featureFlags.ts")
    launch_modules = read("src/config/customerLaunchModules.ts")
    mobile_workbench = read("src/components/mobile/MobileWorkbenchPage.tsx")

    for core_module in ["crm", "approval", "documents", "knowledge", "vmd"]:
        assert core_module in flags
        assert f'flag: "{core_module}"' in launch_modules
    assert "MODULE_TIER_LABELS" in flags
    assert "MODULE_FOCUS_POLICY" in flags
    assert "THIRD_PARTY_FIRST_MODULES" in flags
    assert (
        "外部系统 / 低频入口" in mobile_workbench or "澶栭儴绯荤粺" in mobile_workbench
    )


def test_agent_quality_and_business_audit_are_customer_visible():
    ops_page = read("src/pages/AIOperatingSystemPage.tsx")
    improvement_page = read("src/pages/AgentImprovementCenterPage.tsx")
    ops_service = read("nexus_backend/app/services/agent_evolution_ops_service.py")
    dashboard_router = read("nexus_backend/app/routers/dashboard.py")
    action_analytics = read("src/pages/ActionAnalyticsPage.tsx")

    assert "AI 价值与信任仪表盘" in ops_page
    assert "audit_summary" in ops_page
    assert "reward_model" in improvement_page
    assert "redteam_center" in improvement_page
    assert "build_trust_center_report" in ops_service
    assert "agent_ci_score" in ops_service
    assert "/roi" in dashboard_router
    assert "/ai-weekly-report" in dashboard_router
    assert "Boss View" in improvement_page
    assert "Admin Control Plane" in improvement_page
    assert "高风险未闭环" in action_analytics or "楂橀闄╂湭闂幆" in action_analytics
