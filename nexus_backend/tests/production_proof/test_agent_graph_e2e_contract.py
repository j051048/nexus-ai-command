from __future__ import annotations

import os

import pytest


def test_agent_graph_e2e_contract_names_required_artifacts(llm_replay_cassette):
    for case in llm_replay_cassette["cases"]:
        assert case["input"]
        assert case["expected_tool_calls"]
        assert case["recorded_response"]["tool_calls"] == case["expected_tool_calls"]
        assert case["recorded_response"]["intent"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_graph_real_ainvoke_is_opt_in():
    if os.getenv("RUN_REAL_AGENT_GRAPH_E2E") != "1":
        pytest.skip("Set RUN_REAL_AGENT_GRAPH_E2E=1 to call graph.ainvoke with real dependencies.")

    from langchain_core.messages import HumanMessage

    from app.agent.graph import get_agent_graph
    from app.agent.state import AgentConfig, AgentPhase

    state = {
        "messages": [HumanMessage(content="Find customers not contacted for 30 days and draft next steps.")],
        "current_phase": AgentPhase.ROUTING,
        "iteration": 0,
        "pending_tool_calls": [],
        "completed_tool_calls": [],
        "thinking_steps": [],
        "config": AgentConfig(
            user_id=os.getenv("TEST_USER_ID", "proof-user"),
            org_id=os.getenv("TEST_ORG_ID", "proof-org"),
            session_id="production-proof-session",
            user_role="admin",
            token=os.getenv("TEST_USER_TOKEN", "proof-token"),
        ),
    }
    result = await get_agent_graph().run(state, thread_id="production-proof-session")
    assert result.get("messages")
    assert result.get("tool_calls") or result.get("completed_tools") or result.get("response")
