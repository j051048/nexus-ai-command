"""
LangGraph-based Agentic Architecture for Project Nexus.

This module replaces the tool-augmented chat loop with a true
state-machine agent that follows:
  Plan → Execute → Reflect → Respond (with self-correction)

Key improvements over the old ChatService.stream_response:
- Explicit state graph with conditional edges
- Self-reflection & hallucination detection nodes
- Long-term memory (vector + structured hybrid)
- Dynamic model routing (simple queries to economy tier, complex to power tier)

Modules:
- state: AgentState TypedDict and related data structures
- nodes: Individual graph node functions (plan, execute, reflect, respond)
- graph: LangGraph StateGraph construction and compilation
- router: Intent classifier and dynamic model selector
- memory: Hybrid memory (short-term window + long-term vector)
- stream: SSE streaming adapter for the compiled graph
"""

from app.agent.checkpointer import (
    get_checkpointer,
    reset_checkpointer,
    setup_checkpointer,
)
from app.agent.graph import (
    AgentGraph,
    build_agent_graph,
    get_agent_graph,
    warmup_agent_graph,
)
from app.agent.state import AgentConfig, AgentPhase, AgentState, QueryComplexity
from app.agent.stream import run_agent_stream

__all__ = [
    "build_agent_graph",
    "AgentGraph",
    "get_agent_graph",
    "warmup_agent_graph",
    "AgentState",
    "AgentConfig",
    "AgentPhase",
    "QueryComplexity",
    "run_agent_stream",
    "get_checkpointer",
    "setup_checkpointer",
    "reset_checkpointer",
]
