"""
Core graph construction and compilation.
Extracted from monolithic graph.py.
"""

import asyncio
import logging
import time
from typing import Optional

from langgraph.graph import END, StateGraph

from app.agent.checkpointer import get_checkpointer
from app.agent.graph.conditional_edges import (
    after_critic,
    after_error,
    after_execute,
    after_orchestrate,
    after_plan,
    after_reflect,
    after_router,
    after_slot_verify,
    after_wbs,
)
from app.agent.middlewares import (
    audit_log_middleware,
    memory_inject_middleware,
    memory_update_middleware,
    tenant_context_middleware,
    token_limit_middleware,
)
from app.agent.node_parallel_context import parallel_context_and_plan
from app.agent.nodes import (
    critic_node,
    error_node,
    execute_node,
    plan_node,
    reflect_node,
    respond_node,
    simple_respond_node,
    slot_verify_node,
    synthesize_node,
)
from app.agent.nodes_orchestrator import orchestrate_node
from app.agent.nodes_wbs import wbs_decompose_node
from app.agent.router import route_node
from app.agent.state import AgentState
from app.core.agent_metrics import record_agent_execution
from app.core.config import settings
from app.core.timeout import with_timeout

logger = logging.getLogger(__name__)

_tool_schema_version = 0


def get_tool_schema_version() -> int:
    return _tool_schema_version


def increment_tool_schema_version():
    global _tool_schema_version
    _tool_schema_version += 1
    logger.info(f"[Graph] Tool schema version: {_tool_schema_version}")


def build_agent_graph() -> StateGraph:
    """Construct the LangGraph state machine."""
    graph = StateGraph(AgentState)

    # Middleware nodes
    graph.add_node("tenant_context", tenant_context_middleware)
    graph.add_node("memory_inject", memory_inject_middleware)
    graph.add_node("token_limit", token_limit_middleware)

    # Core nodes
    graph.add_node("router", route_node)
    graph.add_node("plan", plan_node)
    graph.add_node("parallel_plan", parallel_context_and_plan)
    graph.add_node("execute", execute_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("respond", respond_node)
    graph.add_node("simple_respond", simple_respond_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("error", error_node)
    graph.add_node("slot_verify", slot_verify_node)
    graph.add_node("wbs_decompose", wbs_decompose_node)
    graph.add_node("orchestrate", orchestrate_node)
    graph.add_node("critic", critic_node)

    # Post-middleware
    graph.add_node("audit_log", audit_log_middleware)
    graph.add_node("memory_update", memory_update_middleware)

    # Entry point
    graph.set_entry_point("tenant_context")

    # Middleware chain
    graph.add_edge("tenant_context", "memory_inject")
    graph.add_edge("memory_inject", "token_limit")
    graph.add_edge("token_limit", "router")

    # Conditional edges
    graph.add_conditional_edges(
        "router",
        after_router,
        {
            "plan": "plan",
            "parallel_plan": "parallel_plan",
            "wbs_decompose": "wbs_decompose",
            "simple_respond": "simple_respond",
        },
    )

    graph.add_conditional_edges(
        "wbs_decompose",
        after_wbs,
        {"orchestrate": "orchestrate", "error": "error", "plan": "plan"},
    )

    graph.add_conditional_edges(
        "orchestrate",
        after_orchestrate,
        {"critic": "critic", "error": "error"},
    )

    graph.add_conditional_edges(
        "plan",
        after_plan,
        {
            "slot_verify": "slot_verify",
            "reflect": "reflect",
            "respond": "respond",
            "error": "error",
        },
    )

    graph.add_conditional_edges(
        "parallel_plan",
        after_plan,
        {
            "slot_verify": "slot_verify",
            "reflect": "reflect",
            "respond": "respond",
            "error": "error",
        },
    )

    graph.add_conditional_edges(
        "slot_verify",
        after_slot_verify,
        {"execute": "execute", "respond": "respond", "error": "error"},
    )

    graph.add_conditional_edges(
        "execute",
        after_execute,
        {
            "plan": "plan",
            "synthesize": "synthesize",
            "reflect": "reflect",
            "respond": "respond",
            "error": "error",
        },
    )

    graph.add_conditional_edges(
        "reflect",
        after_reflect,
        {"plan": "plan", "respond": "respond", "critic": "critic"},
    )

    graph.add_conditional_edges(
        "critic",
        after_critic,
        {"respond": "respond", "plan": "plan"},
    )

    graph.add_conditional_edges(
        "error",
        after_error,
        {"plan": "plan", "respond": "respond"},
    )

    graph.add_edge("respond", "audit_log")
    graph.add_edge("audit_log", "memory_update")
    graph.add_edge("memory_update", END)
    graph.add_edge("simple_respond", "audit_log")
    graph.add_edge("synthesize", "respond")

    return graph


class AgentGraph:
    """Singleton wrapper around compiled LangGraph agent."""

    _instance: Optional["AgentGraph"] = None
    _compiled = None
    _checkpointer = None
    _compiled_version = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def compiled(self):
        current_version = get_tool_schema_version()
        if self._compiled and self._compiled_version == current_version:
            return self._compiled

        if self._checkpointer is None:
            self._checkpointer = get_checkpointer()

        logger.info(f"[AgentGraph] Compiling (v{current_version})...")
        t0 = time.monotonic()
        graph = build_agent_graph()
        self._compiled = graph.compile(checkpointer=self._checkpointer)
        self._compiled_version = current_version
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info(f"[AgentGraph] Compiled in {elapsed_ms}ms")
        return self._compiled

    def reload(self):
        self._compiled = None
        increment_tool_schema_version()

    @with_timeout(120)
    async def run(self, initial_state: AgentState, thread_id: str = "default"):
        messages = initial_state.get("messages", [])
        if len(messages) > 50:
            initial_state["final_response"] = "对话轮次已达上限（50轮）"
            initial_state["error"] = "MAX_TURNS_EXCEEDED"
            return initial_state

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": settings.LANGGRAPH_MAX_ITERATIONS * 5 + 10,
        }

        start_time = time.time()
        try:
            result = await self.compiled.ainvoke(initial_state, config=config)
            duration = time.time() - start_time
            tokens = result.get("total_input_tokens", 0) + result.get("total_output_tokens", 0)
            record_agent_execution(
                user_id=result.get("config", {}).get("user_id", "unknown"),
                complexity=str(result.get("complexity", "unknown")),
                model=result.get("selected_model", "unknown"),
                tokens=tokens,
                cost=tokens * 0.00001,
                duration=duration,
                success=not result.get("error"),
            )
            return result
        except Exception:
            record_agent_execution(
                user_id=initial_state.get("config", {}).get("user_id", "unknown"),
                complexity="unknown",
                model="unknown",
                tokens=0,
                cost=0,
                duration=time.time() - start_time,
                success=False,
            )
            raise

    async def stream(self, initial_state: AgentState, thread_id: str = "default"):
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": settings.LANGGRAPH_MAX_ITERATIONS * 5 + 10,
        }
        async for event in self.compiled.astream(initial_state, config=config):
            yield event


def get_agent_graph() -> AgentGraph:
    return AgentGraph()


_precompiled_graph: AgentGraph | None = None


def warmup_agent_graph() -> AgentGraph:
    global _precompiled_graph
    if _precompiled_graph is None:
        logger.info("[Graph] Warming up...")
        t0 = time.monotonic()
        _precompiled_graph = get_agent_graph()
        _ = _precompiled_graph.compiled
        logger.info(f"[Graph] Warmed up in {int((time.monotonic() - t0) * 1000)}ms")
    return _precompiled_graph
