"""
LangGraph State Machine — wires the nodes together with conditional edges.

Graph topology:

    ┌─────────┐
    │  START  │
    └────┬────┘
         │
    ┌────▼─────┐
    │  Router  │  ← classify intent, pick model, detect VMD role
    └────┬─────┘
         │
    ┌────▼──────────┐
    │ after_router  │  ← conditional: multi-agent or standard?
    └───┬───────┬───┘
        │       │
    ┌───▼───┐ ┌─▼──────────┐
    │ Plan  │ │ WBS Decomp │  ← multi-agent path
    └───┬───┘ └─────┬──────┘
        │           │
        │     ┌─────▼───────┐
        │     │ Orchestrate │  ← delegates to sub-agents
        │     └─────┬───────┘
        │           │
    ┌───▼───┐       │
    │Execute│       │
    └───┬───┘       │
        │           │
    ┌───▼───┐  ┌────▼───┐
    │Reflect│  │Respond │  ← both paths converge
    └───┬───┘  └────┬───┘
        │           │
    ┌───▼───┐  ┌────▼───┐
    │Respond│  │  END   │
    └───┬───┘  └────────┘
        │
    ┌───▼───┐
    │  END  │
    └───────┘
"""

import hashlib
import json
import logging
from typing import Optional

from langgraph.graph import END, StateGraph

from app.agent.checkpointer import get_checkpointer
from app.agent.nodes import critic_node, error_node, execute_node, plan_node, reflect_node, respond_node
from app.agent.nodes_orchestrator import orchestrate_node
from app.agent.nodes_wbs import wbs_decompose_node
from app.agent.router import route_node
from app.agent.state import AgentState, QueryComplexity
from app.core.config import settings

logger = logging.getLogger(__name__)

# Track tool schema version for hot-reload
_tool_schema_version = 0


def get_tool_schema_version() -> int:
    """Get current tool schema version."""
    return _tool_schema_version


def increment_tool_schema_version():
    """Increment tool schema version (call when tools are reloaded)."""
    global _tool_schema_version
    _tool_schema_version += 1
    logger.info(f"[Graph] Tool schema version incremented to {_tool_schema_version}")


# ─── Loop Detection ──────────────────────────────────────────────────────────

# Maximum consecutive identical tool-call patterns before force-termination
_LOOP_REPEAT_THRESHOLD = 3


def _tool_call_fingerprint(tool_calls: list) -> str:
    """Generate a hash fingerprint for a set of tool calls (name + args)."""
    if not tool_calls:
        return ""
    parts = []
    for tc in sorted(tool_calls, key=lambda t: t.tool_name):
        args_str = json.dumps(tc.tool_args, sort_keys=True, ensure_ascii=False) if tc.tool_args else ""
        parts.append(f"{tc.tool_name}:{args_str}")
    combined = "|".join(parts)
    return hashlib.md5(combined.encode()).hexdigest()


def _detect_loop(state: AgentState) -> bool:
    """
    Check if the agent is stuck in a loop by examining completed tool calls.

    Detects patterns where the exact same set of tool calls (name + args)
    is repeated _LOOP_REPEAT_THRESHOLD times consecutively.
    """
    completed = state.get("completed_tool_calls", [])
    if len(completed) < _LOOP_REPEAT_THRESHOLD:
        return False

    # Group completed calls by iteration (using pending_tool_calls pattern)
    # Since completed_tool_calls accumulates via operator.add, we look at
    # the most recent batches. Each execute_node appends a batch.
    # Strategy: compare fingerprints of the last N pending batches.
    pending_history = state.get("_tool_call_history", [])
    if len(pending_history) >= _LOOP_REPEAT_THRESHOLD:
        # Check if the last N entries are all identical
        recent = pending_history[-_LOOP_REPEAT_THRESHOLD:]
        if len(set(recent)) == 1 and recent[0] != "":
            return True

    return False


# ─── Conditional Edge Functions ──────────────────────────────────────────────


def _after_plan(state: AgentState) -> str:
    """
    After planning:
      - If error occurred → error
      - If tool calls are pending → execute
      - SIMPLE queries skip reflection → respond directly
      - Otherwise → reflect (validates the direct answer)
    """
    if state.get("error"):
        return "error"
    if state.get("requires_tools") and state.get("pending_tool_calls"):
        return "execute"
    # Short-circuit: SIMPLE queries (greetings, FAQ) skip reflection
    if state.get("complexity") == QueryComplexity.SIMPLE:
        return "respond"
    return "reflect"


def _after_execute(state: AgentState) -> str:
    """
    After execution:
      - If error occurred → error
      - If loop detected (same tools called repeatedly) → reflect to finalize
      - Always go back to plan so the LLM can synthesize tool results.
      - Guard: if iteration limit reached → reflect to finalize.
    """
    if state.get("error"):
        return "error"

    config = state.get("config")
    max_iter = config.max_iterations if config else 5
    iteration = state.get("iteration", 0)

    if iteration >= max_iter:
        logger.warning(f"[Graph] Max iterations ({max_iter}) reached, forcing reflect")
        return "reflect"

    # P2: Loop detection — prevent infinite plan→execute→plan cycles
    if _detect_loop(state):
        logger.warning(
            f"[Graph] Loop detected after {iteration} iterations "
            f"(same tool calls repeated {_LOOP_REPEAT_THRESHOLD}x), forcing reflect"
        )
        return "reflect"

    return "plan"


def _after_reflect(state: AgentState) -> str:
    """
    After reflection:
      - If needs_replanning (hallucination detected) → back to plan
      - COMPLEX/CRITICAL queries → critic (P1-5 quality gate)
      - Otherwise → respond (finalize)
    """
    if state.get("needs_replanning"):
        config = state.get("config")
        max_iter = config.max_iterations if config else 5
        iteration = state.get("iteration", 0)
        if iteration < max_iter:
            return "plan"
        logger.warning("[Graph] Needs replanning but max iterations reached, responding anyway")

    # P1-5: Route COMPLEX/CRITICAL through critic before respond
    complexity = state.get("complexity")
    if complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL):
        return "critic"

    return "respond"


def _after_error(state: AgentState) -> str:
    """
    After error recovery attempt:
      - If recovery worked (error cleared) → plan
      - Otherwise → respond (with error message)
    """
    if state.get("error"):
        return "respond"
    return "plan"


def _after_router(state: AgentState) -> str:
    """
    After routing:
      - If the router detected a multi-agent orchestration scenario
        (agent_code is set AND scene_code indicates decomposition needed
         AND complexity is COMPLEX) → wbs_decompose
      - Otherwise → plan (standard single-agent flow)
    """
    agent_code = state.get("agent_code", "")
    scene_code = state.get("scene_code", "")

    # Check if this needs multi-agent WBS decomposition
    # Trigger conditions: agent_code is set AND it's a complex task needing orchestration
    if agent_code and scene_code == "task_decompose":
        return "wbs_decompose"

    return "plan"


def _after_orchestrate(state: AgentState) -> str:
    """
    After orchestration:
      - If error occurred → error
      - Otherwise → critic (P1-5: quality gate before respond)
    """
    if state.get("error"):
        return "error"
    return "critic"


def _after_critic(state: AgentState) -> str:
    """
    P1-5: After critic evaluation:
      - If critic passed → respond
      - If critic failed → plan (one correction pass, guarded by max_iterations)
    """
    if not state.get("critic_passed", True):
        config = state.get("config")
        max_iter = config.max_iterations if config else 5
        iteration = state.get("iteration", 0)
        if iteration < max_iter:
            return "plan"
        logger.warning("[Graph] Critic failed but max iterations reached, responding anyway")
    return "respond"


def _after_wbs(state: AgentState) -> str:
    """
    After WBS decomposition:
      - If error occurred → error
      - If wbs_structure is ready → orchestrate
      - Fallback → plan (degrade to single-agent)
    """
    if state.get("error"):
        return "error"
    if state.get("wbs_structure"):
        return "orchestrate"
    # Fallback to standard planning if WBS fails silently
    return "plan"


# ─── Graph Builder ───────────────────────────────────────────────────────────


def build_agent_graph() -> StateGraph:
    """
    Construct the LangGraph state machine.
    Returns an uncompiled StateGraph.

    Includes both the standard single-agent flow and the VMD multi-agent
    orchestration path (WBS decompose → orchestrate → respond).
    """
    graph = StateGraph(AgentState)

    # ── Add Nodes ──
    graph.add_node("router", route_node)
    graph.add_node("plan", plan_node)
    graph.add_node("execute", execute_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("respond", respond_node)
    graph.add_node("error", error_node)
    # VMD multi-agent nodes
    graph.add_node("wbs_decompose", wbs_decompose_node)
    graph.add_node("orchestrate", orchestrate_node)
    # P1-5: Independent quality evaluator
    graph.add_node("critic", critic_node)

    # ── Set Entry Point ──
    graph.set_entry_point("router")

    # ── Add Edges ──
    # router → plan | wbs_decompose (conditional: multi-agent or standard)
    graph.add_conditional_edges(
        "router",
        _after_router,
        {
            "plan": "plan",
            "wbs_decompose": "wbs_decompose",
        },
    )

    # wbs_decompose → orchestrate | error | plan (conditional)
    graph.add_conditional_edges(
        "wbs_decompose",
        _after_wbs,
        {
            "orchestrate": "orchestrate",
            "error": "error",
            "plan": "plan",
        },
    )

    # orchestrate → critic | error (conditional, P1-5)
    graph.add_conditional_edges(
        "orchestrate",
        _after_orchestrate,
        {
            "critic": "critic",
            "error": "error",
        },
    )

    # plan → execute | reflect | respond | error (conditional)
    graph.add_conditional_edges(
        "plan",
        _after_plan,
        {
            "execute": "execute",
            "reflect": "reflect",
            "respond": "respond",
            "error": "error",
        },
    )

    # execute → plan | reflect | error (conditional)
    graph.add_conditional_edges(
        "execute",
        _after_execute,
        {
            "plan": "plan",
            "reflect": "reflect",
            "error": "error",
        },
    )

    # reflect → plan | respond | critic (conditional, P1-5)
    graph.add_conditional_edges(
        "reflect",
        _after_reflect,
        {
            "plan": "plan",
            "respond": "respond",
            "critic": "critic",
        },
    )

    # P1-5: critic → respond | plan (conditional)
    graph.add_conditional_edges(
        "critic",
        _after_critic,
        {
            "respond": "respond",
            "plan": "plan",
        },
    )

    # error → plan | respond (conditional)
    graph.add_conditional_edges(
        "error",
        _after_error,
        {
            "plan": "plan",
            "respond": "respond",
        },
    )

    # respond → END
    graph.add_edge("respond", END)

    return graph


class AgentGraph:
    """
    Singleton wrapper around the compiled LangGraph agent.

    Supports:
    - Lazy compilation with configurable checkpointer
    - Hot-reload when tools change
    - Thread-based conversation isolation

    Usage:
        agent = AgentGraph()
        result = await agent.run(initial_state, thread_id="...")
        # or
        async for event in agent.stream(initial_state, thread_id="..."):
            ...
    """

    _instance: Optional["AgentGraph"] = None
    _compiled = None
    _checkpointer = None
    _compiled_version = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._compiled = None
            cls._instance._checkpointer = None
            cls._instance._compiled_version = 0
        return cls._instance

    @property
    def compiled(self):
        """
        Lazy-compile the graph on first access.
        Auto-recompiles if tool schema version changed.
        """
        current_version = get_tool_schema_version()

        if self._compiled is not None and self._compiled_version == current_version:
            return self._compiled

        if self._checkpointer is None:
            self._checkpointer = get_checkpointer()

        logger.info(f"[AgentGraph] Compiling LangGraph state machine (version {current_version})...")
        graph = build_agent_graph()

        # Compile with checkpointer for state persistence and HITL
        self._compiled = graph.compile(checkpointer=self._checkpointer)
        self._compiled_version = current_version

        checkpointer_type = type(self._checkpointer).__name__
        logger.info(f"[AgentGraph] ✅ Graph compiled with {checkpointer_type}")

        return self._compiled

    def reload(self):
        """
        Force recompilation of the graph.
        Call this when tools are dynamically added/removed.
        """
        self._compiled = None
        increment_tool_schema_version()
        logger.info("[AgentGraph] Graph marked for reload on next access")

    async def run(self, initial_state: AgentState, thread_id: str = "default") -> AgentState:
        """
        Run the graph to completion and return the final state.
        Suitable for non-streaming use cases (tests, batch jobs).
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "recursion_limit": settings.LANGGRAPH_MAX_ITERATIONS * 3 + 5,
        }
        return await self.compiled.ainvoke(initial_state, config=config)

    async def stream(self, initial_state: AgentState, thread_id: str = "default"):
        """
        Async generator that yields intermediate state updates.
        Each yielded item is a dict with the node name and state delta.
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "recursion_limit": settings.LANGGRAPH_MAX_ITERATIONS * 3 + 5,
        }
        async for event in self.compiled.astream(initial_state, config=config):
            yield event

    async def astream_events(
        self, initial_state: AgentState, thread_id: str = "default", version: str = "v2", config: dict | None = None
    ):
        """
        Async generator for granular events (token streaming, etc.).
        If config is provided, it will be merged with the default config.
        """
        base_config = {
            "configurable": {
                "thread_id": thread_id,
            },
            "recursion_limit": settings.LANGGRAPH_MAX_ITERATIONS * 3 + 5,
        }
        if config:
            # Merge configurable keys from caller (e.g. trace_logger)
            base_config["configurable"].update(config.get("configurable", {}))
        async for event in self.compiled.astream_events(initial_state, config=base_config, version=version):
            yield event

    async def get_state(self, thread_id: str) -> AgentState | None:
        """
        Retrieve the persisted state for a thread.
        Useful for resuming interrupted conversations.
        """
        config = {"configurable": {"thread_id": thread_id}}
        state_snapshot = await self.compiled.aget_state(config)
        return state_snapshot.values if state_snapshot else None

    async def update_state(self, thread_id: str, updates: dict):
        """
        Update the persisted state for a thread.
        Useful for human-in-the-loop confirmations.
        """
        config = {"configurable": {"thread_id": thread_id}}
        await self.compiled.aupdate_state(config, updates)


# Convenience function to get singleton
def get_agent_graph() -> AgentGraph:
    """Get the singleton AgentGraph instance."""
    return AgentGraph()
