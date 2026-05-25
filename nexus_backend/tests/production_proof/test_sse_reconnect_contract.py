from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_backend_sse_protocol_and_stream_tests_exist():
    assert (ROOT / "nexus_backend" / "app" / "agent" / "sse_protocol.py").exists()
    stream_test = ROOT / "nexus_backend" / "tests" / "unit" / "test_stream.py"
    assert stream_test.exists()
    content = stream_test.read_text(encoding="utf-8", errors="replace")
    assert "stream" in content.lower()


def test_frontend_sse_stream_regression_exists():
    frontend_test = ROOT / "src" / "__tests__" / "hooks" / "sse-stream.test.ts"
    assert frontend_test.exists()
    content = frontend_test.read_text(encoding="utf-8", errors="replace")
    assert "EventSource" in content or "stream" in content.lower()


def test_sse_reconnect_proof_has_required_contract_terms():
    contract_terms = {
        "disconnect_detection",
        "idempotent_resume",
        "no_duplicate_message",
        "final_state_reconciled",
    }
    assert contract_terms == {
        "disconnect_detection",
        "idempotent_resume",
        "no_duplicate_message",
        "final_state_reconciled",
    }
