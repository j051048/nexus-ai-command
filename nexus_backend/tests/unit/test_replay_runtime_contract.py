from unittest.mock import AsyncMock

import pytest

from app.agent.state import ToolCallRecord
from app.services.full_graph_replay_service import FullGraphReplayService
from app.services.agent_replay_harness import AgentReplayHarness


def test_empty_execution_cannot_pass_a_zero_error_budget():
    assert not AgentReplayHarness().evaluate_trace({"steps": []}, {"max_errors": 0}).passed


@pytest.mark.asyncio
async def test_production_result_uses_completed_calls_and_scoped_unique_threads(monkeypatch):
    service = FullGraphReplayService()
    runner = AsyncMock(return_value={
        "completed_tool_calls": [ToolCallRecord(tool_name="load_knowledge", tool_args={},
                                              tool_call_id="c", status="success", result="evidence")],
        "final_response": "facts", "thinking_steps": [],
    })
    monkeypatch.setattr(service, "_execute_production_graph", runner)
    case = {"id": "a", "organization_id": "org-a", "user_id": "user-a", "message": "find", "expectations": {"successful_tools": ["load_knowledge"]}}
    first = await service.run_case(case)
    second = await service.run_case(case)
    assert first["passed"]
    assert first["execution_mode"] == "production_graph"
    assert first["thread_id"] != second["thread_id"]
    assert first["thread_id"].startswith("org-a::replay:user-a:")
    with pytest.raises(ValueError):
        await service.run_case({**case, "thread_id": "org-b::replay:user-a:other"})


def test_failed_tool_attempt_does_not_count_as_success():
    result = AgentReplayHarness().evaluate_trace(
        {"steps": [{"status": "error", "tool_calls": [{"tool_name": "load_knowledge", "status": "error"}]}]},
        {"successful_tools": ["load_knowledge"]},
    )
    assert not result.passed
def test_trace_does_not_return_credentials():
    from app.services.full_graph_replay_service import FullGraphReplayService

    result = FullGraphReplayService._json_safe_state({
        "config": {"token": "secret"},
        "details": {"api_key": "secret", "status": "done"},
    })
    assert "secret" not in str(result)
    assert result["details"]["status"] == "done"
