"""
Backend test suite for Agent core functionality.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from app.agent.graph_state import GraphState


@pytest.mark.asyncio
async def test_router_simple_intent():
    """测试简单意图路由"""
    from app.agent.nodes.router import router_node

    with patch('app.agent.nodes.router.get_llm') as mock_llm:
        # Mock LLM 返回简单查询
        mock_llm.return_value.ainvoke = AsyncMock(return_value=AIMessage(
            content="查询客户信息",
            additional_kwargs={"complexity": "SIMPLE"}
        ))

        state = GraphState(
            messages=[HumanMessage(content="查询客户123的信息")],
            user_id="test_user",
            org_id="test_org"
        )

        result = await router_node(state)

        assert result["complexity"] == "SIMPLE"
        assert result["next"] in ["simple_respond", "execute"]


@pytest.mark.asyncio
async def test_execute_node_with_tools():
    """测试工具执行节点"""
    from app.agent.nodes.execute import execute_node

    state = GraphState(
        messages=[
            HumanMessage(content="查询客户"),
            AIMessage(content="", tool_calls=[{
                "name": "get_customer",
                "args": {"customer_id": "123"},
                "id": "call_1"
            }])
        ],
        user_id="test_user",
        org_id="test_org"
    )

    with patch('app.tools.crm_tools.get_customer') as mock_tool:
        mock_tool.return_value = {"id": "123", "name": "测试客户"}

        result = await execute_node(state)

        assert len(result["messages"]) > 0
        assert result["tool_results"] is not None


@pytest.mark.asyncio
async def test_loop_detection():
    """测试循环检测"""
    from app.agent.node_helpers import detect_loop

    state = GraphState(
        messages=[HumanMessage(content="test")] * 10,
        user_id="test_user",
        org_id="test_org",
        iteration_count=6
    )

    is_loop = detect_loop(state)
    assert is_loop is True
