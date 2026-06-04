from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_tool_failure_attribution_contract_is_available():
    from app.agent.tool_failure_attribution import classify_tool_failure

    assert (
        classify_tool_failure({"error_type": "param_error"}).category
        == "invalid_params"
    )
    assert (
        classify_tool_failure({"result": "403 forbidden"}).category
        == "permission_denied"
    )
    assert classify_tool_failure({"result": "request timeout"}).category == "timeout"


def test_agent_graph_uses_tool_failure_attribution():
    graph = (ROOT / "nexus_backend/app/agent/graph.py").read_text(encoding="utf-8")
    assert "classify_tool_failure" in graph
    assert "retryable=" in graph
    assert "confidence=" in graph
