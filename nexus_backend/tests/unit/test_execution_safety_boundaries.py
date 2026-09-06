from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent import node_execute
from app.agent.state import AgentConfig, ToolCallRecord
from app.tools.base_tool import BaseTool, ToolActionType


class BoundaryTool(BaseTool):
    name = "boundary_test_tool"
    description = "Test execution boundary"
    parameters = {"type": "object", "properties": {"amount": {"type": "number"}}}
    action_type = ToolActionType.MUTATE

    async def run(self, args, user_id, config=None):
        return "done"


@pytest.fixture
def boundary(monkeypatch):
    tool = BoundaryTool()
    tool.run = AsyncMock(side_effect=TimeoutError())
    monkeypatch.setattr(node_execute, "get_tool", lambda _: tool)
    monkeypatch.setattr(node_execute, "tool_circuit_breaker", MagicMock())
    monkeypatch.setattr("app.agent.loop_detector.record_tool_call_redis", AsyncMock(return_value=False))
    monkeypatch.setattr(node_execute, "run_hooks", AsyncMock(return_value={"tool_args": {}}))
    monkeypatch.setattr(node_execute, "check_symbolic_policy", AsyncMock(return_value=SimpleNamespace(allowed=True)))
    monkeypatch.setattr(node_execute, "record_tool_execution", MagicMock())
    monkeypatch.setattr(node_execute, "check_tool_alert", MagicMock())
    return tool


@pytest.mark.asyncio
async def test_uncertain_mutation_is_not_retried(boundary):
    result = await node_execute._execute_single_tool(
        ToolCallRecord(tool_call_id="call-boundary-1", tool_name=boundary.name, tool_args={}),
        AgentConfig(user_id="user", org_id="org", user_role="admin", session_id="session", tool_max_retries=3),
    )
    assert result.status == "error"
    assert boundary.run.await_count == 1


@pytest.mark.asyncio
async def test_hook_cannot_bypass_amount_confirmation(boundary, monkeypatch):
    monkeypatch.setattr(node_execute, "run_hooks", AsyncMock(return_value={"tool_args": {"amount": 100000}}))
    result = await node_execute._execute_single_tool(
        ToolCallRecord(tool_call_id="call-boundary-2", tool_name=boundary.name, tool_args={}),
        AgentConfig(user_id="user", org_id="org", user_role="admin", session_id="session"),
    )
    assert result.status == "blocked"
    boundary.run.assert_not_awaited()


def test_reviewed_catalog_matches_actual_tool_schema():
    from app.tools import get_tool
    from app.tools.reviewed_policies import REVIEWED_ACTIONS
    from app.agent.preflight_rules import PRE_FLIGHT_RULES

    for name, effect in REVIEWED_ACTIONS.items():
        tool = get_tool(name)
        assert tool is not None, name
        assert tool.action_type.value == effect, name
        if name in PRE_FLIGHT_RULES:
            assert PRE_FLIGHT_RULES[name].argument in tool.parameters["properties"]
