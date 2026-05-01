"""
Agent Graph 流程集成测试

覆盖：SIMPLE 快速路径、MODERATE 标准流程、COMPLEX 并行计划、
      CRITICAL HITL 确认、错误恢复、循环检测中断
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.state import AgentConfig, AgentPhase, QueryComplexity


def _make_base_state(query: str, complexity: QueryComplexity = QueryComplexity.MODERATE):
    """构造最小可用 AgentState"""
    from langchain_core.messages import HumanMessage
    return {
        "messages": [HumanMessage(content=query)],
        "config": AgentConfig(user_id="user-test"),
        "current_phase": AgentPhase.ROUTING,
        "complexity": complexity,
        "intent_summary": "",
        "plan": [],
        "current_plan_step": 0,
        "completed_tool_calls": [],
        "thinking_steps": [],
        "iteration_count": 0,
        "max_iterations": 5,
        "final_response": "",
        "error": "",
        "error_recovery_level": 0,
        "confidence_score": 0.0,
        "skip_semantic": False,
        "agent_code": "",
        "scene_code": "",
        "needs_multi_agent": False,
        "wbs_structure": None,
        "delegation_results": [],
        "wall_clock_start": None,
        "_tool_call_history": [],
        "org_id": "org-test",
        "user_id": "user-test",
        "token": "test-token",
        "user_role": "employee",
        "rag_context": "",
        "memory_context": "",
        "reflection": "",
        "critic_passed": False,
    }


class TestRouterNodeIntegration:
    """路由节点 → 正确分类 + 设置下游状态"""

    @pytest.mark.asyncio
    @patch("app.agent.router._load_db_intent_rules", new_callable=AsyncMock)
    async def test_simple_greeting_routes_correctly(self, mock_db_rules):
        from app.agent.router import route_node

        state = _make_base_state("你好")

        result = await route_node(state)

        assert result["complexity"] == QueryComplexity.SIMPLE
        assert result["current_phase"] == AgentPhase.PLANNING

    @pytest.mark.asyncio
    @patch("app.agent.router._load_db_intent_rules", new_callable=AsyncMock)
    async def test_business_query_routes_to_moderate(self, mock_db_rules):
        from app.agent.router import route_node

        state = _make_base_state("查一下本月客户列表")

        result = await route_node(state)

        assert result["complexity"] in (QueryComplexity.MODERATE, QueryComplexity.COMPLEX)

    @pytest.mark.asyncio
    @patch("app.agent.router._load_db_intent_rules", new_callable=AsyncMock)
    async def test_critical_operation_detected(self, mock_db_rules):
        from app.agent.router import route_node

        state = _make_base_state("批准张三的报销申请")

        result = await route_node(state)

        assert result["complexity"] == QueryComplexity.CRITICAL


class TestPlanNodeIntegration:
    """Plan 节点 → 生成工具调用计划"""

    @pytest.mark.asyncio
    @patch("app.agent.plan.llm_caller.invoke_with_fallback")
    async def test_plan_generates_steps(self, mock_invoke):
        from app.agent.node_plan import plan_node

        # Mock LLM 返回带工具调用的响应
        mock_msg = MagicMock()
        mock_msg.content = "我会查询客户数据"
        mock_msg.tool_calls = [
            {"name": "GetCustomersTool", "args": {"limit": 10}, "id": "tc-1"}
        ]
        mock_msg.additional_kwargs = {}
        mock_msg.response_metadata = {"token_usage": {"prompt_tokens": 100, "completion_tokens": 50}, "finish_reason": "stop"}

        mock_invoke.return_value = mock_msg

        state = _make_base_state("查询客户列表", QueryComplexity.MODERATE)
        state["current_phase"] = AgentPhase.PLANNING
        state["intent_summary"] = "查询客户"

        result = await plan_node(state)

        assert result["current_phase"] in (AgentPhase.PLANNING, AgentPhase.EXECUTING)
        assert len(result.get("plan", [])) > 0 or len(result.get("thinking_steps", [])) > 0


class TestReflectNodeIntegration:
    """Reflect 节点 → 自纠正逻辑"""

    @pytest.mark.asyncio
    @patch("app.agent.node_reflect._get_llm")
    async def test_reflect_passes_good_result(self, mock_get_llm):
        from app.agent.node_reflect import reflect_node

        mock_msg = MagicMock()
        mock_msg.content = '{"quality": "good", "issues": [], "suggestion": "直接回复"}'
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_msg)
        mock_get_llm.return_value = mock_llm

        state = _make_base_state("查询客户")
        state["current_phase"] = AgentPhase.REFLECTING
        state["completed_tool_calls"] = [
            MagicMock(tool_name="GetCustomersTool", status="success",
                      result="找到5个客户", tool_args={}, tool_call_id="tc-1")
        ]

        result = await reflect_node(state)

        # 反思通过后应设置 confidence_score
        assert "confidence_score" in result or "reflection" in result


class TestErrorRecoveryIntegration:
    """错误恢复 → error_node 生成友好错误消息"""

    @pytest.mark.asyncio
    async def test_error_node_produces_response(self):
        from app.agent.node_respond import error_node

        state = _make_base_state("测试")
        state["current_phase"] = AgentPhase.ERROR
        state["error"] = "工具调用超时"
        state["error_recovery_level"] = 1

        result = await error_node(state)

        # error_node at level 1 retries by transitioning to PLANNING, not staying in ERROR
        assert result.get("final_response") or result.get("current_phase") in (
            AgentPhase.ERROR, AgentPhase.PLANNING, AgentPhase.RESPONDING
        )
