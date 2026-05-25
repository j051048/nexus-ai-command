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


def test_performance_tests_cover_prompt_firewall_and_backend_load():
    load_test = ROOT / "nexus_backend" / "tests" / "performance" / "test_load.py"
    assert load_test.exists()
    content = load_test.read_text(encoding="utf-8", errors="replace")
    assert "PromptFirewall" in content or "firewall" in content.lower()
    assert "elapsed" in content
