"""
LangGraph State Machine — wires the nodes together with conditional edges.

Graph topology:

    ┌─────────┐
    │  START   │
    └────┬─────┘
         │
    ┌────▼─────┐
    │  Router  │  ← classify intent, pick model
    └────┬─────┘
         │
    ┌────▼─────┐    ┌──────────┐
    │  Plan    │◄───┤ Reflect  │  ← hallucination? loop back
    └────┬─────┘    └────▲─────┘
         │               │
         ├── has tools? ──┤
         │   YES          │ NO
    ┌────▼─────┐          │
    │ Execute  │──────────┘
    └──────────┘
         │
    (after reflect passes)
         │
    ┌────▼─────┐
    │ Respond  │  ← sanitize, finalize
    └────┬─────┘
         │
    ┌────▼─────┐
    │   END    │
    └──────────┘
"""

import logging
from typing import Optional

from langgraph.graph import StateGraph, END

from app.agent.state import AgentPhase, AgentState, QueryComplexity
from app.agent.nodes import plan_node, execute_node, reflect_node, respond_node
from app.agent.router import route_node

logger = logging.getLogger(__name__)


# ─── Conditional Edge Functions ──────────────────────────────────────────────

def _after_plan(state: AgentState) -> str:
    """
    After planning:
      - If tool calls are pending → execute
      - Otherwise → reflect (validates the direct answer)
    """
    if state.get("requires_tools") and state.get("pending_tool_calls"):
        return "execute"
    return "reflect"


def _after_execute(state: AgentState) -> str:
    """
    After execution:
      - Always go back to plan so the LLM can synthesize tool results.
      - Guard: if iteration limit reached → reflect to finalize.
    """
    config = state.get("config")
    max_iter = config.max_iterations if config else 5
    iteration = state.get("iteration", 0)

    if iteration >= max_iter:
        logger.warning(f"[Graph] Max iterations ({max_iter}) reached, forcing reflect")
        return "reflect"
    return "plan"


def _after_reflect(state: AgentState) -> str:
    """
    After reflection:
      - If needs_replanning (hallucination detected) → back to plan
      - Otherwise → respond (finalize)
    """
    if state.get("needs_replanning"):
        config = state.get("config")
        max_iter = config.max_iterations if config else 5
        iteration = state.get("iteration", 0)
        if iteration < max_iter:
            return "plan"
        logger.warning("[Graph] Needs replanning but max iterations reached, responding anyway")
    return "respond"


# ─── Graph Builder ───────────────────────────────────────────────────────────

def build_agent_graph() -> StateGraph:
    """
    Construct and compile the LangGraph state machine.

    Returns a compiled StateGraph ready for .invoke() or .astream().
    """
    graph = StateGraph(AgentState)

    # ── Add Nodes ──
    graph.add_node("router", route_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("respond", respond_node)

    # ── Set Entry Point ──
    graph.set_entry_point("router")

    # ── Add Edges ──
    # router → plan (always)
    graph.add_edge("router", "plan")

    # plan → execute | reflect (conditional)
    graph.add_conditional_edges("plan", _after_plan, {
        "execute": "execute",
        "reflect": "reflect",
    })

    # execute → plan | reflect (conditional)
    graph.add_conditional_edges("execute", _after_execute, {
        "plan": "plan",
        "reflect": "reflect",
    })

    # reflect → plan | respond (conditional)
    graph.add_conditional_edges("reflect", _after_reflect, {
        "plan": "plan",
        "respond": "respond",
    })

    # respond → END
    graph.add_edge("respond", END)

    return graph


class AgentGraph:
    """
    Singleton wrapper around the compiled LangGraph agent.

    Usage:
        agent = AgentGraph()
        result = await agent.run(initial_state)
        # or
        async for event in agent.stream(initial_state):
            ...
    """

    _instance: Optional["AgentGraph"] = None
    _compiled = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._compiled = None
        return cls._instance

    @property
    def compiled(self):
        """Lazy-compile the graph on first access."""
        if self._compiled is None:
            logger.info("[AgentGraph] Compiling LangGraph state machine...")
            graph = build_agent_graph()
            self._compiled = graph.compile()
            logger.info("[AgentGraph] ✅ Graph compiled successfully")
        return self._compiled

    async def run(self, initial_state: AgentState) -> AgentState:
        """
        Run the graph to completion and return the final state.
        Suitable for non-streaming use cases (tests, batch jobs).
        """
        return await self.compiled.ainvoke(initial_state)

    async def stream(self, initial_state: AgentState):
        """
        Async generator that yields intermediate state updates.
        Each yielded item is a dict with the node name and state delta.
        """
        async for event in self.compiled.astream(initial_state):
            yield event
