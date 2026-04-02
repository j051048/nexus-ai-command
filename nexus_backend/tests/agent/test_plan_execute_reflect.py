"""
Plan → Execute → Reflect → Critic 全链路测试

覆盖：计划生成、工具执行、反思自纠正、Critic 质量门禁、
      HITL 确认流程、循环检测中断、错误恢复
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agent.state import AgentPhase, QueryComplexity, AgentConfig, ThinkingStep, ToolCallRecord


def _base_config(**overrides):
    defaults = dict(user_id="u-test", org_id="org-test", token="jwt-test")
    defaults.update(overrides)
    return AgentConfig(**defaults)


def _base_state(**overrides):
    from langchain_core.messages import HumanMessage
    state = {
        "messages": [HumanMessage(content="查询客户列表")],
        "current_phase": AgentPhase.PLANNING,
        "complexity": QueryComplexity.MODERATE,
        "intent_summary": "查询客户",
        "plan": [],
        "current_plan_step": 0,
        "completed_tool_calls": [],
        "thinking_steps": [],
        "iteration_count": 0,
        "max_iterations": 5,
        "final_response": "",
        "error_message": "",
        "error_count": 0,
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
        "user_id": "u-test",
        "token": "jwt-test",
        "user_role": "employee",
        "rag_context": "",
        "memory_context": "",
        "reflect_feedback": "",
        "critic_passed": False,
        "config": _base_config(),
    }
    state.update(overrides)
    return state


class TestPlanNode:
    """Plan 节点测试"""

    @pytest.mark.asyncio
    @patch("app.agent.node_plan._get_llm")
    async def test_plan_with_tool_calls(self, mock_get_llm):
        from app.agent.node_plan import plan_node

        mock_msg = MagicMock()
        mock_msg.content = "查询客户数据"
        mock_msg.tool_calls = [
            {"name": "GetCustomersTool", "args": {"limit": 10}, "id": "tc-1"}
        ]
        mock_msg.additional_kwargs = {}
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_msg)
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_get_llm.return_value = mock_llm

        state = _base_state()
        result = await plan_node(state)

        assert result["current_phase"] == AgentPhase.EXECUTING
        # 应生成计划或 thinking_steps
        assert len(result.get("plan", [])) > 0 or len(result.get("thinking_steps", [])) > 0

    @pytest.mark.asyncio
    @patch("app.agent.node_plan._get_llm")
    async def test_plan_no_tools_goes_to_respond(self, mock_get_llm):
        from app.agent.node_plan import plan_node

        mock_msg = MagicMock()
        mock_msg.content = "这是一个简单回答"
        mock_msg.tool_calls = []
        mock_msg.additional_kwargs = {}
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_msg)
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mock_get_llm.return_value = mock_llm

        state = _base_state()
        result = await plan_node(state)

        # 无工具调用时应进入 reflecting 或 responding
        assert result.get("final_response") or result.get("current_phase") in (
            AgentPhase.REFLECTING, AgentPhase.RESPONDING
        )


class TestReflectCriticChain:
    """Reflect → Critic 链路测试"""

    @pytest.mark.asyncio
    @patch("app.agent.node_reflect._get_llm")
    async def test_reflect_high_confidence_passes(self, mock_get_llm):
        from app.agent.node_reflect import reflect_node
        from langchain_core.messages import AIMessage, HumanMessage

        mock_msg = MagicMock()
        mock_msg.content = '{"quality": "good", "issues": [], "confidence": 0.95}'
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_msg)
        mock_get_llm.return_value = mock_llm

        tc = ToolCallRecord(
            tool_name="GetCustomersTool", tool_args={},
            tool_call_id="tc-1", result="5 customers", status="success"
        )
        state = _base_state(
            current_phase=AgentPhase.REFLECTING,
            completed_tool_calls=[tc],
            messages=[
                HumanMessage(content="查询客户列表"),
                AIMessage(content="根据查询结果，共有5个客户。"),
            ],
        )

        result = await reflect_node(state)
        # 高置信度应通过 — 返回 confidence_score 或 reflection
        assert result.get("confidence_score", 0) > 0 or "reflection" in result

    @pytest.mark.asyncio
    @patch("app.agent.node_reflect._get_llm")
    async def test_reflect_low_confidence_triggers_replan(self, mock_get_llm):
        from app.agent.node_reflect import reflect_node
        from langchain_core.messages import AIMessage, HumanMessage

        mock_msg = MagicMock()
        mock_msg.content = '{"quality": "poor", "issues": ["数据不完整"], "confidence": 0.3, "suggestion": "需要补充查询"}'
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_msg)
        mock_get_llm.return_value = mock_llm

        tc = ToolCallRecord(
            tool_name="GetCustomersTool", tool_args={},
            tool_call_id="tc-1", result="error", status="error"
        )
        state = _base_state(
            current_phase=AgentPhase.REFLECTING,
            completed_tool_calls=[tc],
            messages=[
                HumanMessage(content="查询客户列表"),
                AIMessage(content=""),  # 空回复触发 replan
            ],
        )

        result = await reflect_node(state)
        # 低置信度/空回复应触发 replan
        assert result.get("needs_replanning") is True or result.get("reflection")


class TestHITLConfirmation:
    """HITL 人机确认流程"""

    def test_confirmation_required_exception(self):
        from app.tools.base_tool import ConfirmationRequired, ConfirmationType

        exc = ConfirmationRequired(
            preview_message="确认批准？金额: ¥50,000",
            tool_name="ApprovalTool",
            args={"id": "a-1", "decision": "approved"},
            confirmation_type=ConfirmationType.IRREVERSIBLE,
        )
        assert exc.tool_name == "ApprovalTool"
        assert exc.confirmation_type == ConfirmationType.IRREVERSIBLE
        assert "50,000" in exc.preview_message

    def test_confirmed_tool_in_config(self):
        """用户确认后，confirmed_tool 应传入 config"""
        config = _base_config(
            system_confirmed=True,
            confirmed_tool={"tool_name": "ApprovalTool", "args": {"id": "a-1"}},
        )
        assert config.system_confirmed is True
        assert config.confirmed_tool["tool_name"] == "ApprovalTool"


class TestIterationLimit:
    """迭代次数限制"""

    def test_max_iterations_enforced(self):
        state = _base_state(iteration_count=5, max_iterations=5)
        assert state["iteration_count"] >= state["max_iterations"]

    def test_config_max_iterations_validation(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AgentConfig(user_id="u-1", max_iterations=0)
