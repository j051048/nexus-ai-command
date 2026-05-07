"""Static architecture guardrails for P0 platform regressions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_celery_registers_isolated_tool_tasks():
    content = read("nexus_backend/app/core/celery_app.py")
    assert '"app.tasks.tool_tasks"' in content


def test_browser_ai_proxy_fallback_is_policy_gated():
    content = read("src/hooks/useAIStream.ts")
    assert "VITE_ENABLE_BROWSER_AI_PROXY_FALLBACK" in content
    assert "Browser-side AI proxy fallback is disabled by policy" in content


def test_pwa_precache_is_bounded():
    content = read("vite.config.ts")
    assert "maximumFileSizeToCacheInBytes" in content
    assert "vendor-syntax" in content


def test_static_rls_scanner_covers_common_tenant_columns():
    content = read("scripts/scan_rls_coverage.py")
    assert "organization_id" in content
    assert "org_id" in content
    assert "tenant_id" in content
