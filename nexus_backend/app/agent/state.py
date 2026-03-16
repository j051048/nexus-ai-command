"""
Agent State Definition - The single source of truth flowing through the graph.

Uses TypedDict so LangGraph can checkpoint, serialize, and replay states.
Every node reads from and writes to this state dict.
"""

import logging
import operator
import time
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field, field_validator

from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)

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


# ─── Agent Configuration (immutable per-request, Pydantic-validated) ─────────


class AgentConfig(BaseModel):
    """Per-request configuration injected at graph invocation time.

    Uses Pydantic BaseModel for runtime validation of field constraints.
    """

    model_config = {"frozen": False}  # Allow mutation for backward compat

    user_id: str
    session_id: str = "default"
    agent_name: str = "default"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    mini_model: str = "gpt-4o-mini"
    system_confirmed: bool = False
    confirmed_tool: dict | None = None  # HITL: {tool_name, args} from blocked call
    org_id: str | None = None
    user_role: str = "employee"
    max_iterations: int = Field(default=5, gt=0, description="Must be > 0")
    max_tokens_per_day: int = Field(default=1_000_000, gt=0, description="Must be > 0")
    temperature: float = Field(default=0.5, ge=0.0, le=2.0, description="0.0-2.0")
    # RAG auto-injection settings
    enable_rag_inject: bool = True
    rag_inject_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    rag_inject_limit: int = Field(default=3, gt=0)
    # Reflect node settings
    reflect_use_llm: bool = True
    # Tool execution settings
    tool_timeout: int = Field(default=15, gt=0, description="Seconds, must be > 0")
    gather_timeout: int = Field(default=120, gt=0, description="Seconds, must be > 0")
    tool_max_retries: int = Field(default=2, ge=0, le=5, description="Max retry attempts for retryable tool errors")

    @field_validator("user_role")
    @classmethod
    def validate_user_role(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            return "employee"
        return v

    def get_model_for_complexity(self, complexity: QueryComplexity) -> str:
        """Dynamic model routing based on query complexity (4-tier).

        For power/flagship tiers, guards against weak models (mini/flash/turbo
        etc.) that the user may have saved as their default.  Falls back to
        the env-level AI_DEFAULT_MODEL so complex tasks get a capable model
        while still using the user's API key and proxy.
        """
        tier = complexity.model_tier
        if tier in ("economy", "balanced"):
            return self.mini_model

        # power / flagship — ensure a capable model
        model = self.model
        _weak = {"mini", "flash", "turbo", "haiku", "lite"}
        if any(w in model.lower() for w in _weak):
            from app.core.config import settings as _settings
            fallback = getattr(_settings, "AI_STRONG_MODEL", "") or getattr(_settings, "AI_DEFAULT_MODEL", "gpt-4o")
            logger.info(
                "Weak model '%s' for %s tier, upgrading to '%s'",
                model, tier, fallback,
            )
            return fallback
        return model

    def get_tier_config(self, complexity: QueryComplexity) -> dict:
        """Return full tier-aware config (model + temperature + timeout + tools).

        Used by nodes that need more than just the model name — e.g. when
        creating LLM instances with tier-specific temperature/timeout.
        """
        _tier_overrides = {
            "economy":  {"temperature": 0.3, "timeout": 30, "supports_tools": False},
            "balanced": {"temperature": 0.5, "timeout": 45, "supports_tools": True},
            "power":    {"temperature": 0.7, "timeout": 60, "supports_tools": True},
            "flagship": {"temperature": 0.5, "timeout": 90, "supports_tools": True},
        }
        tier = complexity.model_tier
        overrides = _tier_overrides.get(tier, {})
        return {
            "model": self.get_model_for_complexity(complexity),
            "temperature": overrides.get("temperature", self.temperature),
            "timeout": overrides.get("timeout", self.tool_timeout),
            "supports_tools": overrides.get("supports_tools", True),
            "tier": tier,
        }


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
    intent_domains: list[str]  # Business domains identified by Router LLM fallback

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

    # ── Confirmation gate ──
    confirmation_pending: bool  # True when tools are blocked waiting for user confirmation

    # ── Reflection budget (Item 33) ──
    reflection_count: int  # Number of reflect-node invocations this turn (budget: max 2)

    # ── Loop detection (P2) ──
    _tool_call_history: Annotated[list[str], operator.add]  # Fingerprint hashes per execute round
