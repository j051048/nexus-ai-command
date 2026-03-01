"""
Tests for Agent graph — compilation, conditional edges, state machine topology.
"""

import pytest

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
from app.agent.state import AgentPhase, QueryComplexity


def _make_state(**overrides) -> dict:
    """Create a minimal AgentState dict for testing conditional edges."""
    from dataclasses import dataclass

    @dataclass
    class FakeConfig:
        max_iterations: int = 5

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
        assert _after_plan(state) == "execute"

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

    def test_singleton_returns_same_instance(self):
        g1 = AgentGraph()
        g2 = AgentGraph()
        assert g1 is g2

    def test_compiled_graph_is_cached(self):
        g = AgentGraph()
        compiled1 = g.compiled
        compiled2 = g.compiled
        assert compiled1 is compiled2
