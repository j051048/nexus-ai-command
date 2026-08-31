from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_k6_profiles_exist_for_chat_and_small_company_paths():
    baseline = ROOT / "nexus_backend" / "tests" / "k6" / "baseline.js"
    small_company = ROOT / "nexus_backend" / "tests" / "k6" / "small_company.js"
    assert baseline.exists()
    assert small_company.exists()
    baseline_text = baseline.read_text(encoding="utf-8", errors="replace")
    small_text = small_company.read_text(encoding="utf-8", errors="replace")
    assert "/api/chat" in baseline_text or "/api/ai" in baseline_text
    assert "/api/chat" in small_text or "/api/ai" in small_text


def test_k6_separates_server_failures_from_expected_throttling():
    baseline_text = (ROOT / "nexus_backend" / "tests" / "k6" / "baseline.js").read_text(
        encoding="utf-8", errors="replace"
    )
    small_text = (
        ROOT / "nexus_backend" / "tests" / "k6" / "small_company.js"
    ).read_text(encoding="utf-8", errors="replace")
    workflow_text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8", errors="replace"
    )

    for profile in (baseline_text, small_text):
        assert "status >= 500" in profile
        assert "status >= 500 ||" not in profile
        assert "rate_limited" in profile
        assert "expectedStatuses" in profile

    assert 'RATE_LIMIT_PER_IP: "100000"' in workflow_text
    assert 'RATE_LIMIT_PER_MINUTE: "100000"' in workflow_text
    assert "rate_limited: ['rate<0.20']" in baseline_text
    assert "small_company_rate_limited: ['rate<0.15']" in small_text
    assert "/health/ready" not in small_text
    assert "/api/org-structure/employees" in small_text
    assert "/api/hr/employees" not in small_text


def test_performance_tests_cover_prompt_firewall_and_backend_load():
    load_test = ROOT / "nexus_backend" / "tests" / "performance" / "test_load.py"
    assert load_test.exists()
    content = load_test.read_text(encoding="utf-8", errors="replace")
    assert "PromptFirewall" in content or "firewall" in content.lower()
    assert "elapsed" in content
