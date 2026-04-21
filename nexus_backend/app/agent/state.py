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

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field, ValidationError, field_validator

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
        """Convert step to dictionary, excluding None values."""
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
    error_type: str | None = None  # retryable | param_error | fatal
    tool_version: str | None = None  # #17: tool version for audit
    confirmation_type: str = ""  # P0-6: "irreversible" | "high_value" | "bulk" | ""

    def get(self, key: str, default=None):
        """Dict-compatible access for code that treats records as dicts."""
        return getattr(self, key, default)


# ─── Pydantic Models for Complex State Fields ────────────────────────────────
# These provide type-safe access to dict-based structures in AgentState,
# especially when deserializing from JSON checkpoints.


class WBSSubTask(BaseModel):
    """WBS sub-task structure produced by wbs_decompose_node."""

    title: str
    agent_code: str = ""
    description: str = ""
    dependencies: list[int] = []
    priority: int = 3
    sub_task_id: str = ""
    status: str = "pending"


class WBSStructure(BaseModel):
    """WBS decomposition structure (top-level)."""

    title: str
    summary: str = ""
    sub_tasks: list[WBSSubTask] = []


class DelegationResult(BaseModel):
    """Result from a sub-agent delegation in orchestrate_node."""

    sub_task_id: str
    agent_code: str
    title: str
    status: str  # completed | degraded | failed
    result: str = ""


class TaskStep(BaseModel):
    """Decomposed step from task decomposition in plan_node."""

    title: str
    description: str = ""
    acceptance_criteria: str = ""


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
    token: str = ""  # User JWT for RLS-scoped DB queries in tools
    user_role: str = "employee"
    max_iterations: int = Field(default=5, gt=0, description="Must be > 0")
    max_tokens_per_day: int = Field(default=1_000_000, gt=0, description="Must be > 0")
    temperature: float = Field(default=0.5, ge=0.0, le=2.0, description="0.0-2.0")
    # Pre-resolved model configs per tier (populated once at stream.py entry)
    resolved_configs: dict = Field(
        default_factory=dict
    )  # tier -> {api_key, base_url, model, ...}
    # RAG auto-injection settings
    enable_rag_inject: bool = True
    rag_inject_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    rag_inject_limit: int = Field(default=3, gt=0)
    # Reflect node settings
    reflect_use_llm: bool = True
    # Tool execution settings
    tool_timeout: int = Field(default=15, gt=0, description="Seconds, must be > 0")
    gather_timeout: int = Field(default=120, gt=0, description="Seconds, must be > 0")
    tool_max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Max retry attempts for retryable tool errors",
    )
    # P0-1: Confidence gating
    confidence_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Min confidence for tool params"
    )
    # P0-2: Dry-run mode
    dry_run: bool = False

    @field_validator("user_role")
    @classmethod
    def validate_user_role(cls, v: str) -> str:
        """Validate and normalize user role, defaulting to 'employee' if invalid."""
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
        from app.services.llm_helpers import is_weak_model

        if is_weak_model(model):
            from app.core.config import settings as _settings

            fallback = getattr(_settings, "AI_STRONG_MODEL", "") or getattr(
                _settings, "AI_DEFAULT_MODEL", "gemini-3-flash-preview"
            )
            # Guard: if fallback is the same model, skip the misleading log
            if fallback != model:
                logger.info(
                    "Weak model '%s' for %s tier, upgrading to '%s'",
                    model,
                    tier,
                    fallback,
                )
            return fallback
        return model

    def get_tier_config(self, complexity: QueryComplexity) -> dict:
        """Return full tier-aware config (model + temperature + timeout + tools).

        Uses pre-resolved Gateway configs when available, otherwise falls back
        to local tier overrides.  Includes cost_multiplier for cost tracking.
        """
        tier = complexity.model_tier
        _cost_multipliers = {
            "economy": 0.1,
            "balanced": 0.3,
            "power": 1.0,
            "flagship": 1.5,
        }
        cost_multiplier = _cost_multipliers.get(tier, 1.0)

        # Prefer pre-resolved Gateway config
        if self.resolved_configs and tier in self.resolved_configs:
            rc = self.resolved_configs[tier]
            return {
                "model": rc.get("model", self.get_model_for_complexity(complexity)),
                "temperature": rc.get("temperature", self.temperature),
                "timeout": rc.get("timeout", 300),
                "supports_tools": rc.get("supports_tools", True),
                "tier": tier,
                "cost_multiplier": cost_multiplier,
            }

        _tier_overrides = {
            # economy: supports_tools=False is intentional — simple greetings and
            # cheap-routed queries don't need tool calls, saving unnecessary overhead.
            "economy": {"temperature": 0.3, "timeout": 120, "supports_tools": False},
            "balanced": {"temperature": 0.5, "timeout": 180, "supports_tools": True},
            "power": {"temperature": 0.7, "timeout": 300, "supports_tools": True},
            "flagship": {"temperature": 0.5, "timeout": 600, "supports_tools": True},
        }
        tier = complexity.model_tier
        overrides = _tier_overrides.get(tier, {})
        return {
            "model": self.get_model_for_complexity(complexity),
            "temperature": overrides.get("temperature", self.temperature),
            "timeout": overrides.get(
                "timeout", self.tool_timeout * 10
            ),  # fallback to higher limit
            "supports_tools": overrides.get("supports_tools", True),
            "tier": tier,
            "cost_multiplier": cost_multiplier,
        }


# ─── Core Agent State (TypedDict for LangGraph) ─────────────────────────────


class AgentState(TypedDict, total=False):
    """
    The state that flows through every node of the LangGraph.

    Uses Annotated[list, operator.add] for messages so that each node
    *appends* rather than replaces — this is the LangGraph accumulator pattern.

    Field groups (#19):
      Core (2)     → messages, current_phase, iteration
      Routing (4)  → complexity, selected_model, intent_summary, intent_domains
      Planning (2) → plan, requires_tools
      Execution (2)→ pending_tool_calls, completed_tool_calls
      Reflection (7)→ reflection, is_hallucination, needs_replanning, confidence_score,
                      reflection_guidance, critic_feedback, critic_passed, reflection_count
      RAG (2)      → rag_context, rag_sources
      Output (2)   → final_response, thinking_steps
      VMD (7)      → agent_code, scene_code, main_task_id, sub_task_id,
                      parent_agent_code, delegation_results, wbs_structure
      Config (1)   → config
      Error (3)    → error, error_recovery_attempted, error_recovery_level
      Token (2)    → total_input_tokens, total_output_tokens
      Control (6)  → confirmation_pending, _tool_call_history, _loop_escape_attempted,
                      context_compacted_summary, _task_decomposition_done,
                      _task_steps, _active_step_index
      ToT (3)      → candidate_plans, backtrack_depth, best_plan_score
      SLO (1)      → wall_clock_start
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
    thinking_steps: Annotated[
        list[ThinkingStep], operator.add
    ]  # Accumulate across nodes

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
    reflection_guidance: (
        str  # Structured correction instructions from reflect/critic → plan
    )
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
    confirmation_pending: (
        bool  # True when tools are blocked waiting for user confirmation
    )

    # ── Reflection budget (Item 33) ──
    reflection_count: (
        int  # Number of reflect-node invocations this turn (budget: max 2)
    )

    # ── Loop detection (P2) ──
    _tool_call_history: Annotated[
        list[str], operator.add
    ]  # Fingerprint hashes per execute round
    _loop_escape_attempted: (
        bool  # True after first loop → strategy reset before circuit break
    )

    # ── Context compaction (P0) ──
    context_compacted_summary: str  # Summary produced by compact_context pseudo-tool

    # ── Task decomposition (P1) ──
    _task_decomposition_done: bool  # Whether complex query has been decomposed
    _task_steps: list[dict]  # Decomposed steps: [{title, description, tools}]
    _active_step_index: int  # Current step being executed (0-based)

    # ── SLO tracking ──
    wall_clock_start: (
        float  # time.time() at plan_node entry for dynamic SLO degradation
    )

    # ── Circuit breaker (set by _after_execute on loop/iteration limit) ──
    circuit_break_reason: str | None

    # ── Slot filling / DST (Dialog State Tracking) ──
    slot_context: (
        dict | None
    )  # {tool_name, tool_call_id, filled_slots, missing_slots, tool_schema}
    slot_round: int  # 当前澄清轮次 (0=首次, max=3)

    # ── Tree-of-Thought (ToT) branch search ──
    candidate_plans: list[
        dict
    ]  # Top-N scored alternatives from self-consistency: [{sig, score, msg_snapshot}]
    backtrack_depth: int  # Times we've backtracked to an alternative plan (max=1)
    best_plan_score: float  # Votes / n for the winning plan (0.0-1.0)

    # ── Schema version (for checkpoint restore compatibility) ──
    _schema_version: int  # Current schema version; used to migrate stale checkpoints


# ─── Schema Version & Migration ──────────────────────────────────────────────

CURRENT_SCHEMA_VERSION = 2  # Bump when adding/removing/renaming AgentState fields

# Fields added in each version (for forward-compatible migration)
_SCHEMA_DEFAULTS: dict[int, dict[str, Any]] = {
    2: {
        "_schema_version": 2,
        "candidate_plans": [],
        "backtrack_depth": 0,
        "best_plan_score": 0.0,
        "slot_context": None,
        "slot_round": 0,
        "circuit_break_reason": None,
    },
}


def migrate_state(state: dict) -> dict:
    """Migrate a checkpoint state dict to the current schema version.

    Adds missing fields with safe defaults so that stale checkpoints
    don't crash on KeyError.  Called once on checkpoint restore.
    """
    version = state.get("_schema_version", 1)
    if version >= CURRENT_SCHEMA_VERSION:
        return state

    for v in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
        defaults = _SCHEMA_DEFAULTS.get(v, {})
        for key, default in defaults.items():
            if key not in state:
                state[key] = default

    state["_schema_version"] = CURRENT_SCHEMA_VERSION
    logger.info(
        "[State] Migrated checkpoint from schema v%d → v%d",
        version,
        CURRENT_SCHEMA_VERSION,
    )
    return state


# ─── State Access Helpers ─────────────────────────────────────────────────────
# Type-safe accessors that handle dict/dataclass duality from checkpoint
# deserialization.  Use these instead of raw state.get("field", []).


def get_completed_tools(state: "AgentState") -> list[ToolCallRecord]:
    """Type-safe access to completed_tool_calls.

    Handles both ToolCallRecord instances and raw dicts (from JSON checkpoint
    deserialization) transparently.
    """
    raw = state.get("completed_tool_calls", [])
    result: list[ToolCallRecord] = []
    _fields = set(ToolCallRecord.__dataclass_fields__)
    for item in raw:
        if isinstance(item, ToolCallRecord):
            result.append(item)
        elif isinstance(item, dict):
            filtered = {k: v for k, v in item.items() if k in _fields}
            try:
                result.append(ToolCallRecord(**filtered))
            except TypeError:
                logger.warning(
                    "[State] Skipping malformed tool call record: %s", filtered
                )
        # silently skip other types
    return result


def get_wbs(state: "AgentState") -> WBSStructure | None:
    """Type-safe access to wbs_structure."""
    raw = state.get("wbs_structure")
    if not raw:
        return None
    if isinstance(raw, WBSStructure):
        return raw
    if isinstance(raw, dict):
        try:
            return WBSStructure(**raw)
        except (ValidationError, TypeError):
            logger.warning("[State] Malformed wbs_structure, returning None")
            return None
    return None


def get_task_steps(state: "AgentState") -> list[TaskStep]:
    """Type-safe access to _task_steps."""
    raw = state.get("_task_steps", [])
    result: list[TaskStep] = []
    for item in raw:
        if isinstance(item, TaskStep):
            result.append(item)
        elif isinstance(item, dict):
            try:
                result.append(TaskStep(**item))
            except (ValidationError, TypeError):
                logger.warning("[State] Skipping malformed task step: %s", item)
        # silently skip other types
    return result


def get_delegation_results(state: "AgentState") -> list[DelegationResult]:
    """Type-safe access to delegation_results."""
    raw = state.get("delegation_results", [])
    result: list[DelegationResult] = []
    for item in raw:
        if isinstance(item, DelegationResult):
            result.append(item)
        elif isinstance(item, dict):
            try:
                result.append(DelegationResult(**item))
            except (ValidationError, TypeError):
                logger.warning("[State] Skipping malformed delegation result: %s", item)
    return result


def get_config(state: "AgentState") -> "AgentConfig":
    """Safe config access — raises ValueError instead of KeyError."""
    config = state.get("config")
    if config is None:
        raise ValueError("AgentState missing required 'config' field")
    return config
