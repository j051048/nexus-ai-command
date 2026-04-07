"""
#2 — Agent Core Path (Agent 核心路径测试)

测试 LangGraph 状态机的节点转换:
- Route node: 简单查询 -> RESPONDING, 复杂查询 -> PLANNING
- Plan node: 生成计划并设置 requires_tools
- Execute node: 工具调用 mock -> 结果存储到 completed_tool_calls
- Reflect node: 对有工具支撑的回复设 is_hallucination=False
- Respond node: 生成 final_response
- 全流程: ROUTING -> PLANNING -> EXECUTING -> REFLECTING -> RESPONDING
"""

from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.state import (
    AgentConfig,
    AgentPhase,
    QueryComplexity,
    ToolCallRecord,
)

# ═══════════════════════════════════════════════════════════════════════════════
#  Route Node 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouteNode:
    """测试意图路由节点 (route_node)"""

    def _make_state(self, user_msg: str, config: AgentConfig) -> dict:
        """构建包含用户消息的 state"""
        return {
            "messages": [
                SystemMessage(content="你是一个AI助手"),
                HumanMessage(content=user_msg),
            ],
            "config": config,
            "current_phase": AgentPhase.ROUTING,
            "iteration": 0,
        }

    async def test_simple_greeting_routes_to_planning(self, mock_agent_config):
        """简单问候应被分类为 SIMPLE 复杂度"""
        from app.agent.router import route_node

        state = self._make_state("你好", mock_agent_config)
        result = await route_node(state)

        assert result["complexity"] == QueryComplexity.SIMPLE
        assert result["current_phase"] == AgentPhase.PLANNING

    async def test_complex_query_routes_correctly(self, mock_agent_config):
        """复杂分析查询应被分类为 COMPLEX 复杂度"""
        from app.agent.router import route_node

        state = self._make_state("请分析本月销售趋势并生成报告", mock_agent_config)
        result = await route_node(state)

        assert result["complexity"] == QueryComplexity.COMPLEX
        assert result["current_phase"] == AgentPhase.PLANNING

    async def test_critical_query_identified(self, mock_agent_config):
        """审批操作应被分类为 CRITICAL 复杂度"""
        from app.agent.router import route_node

        state = self._make_state("批准张三的报销申请", mock_agent_config)
        result = await route_node(state)

        assert result["complexity"] == QueryComplexity.CRITICAL

    async def test_moderate_query_identified(self, mock_agent_config):
        """工具查询应被分类为 MODERATE 复杂度"""
        from app.agent.router import route_node

        state = self._make_state("查询一下我的考勤记录", mock_agent_config)
        result = await route_node(state)

        assert result["complexity"] == QueryComplexity.MODERATE

    async def test_route_node_selects_model(self, mock_agent_config):
        """路由节点应根据复杂度选择合适的模型"""
        from app.agent.router import route_node

        state = self._make_state("你好", mock_agent_config)
        result = await route_node(state)

        assert "selected_model" in result
        # SIMPLE 应选择 mini model
        assert result["selected_model"] == mock_agent_config.mini_model

    async def test_route_node_returns_thinking_steps(self, mock_agent_config):
        """路由节点应返回 thinking_steps"""
        from app.agent.router import route_node

        state = self._make_state("你好", mock_agent_config)
        result = await route_node(state)

        assert "thinking_steps" in result
        assert len(result["thinking_steps"]) > 0
        assert result["thinking_steps"][0].phase == AgentPhase.ROUTING.value


# ═══════════════════════════════════════════════════════════════════════════════
#  Plan Node 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlanNode:
    """测试计划节点 (plan_node)"""

    async def test_plan_node_no_tools_for_simple(self, mock_agent_config):
        """SIMPLE 查询不应产生工具调用"""
        from app.agent.nodes import plan_node

        # 模拟 LLM 返回纯文本（无工具调用）
        mock_ai_msg = AIMessage(content="你好！有什么可以帮你的？")
        mock_ai_msg.response_metadata = {"token_usage": {"prompt_tokens": 10, "completion_tokens": 5}}
        mock_ai_msg.tool_calls = []

        state = {
            "messages": [
                SystemMessage(content="你是AI助手"),
                HumanMessage(content="你好"),
            ],
            "config": mock_agent_config,
            "complexity": QueryComplexity.SIMPLE,
            "selected_model": mock_agent_config.mini_model,
            "iteration": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }

        with (
            patch("app.agent.node_plan._get_llm") as mock_get_llm,
            patch("app.agent.node_plan.plugin_system_service.run_hooks", new_callable=AsyncMock),
            patch("app.agent.node_plan.llm_circuit_breaker") as mock_cb,
        ):
            mock_cb.allow_request.return_value = True
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_ai_msg)
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)
            mock_get_llm.return_value = mock_llm

            result = await plan_node(state)

        assert result["requires_tools"] is False
        assert result["current_phase"] == AgentPhase.REFLECTING
        assert len(result["pending_tool_calls"]) == 0

    async def test_plan_node_with_tool_calls(self, mock_agent_config):
        """复杂查询应产生工具调用"""
        from app.agent.nodes import plan_node

        # 模拟 LLM 返回工具调用
        mock_ai_msg = AIMessage(content="")
        mock_ai_msg.response_metadata = {"token_usage": {"prompt_tokens": 50, "completion_tokens": 30}}
        mock_ai_msg.tool_calls = [
            {"name": "query_knowledge_base", "args": {"query": "销售数据"}, "id": "tc-001"},
        ]

        state = {
            "messages": [
                SystemMessage(content="你是AI助手"),
                HumanMessage(content="查询本月销售数据"),
            ],
            "config": mock_agent_config,
            "complexity": QueryComplexity.MODERATE,
            "selected_model": mock_agent_config.model,
            "iteration": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }

        with (
            patch("app.agent.node_plan._get_llm") as mock_get_llm,
            patch("app.agent.node_plan.plugin_system_service.run_hooks", new_callable=AsyncMock),
            patch("app.agent.node_plan.llm_circuit_breaker") as mock_cb,
        ):
            mock_cb.allow_request.return_value = True
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_ai_msg)
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)
            mock_get_llm.return_value = mock_llm

            result = await plan_node(state)

        assert result["requires_tools"] is True
        assert result["current_phase"] == AgentPhase.EXECUTING
        assert len(result["pending_tool_calls"]) == 1
        assert result["pending_tool_calls"][0].tool_name == "query_knowledge_base"

    async def test_plan_node_circuit_breaker_open(self, mock_agent_config):
        """LLM 断路器打开时应返回 ERROR 阶段"""
        from app.agent.nodes import plan_node

        state = {
            "messages": [HumanMessage(content="测试")],
            "config": mock_agent_config,
            "complexity": QueryComplexity.MODERATE,
            "selected_model": mock_agent_config.model,
            "iteration": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
        }

        with patch("app.agent.node_plan.llm_circuit_breaker") as mock_cb:
            mock_cb.allow_request.return_value = False

            result = await plan_node(state)

        assert result["current_phase"] == AgentPhase.ERROR
        assert "error" in result


# ═══════════════════════════════════════════════════════════════════════════════
#  Execute Node 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecuteNode:
    """测试工具执行节点 (execute_node)"""

    async def test_execute_node_no_pending(self, mock_agent_config):
        """没有待执行工具时应直接进入 REFLECTING 阶段"""
        from app.agent.nodes import execute_node

        state = {
            "config": mock_agent_config,
            "pending_tool_calls": [],
            "completed_tool_calls": [],
            "iteration": 0,
        }

        result = await execute_node(state)
        assert result["current_phase"] == AgentPhase.REFLECTING

    async def test_execute_node_with_mocked_tool(self, mock_agent_config):
        """工具执行后结果应存储在 completed_tool_calls"""
        from app.agent.nodes import execute_node

        pending = [
            ToolCallRecord(
                tool_name="test_tool",
                tool_args={"query": "test"},
                tool_call_id="tc-001",
            )
        ]

        state = {
            "config": mock_agent_config,
            "pending_tool_calls": pending,
            "completed_tool_calls": [],
            "iteration": 0,
        }

        # mock _execute_single_tool 以避免真正执行
        async def fake_execute(record, config, cache=None, prior_completed_tools=None, trace_id=None):
            record.status = "success"
            record.result = "工具执行结果: 测试数据"
            record.duration_ms = 100
            return record

        with (
            patch("app.agent.node_execute._execute_single_tool", side_effect=fake_execute),
            patch("app.agent.node_execute.plugin_system_service.run_hooks", new_callable=AsyncMock),
            patch("app.services.content_moderation.check_user_input", return_value=(True, [])),
            patch("app.agent.node_execute.agent_trace_service", MagicMock()),
        ):
            result = await execute_node(state)

        assert result["current_phase"] == AgentPhase.PLANNING
        assert len(result["completed_tool_calls"]) == 1
        assert result["completed_tool_calls"][0].status == "success"
        assert result["iteration"] == 1

    async def test_execute_node_increments_iteration(self, mock_agent_config):
        """执行节点应递增 iteration 计数"""
        from app.agent.nodes import execute_node

        pending = [
            ToolCallRecord(
                tool_name="mock_tool",
                tool_args={},
                tool_call_id="tc-002",
            )
        ]

        state = {
            "config": mock_agent_config,
            "pending_tool_calls": pending,
            "completed_tool_calls": [],
            "iteration": 2,
        }

        async def fake_execute(record, config, cache=None, prior_completed_tools=None, trace_id=None):
            record.status = "success"
            record.result = "ok"
            return record

        with (
            patch("app.agent.node_execute._execute_single_tool", side_effect=fake_execute),
            patch("app.agent.node_execute.plugin_system_service.run_hooks", new_callable=AsyncMock),
            patch("app.services.content_moderation.check_user_input", return_value=(True, [])),
            patch("app.agent.node_execute.agent_trace_service", MagicMock()),
        ):
            result = await execute_node(state)

        assert result["iteration"] == 3


# ═══════════════════════════════════════════════════════════════════════════════
#  Reflect Node 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestReflectNode:
    """测试反思节点 (reflect_node)"""

    async def test_reflect_grounded_response_passes(self, mock_agent_config):
        """有工具支撑的正常回复应通过反思校验"""
        from app.agent.nodes import reflect_node

        # 设置 reflect_use_llm=False 避免外部 LLM 调用
        mock_agent_config.reflect_use_llm = False

        completed_tools = [
            ToolCallRecord(
                tool_name="query_sales",
                tool_args={"month": "2024-01"},
                tool_call_id="tc-001",
                result="本月销售额: 500000元",
                status="success",
            )
        ]

        state = {
            "messages": [
                HumanMessage(content="查询本月销售额"),
                AIMessage(content="根据查询结果，本月销售额为 500000元。"),
            ],
            "config": mock_agent_config,
            "iteration": 1,
            "complexity": QueryComplexity.MODERATE,
            "completed_tool_calls": completed_tools,
            "rag_context": "",
            "needs_replanning": False,
        }

        with (
            patch("app.agent.node_reflect.scan_content", return_value=(True, [])),
            patch("app.agent.node_reflect._verify_tool_grounding", new_callable=AsyncMock, return_value=None),
            patch("app.agent.node_reflect._check_data_source_primacy", return_value=None),
        ):
            result = await reflect_node(state)

        assert result["is_hallucination"] is False
        assert result["current_phase"] == AgentPhase.RESPONDING
        assert result["needs_replanning"] is False

    async def test_reflect_empty_response_triggers_replanning(self, mock_agent_config):
        """空回复且有工具结果时应触发重新规划"""
        from app.agent.nodes import reflect_node

        mock_agent_config.reflect_use_llm = False

        completed_tools = [
            ToolCallRecord(
                tool_name="query_data",
                tool_args={},
                tool_call_id="tc-001",
                result="数据结果",
                status="success",
            )
        ]

        state = {
            "messages": [
                HumanMessage(content="查询数据"),
                AIMessage(content=""),  # 空回复
            ],
            "config": mock_agent_config,
            "iteration": 0,
            "complexity": QueryComplexity.MODERATE,
            "completed_tool_calls": completed_tools,
            "rag_context": "",
            "needs_replanning": False,
        }

        result = await reflect_node(state)

        assert result["needs_replanning"] is True
        assert result["current_phase"] == AgentPhase.PLANNING

    async def test_reflect_hallucination_without_tools(self, mock_agent_config):
        """复杂查询无工具调用但声称有数据 -> 标记为幻觉"""
        from app.agent.nodes import reflect_node

        mock_agent_config.reflect_use_llm = False

        state = {
            "messages": [
                HumanMessage(content="查询本月业绩数据"),
                AIMessage(content="系统显示本月业绩为 1500000 元，同比增长 25%。"),
            ],
            "config": mock_agent_config,
            "iteration": 0,
            "complexity": QueryComplexity.COMPLEX,
            "completed_tool_calls": [],  # 没有工具调用
            "rag_context": "",
            "needs_replanning": False,
        }

        with patch("app.agent.node_reflect.scan_content", return_value=(True, [])):
            result = await reflect_node(state)

        assert result["is_hallucination"] is True

    async def test_reflect_confidence_high_with_tools(self, mock_agent_config):
        """有成功的工具调用时置信度应较高"""
        from app.agent.nodes import reflect_node

        mock_agent_config.reflect_use_llm = False

        completed_tools = [
            ToolCallRecord(
                tool_name="query_data",
                tool_args={},
                tool_call_id="tc-001",
                result="结果数据",
                status="success",
            )
        ]

        state = {
            "messages": [
                HumanMessage(content="查询数据"),
                AIMessage(content="根据查询结果，数据如下..."),
            ],
            "config": mock_agent_config,
            "iteration": 1,
            "complexity": QueryComplexity.MODERATE,
            "completed_tool_calls": completed_tools,
            "rag_context": "",
            "needs_replanning": False,
        }

        with patch("app.agent.node_reflect.scan_content", return_value=(True, [])):
            result = await reflect_node(state)

        assert result["confidence_score"] >= 0.9


# ═══════════════════════════════════════════════════════════════════════════════
#  Respond Node 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestRespondNode:
    """测试响应节点 (respond_node)"""

    async def test_respond_generates_final_response(self, mock_agent_config):
        """响应节点应生成 final_response 并进入 DONE 阶段"""
        from app.agent.nodes import respond_node

        state = {
            "messages": [AIMessage(content="这是最终回复")],
            "final_response": "这是最终回复",
            "config": mock_agent_config,
            "confidence_score": 0.9,
        }

        result = await respond_node(state)

        assert result["current_phase"] == AgentPhase.DONE
        assert "final_response" in result
        assert len(result["final_response"]) > 0

    async def test_respond_fallback_when_no_final_response(self, mock_agent_config):
        """final_response 为空时应从消息历史中提取"""
        from app.agent.nodes import respond_node

        state = {
            "messages": [
                HumanMessage(content="问题"),
                AIMessage(content="从消息历史提取的回复"),
            ],
            "final_response": "",
            "config": mock_agent_config,
            "confidence_score": 0.8,
        }

        result = await respond_node(state)

        assert result["current_phase"] == AgentPhase.DONE
        assert "从消息历史提取的回复" in result["final_response"]

    async def test_respond_masks_sensitive_for_employee(self, mock_agent_config):
        """employee 角色应无法看到薪资信息"""
        from app.agent.nodes import respond_node

        mock_agent_config.user_role = "employee"

        state = {
            "messages": [],
            "final_response": "张三的月薪: 25000元",
            "config": mock_agent_config,
            "confidence_score": 0.9,
        }

        result = await respond_node(state)

        assert "薪资信息已隐藏" in result["final_response"]
        assert "25000" not in result["final_response"]

    async def test_respond_no_mask_for_boss(self, mock_agent_config):
        """boss 角色应能看到薪资信息"""
        from app.agent.nodes import respond_node

        mock_agent_config.user_role = "boss"

        state = {
            "messages": [],
            "final_response": "张三的月薪: 25000元",
            "config": mock_agent_config,
            "confidence_score": 0.9,
        }

        result = await respond_node(state)

        # boss 应该能看到薪资
        assert "25000" in result["final_response"]
