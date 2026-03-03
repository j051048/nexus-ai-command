"""
Agent State Definition - The single source of truth flowing through the graph.

Uses TypedDict so LangGraph can checkpoint, serialize, and replay states.
Every node reads from and writes to this state dict.
"""

from __future__ import annotations

import operator
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage

# ─── Enums ───────────────────────────────────────────────────────────────────


class AgentPhase(StrEnum):
    """Tracks which node the agent is currently in."""

    ROUTING = "routing"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    CRITIQUING = "critiquing"
    RESPONDING = "responding"
    DONE = "done"
    ERROR = "error"


class QueryComplexity(StrEnum):
    """Result of the intent router — drives model selection."""

    SIMPLE = "simple"  # Greeting, FAQ → gpt-4o-mini
    MODERATE = "moderate"  # Single-tool lookup → gpt-4o-mini
    COMPLEX = "complex"  # Multi-tool, analysis → gpt-4o
    CRITICAL = "critical"  # Approvals, financial ops → gpt-4o + confirmation

    @property
    def model_tier(self) -> str:
        """Map to Gateway schedule_rule complexity_tier value (4-tier routing)."""
        return {
            "simple": "economy",
            "moderate": "balanced",
            "complex": "power",
            "critical": "flagship",
        }[self.value]


# ─── Thinking Step (for frontend visualization) ─────────────────────────────


@dataclass
class ThinkingStep:
    """Represents a single step in the agent's thinking chain for UI display."""

    phase: str
    content: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None
    timestamp: float = field(default_factory=time.time)
    duration_ms: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ─── Tool Call Record ────────────────────────────────────────────────────────


@dataclass
class ToolCallRecord:
    """Structured record of a single tool invocation and its result."""

    tool_name: str
    tool_args: dict[str, Any]
    tool_call_id: str
    result: str | None = None
    status: str = "pending"  # pending | success | error | blocked
    duration_ms: int | None = None


# ─── Agent Configuration (immutable per-request) ────────────────────────────


@dataclass
class AgentConfig:
    """Per-request configuration injected at graph invocation time."""

    user_id: str
    session_id: str = "default"
    agent_name: str = "default"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    mini_model: str = "gpt-4o-mini"
    system_confirmed: bool = False
    org_id: str | None = None
    user_role: str = "employee"
    max_iterations: int = 5
    max_tokens_per_day: int = 1_000_000
    temperature: float = 0.5
    # RAG auto-injection settings
    enable_rag_inject: bool = True
    rag_inject_threshold: float = 0.5
    rag_inject_limit: int = 3
    # Reflect node settings
    reflect_use_llm: bool = True
    # Tool execution settings
    tool_timeout: int = 30
    gather_timeout: int = 120

    def get_model_for_complexity(self, complexity: QueryComplexity) -> str:
        """Dynamic model routing based on query complexity (4-tier)."""
        tier = complexity.model_tier
        if tier in ("economy", "balanced"):
            return self.mini_model
        return self.model  # power, flagship


# ─── Core Agent State (TypedDict for LangGraph) ─────────────────────────────


class AgentState(TypedDict, total=False):
    """
    The state that flows through every node of the LangGraph.

    Uses Annotated[list, operator.add] for messages so that each node
    *appends* rather than replaces — this is the LangGraph accumulator pattern.
    """

    # ── Core message history (LangChain BaseMessage list) ──
    messages: Annotated[list[BaseMessage], operator.add]

    # ── Phase tracking ──
    current_phase: AgentPhase
    iteration: int  # Current loop iteration (0-based)

    # ── Router output ──
    complexity: QueryComplexity
    selected_model: str  # Model chosen for this turn
    intent_summary: str  # One-line description of user intent

    # ── Plan ──
    plan: str  # Natural language plan from planning node
    requires_tools: bool  # Whether the plan involves tool calls

    # ── Tool execution ──
    pending_tool_calls: list[ToolCallRecord]
    completed_tool_calls: list[ToolCallRecord]

    # ── Reflection ──
    reflection: str  # Self-critique from reflection node
    is_hallucination: bool  # Hallucination detector flag
    needs_replanning: bool  # Whether to loop back to planning
    confidence_score: float  # 0.0-1.0 confidence in the answer

    # ── RAG context (auto-injected by memory / rag_inject node) ──
    rag_context: str  # Retrieved knowledge base context
    rag_sources: list[str]  # Source citations for the RAG context

    # ── Final output ──
    final_response: str  # The text response to send to user
    thinking_steps: Annotated[list[ThinkingStep], operator.add]  # Accumulate across nodes

    # ── Configuration (immutable, set once at start) ──
    config: AgentConfig

    # ── Error handling ──
    error: str | None
    error_recovery_attempted: bool  # Whether error recovery has been tried
    error_recovery_level: int  # Multi-level error recovery (0=none, 1=retry, 2=degrade)

    # ── Token tracking ──
    total_input_tokens: int
    total_output_tokens: int

    # ── Observability ──
    # NOTE: trace_logger is passed via RunnableConfig["configurable"]["trace_logger"]
    # instead of state, because it's not serializable (contains network connections).

    # ── Reflection & Critic (P0-3 / P1-5) ──
    reflection_guidance: str  # Structured correction instructions from reflect/critic → plan
    critic_feedback: str  # Critic evaluation summary
    critic_passed: bool  # Whether critic approved the response

    # ── VMD Multi-Agent Orchestration ──
    agent_code: str  # Current agent role code (e.g., "content_agent")
    scene_code: str  # Current business scene code
    main_task_id: str | None  # Main task ID for multi-agent orchestration
    sub_task_id: str | None  # Sub-task ID
    parent_agent_code: str | None  # Parent agent that delegated to this one
    delegation_results: list  # Results from sub-agents
    wbs_structure: dict | None  # WBS task decomposition structure

    # ── Loop detection (P2) ──
    _tool_call_history: Annotated[list[str], operator.add]  # Fingerprint hashes per execute round
