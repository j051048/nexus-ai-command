"""
Agent State Definition - The single source of truth flowing through the graph.

Uses TypedDict so LangGraph can checkpoint, serialize, and replay states.
Every node reads from and writes to this state dict.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
import operator


# ─── Enums ───────────────────────────────────────────────────────────────────

class AgentPhase(str, Enum):
    """Tracks which node the agent is currently in."""
    ROUTING = "routing"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    RESPONDING = "responding"
    DONE = "done"
    ERROR = "error"


class QueryComplexity(str, Enum):
    """Result of the intent router — drives model selection."""
    SIMPLE = "simple"          # Greeting, FAQ → gpt-4o-mini
    MODERATE = "moderate"      # Single-tool lookup → gpt-4o-mini
    COMPLEX = "complex"        # Multi-tool, analysis → gpt-4o
    CRITICAL = "critical"      # Approvals, financial ops → gpt-4o + confirmation


# ─── Thinking Step (for frontend visualization) ─────────────────────────────

@dataclass
class ThinkingStep:
    """Represents a single step in the agent's thinking chain for UI display."""
    phase: str
    content: str
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# ─── Tool Call Record ────────────────────────────────────────────────────────

@dataclass
class ToolCallRecord:
    """Structured record of a single tool invocation and its result."""
    tool_name: str
    tool_args: Dict[str, Any]
    tool_call_id: str
    result: Optional[str] = None
    status: str = "pending"  # pending | success | error | blocked
    duration_ms: Optional[int] = None


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
    org_id: Optional[str] = None
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
    gather_timeout: int = 60

    def get_model_for_complexity(self, complexity: QueryComplexity) -> str:
        """Dynamic model routing based on query complexity."""
        if complexity in (QueryComplexity.SIMPLE, QueryComplexity.MODERATE):
            return self.mini_model
        return self.model


# ─── Core Agent State (TypedDict for LangGraph) ─────────────────────────────

class AgentState(TypedDict, total=False):
    """
    The state that flows through every node of the LangGraph.

    Uses Annotated[list, operator.add] for messages so that each node
    *appends* rather than replaces — this is the LangGraph accumulator pattern.
    """

    # ── Core message history (LangChain BaseMessage list) ──
    messages: Annotated[List[BaseMessage], operator.add]

    # ── Phase tracking ──
    current_phase: AgentPhase
    iteration: int                          # Current loop iteration (0-based)

    # ── Router output ──
    complexity: QueryComplexity
    selected_model: str                     # Model chosen for this turn
    intent_summary: str                     # One-line description of user intent

    # ── Plan ──
    plan: str                               # Natural language plan from planning node
    requires_tools: bool                    # Whether the plan involves tool calls

    # ── Tool execution ──
    pending_tool_calls: List[ToolCallRecord]
    completed_tool_calls: List[ToolCallRecord]

    # ── Reflection ──
    reflection: str                         # Self-critique from reflection node
    is_hallucination: bool                  # Hallucination detector flag
    needs_replanning: bool                  # Whether to loop back to planning
    confidence_score: float                 # 0.0-1.0 confidence in the answer

    # ── RAG context (auto-injected by memory / rag_inject node) ──
    rag_context: str                        # Retrieved knowledge base context
    rag_sources: List[str]                  # Source citations for the RAG context

    # ── Final output ──
    final_response: str                     # The text response to send to user
    thinking_steps: List[ThinkingStep]      # For frontend thinking-chain UI

    # ── Configuration (immutable, set once at start) ──
    config: AgentConfig

    # ── Error handling ──
    error: Optional[str]
    error_recovery_attempted: bool          # Whether error recovery has been tried

    # ── Token tracking ──
    total_input_tokens: int
    total_output_tokens: int