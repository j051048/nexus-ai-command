"""
Tests for Agent graph — compilation, conditional edges, state machine topology.
"""


from app.agent.graph import (
    AgentGraph,
    _after_error,
    _after_execute,
    _after_orchestrate,
    _after_plan,
    _after_reflect,
    _after_router,
    _after_wbs,
    build_agent_graph,
)


def _make_state(**overrides) -> dict:
    """Create a minimal AgentState dict for testing conditional edges."""
    from dataclasses import dataclass

    @dataclass
    class FakeConfig:
        max_iterations: int = 5
        system_confirmed: bool = False

    base = {
        "error": None,
        "requires_tools": False,
        "pending_tool_calls": [],
        "needs_replanning": False,
        "iteration": 0,
        "config": FakeConfig(),
        "agent_code": "",
        "scene_code": "",
        "wbs_structure": None,
    }
    base.update(overrides)
    return base


# ── Conditional Edge Tests ──


class TestAfterRouter:
    """Test routing decisions after intent classification."""

    def test_standard_flow_goes_to_plan(self):
        state = _make_state(agent_code="", scene_code="")
        assert _after_router(state) == "plan"

    def test_wbs_flow_with_task_decompose(self):
        state = _make_state(agent_code="sales_agent", scene_code="task_decompose")
        assert _after_router(state) == "wbs_decompose"

    def test_agent_code_without_decompose_goes_to_plan(self):
        state = _make_state(agent_code="sales_agent", scene_code="general")
        assert _after_router(state) == "plan"


class TestAfterPlan:
    """Test planning phase transitions."""

    def test_error_goes_to_error_node(self):
        state = _make_state(error="LLM failed")
        assert _after_plan(state) == "error"

    def test_tool_calls_go_to_execute(self):
        state = _make_state(requires_tools=True, pending_tool_calls=["tool1"])
        assert _after_plan(state) == "slot_verify"

    def test_no_tools_goes_to_reflect(self):
        state = _make_state(requires_tools=False, pending_tool_calls=[])
        assert _after_plan(state) == "reflect"

    def test_requires_tools_but_empty_list_goes_to_reflect(self):
        state = _make_state(requires_tools=True, pending_tool_calls=[])
        assert _after_plan(state) == "reflect"


class TestAfterExecute:
    """Test execution phase transitions."""

    def test_error_goes_to_error_node(self):
        state = _make_state(error="Tool failed")
        assert _after_execute(state) == "error"

    def test_under_limit_goes_back_to_plan(self):
        state = _make_state(iteration=2)
        assert _after_execute(state) == "plan"

    def test_at_limit_goes_to_reflect(self):
        state = _make_state(iteration=5)
        assert _after_execute(state) == "reflect"

    def test_over_limit_goes_to_reflect(self):
        state = _make_state(iteration=10)
        assert _after_execute(state) == "reflect"


class TestAfterReflect:
    """Test reflection phase transitions."""

    def test_no_replanning_goes_to_respond(self):
        state = _make_state(needs_replanning=False)
        assert _after_reflect(state) == "respond"

    def test_replanning_under_limit_goes_to_plan(self):
        state = _make_state(needs_replanning=True, iteration=2)
        assert _after_reflect(state) == "plan"

    def test_replanning_at_limit_goes_to_respond(self):
        state = _make_state(needs_replanning=True, iteration=5)
        assert _after_reflect(state) == "respond"


class TestAfterError:
    """Test error recovery transitions."""

    def test_error_still_present_goes_to_respond(self):
        state = _make_state(error="persistent error")
        assert _after_error(state) == "respond"

    def test_error_cleared_goes_to_plan(self):
        state = _make_state(error=None)
        assert _after_error(state) == "plan"


class TestAfterWBS:
    """Test WBS decomposition transitions."""

    def test_error_goes_to_error(self):
        state = _make_state(error="WBS failed")
        assert _after_wbs(state) == "error"

    def test_wbs_ready_goes_to_orchestrate(self):
        state = _make_state(wbs_structure={"sub_tasks": []})
        assert _after_wbs(state) == "orchestrate"

    def test_no_wbs_fallback_to_plan(self):
        state = _make_state(wbs_structure=None)
        assert _after_wbs(state) == "plan"


class TestAfterOrchestrate:
    """Test orchestration transitions."""

    def test_error_goes_to_error(self):
        state = _make_state(error="Orchestration failed")
        assert _after_orchestrate(state) == "error"

    def test_success_goes_to_critic(self):
        state = _make_state()
        assert _after_orchestrate(state) == "critic"


# ── Graph Build & Compile Tests ──


class TestGraphBuild:
    """Test graph construction."""

    def test_build_returns_state_graph(self):
        graph = build_agent_graph()
        assert graph is not None

    def test_graph_has_all_nodes(self):
        graph = build_agent_graph()
        node_names = set(graph.nodes.keys())
        expected = {"router", "plan", "execute", "reflect", "respond", "error", "wbs_decompose", "orchestrate"}
        assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"


class TestAgentGraphSingleton:
    """Test AgentGraph singleton behavior."""

    def setup_method(self):
        """Reset singleton state before each test."""
        AgentGraph._instance = None

    def teardown_method(self):
        """Reset singleton state after each test."""
        AgentGraph._instance = None

    def test_singleton_returns_same_instance(self):
        g1 = AgentGraph()
        g2 = AgentGraph()
        assert g1 is g2

    def test_compiled_graph_is_cached(self):
        from unittest.mock import patch

        with patch("app.agent.graph.get_checkpointer", return_value=None):
            g = AgentGraph()
            compiled1 = g.compiled
            compiled2 = g.compiled
            assert compiled1 is compiled2

# ── Advanced Condition Edge Tests ──

class TestLoopDetectionAndSafety:
    def test_after_execute_loop_first_time(self):
        state = _make_state(iteration=2)
        # Mock detect_loop to return True, but _loop_escape_attempted is False
        from unittest.mock import patch
        with patch("app.agent.graph._detect_loop", return_value=True):
            nxt = _after_execute(state)
            assert nxt == "plan"
            assert state["_loop_escape_attempted"] is True
            assert "⚠️ 检测到工具调用循环" in state["reflection_guidance"]

    def test_after_execute_loop_second_time(self):
        from unittest.mock import MagicMock, patch

        mock_tc = MagicMock()
        mock_tc.status = "success"
        mock_tc.tool_name = "mock_tool"

        state = _make_state(
            iteration=3,
            _loop_escape_attempted=True,
            completed_tool_calls=[mock_tc],
        )
        with patch("app.agent.graph._detect_loop", return_value=True), \
             patch("app.agent.graph.get_completed_tools", return_value=[mock_tc]), \
             patch("app.agent.graph._has_irreversible_tool", return_value=True):
            nxt = _after_execute(state)
            assert nxt == "reflect"
            assert state["circuit_break_reason"] == "loop_detected"

    def test_after_execute_confirmation_pending_for_hitl(self):
        state = _make_state(confirmation_pending=True)
        assert _after_execute(state) == "respond"

class TestFastSynthesis:
    def test_after_execute_all_tools_success_fast_synthesis(self):
        from unittest.mock import MagicMock, patch
        mock_tc = MagicMock()
        mock_tc.status = "success"
        mock_tc.tool_name = "mock_tool"
        
        state = _make_state(
            complexity="MODERATE",
            completed_tool_calls=[mock_tc]
        )
        with patch("app.agent.graph.get_completed_tools", return_value=state["completed_tool_calls"]), \
             patch("app.agent.graph._has_irreversible_tool", return_value=False):
             assert _after_execute(state) == "synthesize"

    def test_after_execute_irreversible_unconfirmed_goes_to_reflect(self):
        from unittest.mock import MagicMock, patch
        mock_tc = MagicMock()
        mock_tc.status = "success"
        mock_tc.tool_name = "mock_tool"
        
        state = _make_state(
            completed_tool_calls=[mock_tc]
        )
        # config with system_confirmed = False
        with patch("app.agent.graph.get_completed_tools", return_value=state["completed_tool_calls"]), \
             patch("app.agent.graph._has_irreversible_tool", return_value=True):
             assert _after_execute(state) == "reflect"

class TestSLODegradation:
    def test_after_reflect_slo_timeout(self):
        import time
        # Slo is 10.0 for normal, test elapsed > 8.0s
        state = _make_state(wall_clock_start=time.time() - 9.0)
        assert _after_reflect(state) == "respond"

class FakeConfig:
    def __init__(self, max_iterations=5, max_reflection_steps=2, require_hitl_approval=False, system_confirmed=False):
        self.max_iterations = max_iterations
        self.max_reflection_steps = max_reflection_steps
        self.require_hitl_approval = require_hitl_approval
        self.system_confirmed = system_confirmed

class TestAfterPlanConditionals:
    def test_after_plan_skip_reflect_when_budget_exhausted(self):
        state = _make_state(reflection_count=2, requires_tools=False)
        assert _after_plan(state) == "respond"

    def test_after_plan_fast_path_mutation(self):
        from unittest.mock import patch
        state = _make_state(requires_tools=False)
        with patch("app.agent.graph._is_mutation_fast_path", return_value=True):
            assert _after_plan(state) == "respond"
