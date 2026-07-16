"""Unified, tenant-aware execution policy for all AI workloads.

The policy deliberately controls *how much work* an Agent may perform instead
of exposing model selection to regular users. All chat-capable workers use the
production primary model; execution depth is selected by deterministic risk
and task-shape rules.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings

logger = logging.getLogger(__name__)

POLICY_CONFIG_TYPE = "ai_execution"
POLICY_CONFIG_KEY = "policy"
POLICY_VERSION = "2026-07-16.1"
PRIMARY_CHAT_MODEL = "deepseek-v4-flash"


class AIExecutionMode(StrEnum):
    ECONOMY = "economy"
    BALANCED = "balanced"
    STRICT = "strict"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExecutionStopReason(StrEnum):
    COMPLETED = "completed"
    CALL_BUDGET = "call_budget"
    COST_BUDGET = "cost_budget"
    TOKEN_BUDGET = "token_budget"
    DEADLINE = "deadline"
    CANCELLED = "cancelled"
    BEST_AVAILABLE = "best_available"


class AIExecutionPolicy(BaseModel):
    """The only supported runtime policy contract."""

    model_config = ConfigDict(extra="ignore")

    version: str = POLICY_VERSION
    mode: AIExecutionMode = AIExecutionMode.BALANCED
    primary_model: str = PRIMARY_CHAT_MODEL
    embedding_model: str = "text-embedding-3-small"
    rerank_model: str = "bge-reranker-v2-m3"
    premium_model: str | None = None
    premium_manual_only: bool = True
    allow_llm_router: bool = False
    scheduled_primary_only: bool = True
    max_calls: int = Field(default=2, ge=1, le=3)
    max_verifications: int = Field(default=1, ge=0, le=1)
    max_iterations: int = Field(default=2, ge=1, le=3)
    max_input_tokens: int = Field(default=24_000, ge=1_000, le=128_000)
    max_output_tokens: int = Field(default=4_096, ge=256, le=16_384)
    max_task_cost_usd: float = Field(default=0.08, ge=0.001, le=5.0)
    max_latency_ms: int = Field(default=60_000, ge=5_000, le=180_000)
    context_tool_limit: int = Field(default=12, ge=1, le=32)
    require_confirmation_for_high_risk: bool = True
    retain_inference_receipts: bool = True
    high_risk_terms: list[str] = Field(default_factory=list, max_length=50)
    medium_risk_terms: list[str] = Field(default_factory=list, max_length=50)

    @classmethod
    def for_mode(cls, mode: AIExecutionMode | str) -> AIExecutionPolicy:
        resolved = AIExecutionMode(mode)
        presets: dict[AIExecutionMode, dict[str, Any]] = {
            AIExecutionMode.ECONOMY: {
                "max_calls": 1,
                "max_verifications": 0,
                "max_iterations": 1,
                "max_input_tokens": 12_000,
                "max_output_tokens": 2_048,
                "max_task_cost_usd": 0.03,
                "max_latency_ms": 35_000,
                "context_tool_limit": 8,
            },
            AIExecutionMode.BALANCED: {
                "max_calls": 2,
                "max_verifications": 1,
                "max_iterations": 2,
                "max_input_tokens": 24_000,
                "max_output_tokens": 4_096,
                "max_task_cost_usd": 0.08,
                "max_latency_ms": 60_000,
                "context_tool_limit": 12,
            },
            AIExecutionMode.STRICT: {
                "max_calls": 3,
                "max_verifications": 1,
                "max_iterations": 3,
                "max_input_tokens": 48_000,
                "max_output_tokens": 6_144,
                "max_task_cost_usd": 0.18,
                "max_latency_ms": 120_000,
                "context_tool_limit": 18,
            },
        }
        return cls(mode=resolved, **presets[resolved])


class TaskProfile(BaseModel):
    classification_source: Literal["deterministic"] = "deterministic"
    complexity: str
    risk_level: RiskLevel
    needs_tools: bool
    needs_verification: bool
    execution_depth: Literal["direct", "verify", "critic"]
    reason_codes: list[str]
    route_confidence: float = Field(ge=0.0, le=1.0)
    recommended_mode: AIExecutionMode


class WorkerDefinition(BaseModel):
    code: str
    label: str
    capability: str
    model: str = PRIMARY_CHAT_MODEL
    may_call_tools: bool = False
    readable_artifacts: list[str]
    writable_artifacts: list[str]
    max_calls: int = 1
    enabled: bool = True


class BudgetDecision(BaseModel):
    allowed: bool
    stop_reason: ExecutionStopReason | None = None
    remaining_calls: int
    remaining_cost_usd: float
    remaining_tokens: int
    remaining_latency_ms: int


class InferenceReceipt(BaseModel):
    receipt_version: str = "1.0"
    policy_version: str
    policy_mode: AIExecutionMode
    task_risk: RiskLevel
    execution_depth: str
    model: str
    steps: list[str]
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    actual_cost_usd: float
    latency_ms: int
    stop_reason: ExecutionStopReason
    answer_hash: str
    trace_hash: str


class SimulationCase(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    complexity: str = "moderate"
    scene_code: str = "chat"
    agent_code: str = "assistant"
    requires_tools: bool = False
    scheduled: bool = False


class SimulationResult(BaseModel):
    query: str
    profile: TaskProfile
    policy: AIExecutionPolicy
    planned_steps: list[str]
    estimated_calls: int
    estimated_latency_ms: int
    model: str


_HIGH_RISK_RE = re.compile(
    r"(删除|批量删除|付款|支付|转账|退款|批准|驳回|审批|签署|签约|合同|"
    r"群发|外发|发送邮件|权限|角色|密钥|停用|注销|delete|payment|transfer|"
    r"approve|reject|sign|permission|credential)",
    re.IGNORECASE,
)
_MEDIUM_RISK_RE = re.compile(
    r"(创建|更新|修改|导入|同步|发布|提交|生成报告|预测|分析|对比|"
    r"create|update|import|sync|publish|submit|forecast|analyse|analyze)",
    re.IGNORECASE,
)
_COMPLEX_RE = re.compile(
    r"(然后|并且|同时|分别|综合|多步骤|跨部门|完整方案|根因|评估|"
    r"and then|multi-step|root cause|comprehensive)",
    re.IGNORECASE,
)


def _normalize_policy(policy: AIExecutionPolicy) -> AIExecutionPolicy:
    """Enforce non-negotiable production cost controls."""
    preset = AIExecutionPolicy.for_mode(policy.mode)
    values = policy.model_dump()
    values.update(
        {
            "version": POLICY_VERSION,
            "primary_model": PRIMARY_CHAT_MODEL,
            "premium_manual_only": True,
            "allow_llm_router": False,
            "scheduled_primary_only": True,
            "max_calls": min(policy.max_calls, preset.max_calls),
            "max_verifications": min(
                policy.max_verifications, preset.max_verifications
            ),
            "max_iterations": min(policy.max_iterations, preset.max_iterations),
            "max_input_tokens": min(policy.max_input_tokens, preset.max_input_tokens),
            "max_output_tokens": min(
                policy.max_output_tokens, preset.max_output_tokens
            ),
            "max_task_cost_usd": min(
                policy.max_task_cost_usd, preset.max_task_cost_usd
            ),
            "max_latency_ms": min(policy.max_latency_ms, preset.max_latency_ms),
            "context_tool_limit": min(
                policy.context_tool_limit, preset.context_tool_limit
            ),
        }
    )
    return AIExecutionPolicy.model_validate(values)


def assess_task(
    query: str,
    *,
    complexity: Any = "moderate",
    scene_code: str = "chat",
    agent_code: str = "assistant",
    requires_tools: bool = False,
    scheduled: bool = False,
    policy: AIExecutionPolicy | None = None,
) -> TaskProfile:
    """Classify task shape without spending an LLM call."""
    del agent_code
    text = str(query or "").strip()
    complexity_value = str(getattr(complexity, "value", complexity)).lower()
    reasons: list[str] = []
    risk = RiskLevel.LOW

    high_override = bool(
        policy
        and any(
            term.strip() and term.strip() in text for term in policy.high_risk_terms
        )
    )
    medium_override = bool(
        policy
        and any(
            term.strip() and term.strip() in text for term in policy.medium_risk_terms
        )
    )

    if _HIGH_RISK_RE.search(text) or high_override:
        risk = RiskLevel.HIGH
        reasons.append("irreversible_or_sensitive_action")
    elif requires_tools or _MEDIUM_RISK_RE.search(text) or medium_override:
        risk = RiskLevel.MEDIUM
        reasons.append("business_side_effect_or_analysis")

    if complexity_value in {"complex", "critical"} or _COMPLEX_RE.search(text):
        reasons.append("multi_step_or_complex_reasoning")
        if risk == RiskLevel.LOW:
            risk = RiskLevel.MEDIUM
    if scheduled:
        reasons.append("scheduled_primary_only")
    if scene_code in {"approval", "finance", "contract", "security"}:
        risk = RiskLevel.HIGH
        reasons.append("sensitive_business_scene")
    if not reasons:
        reasons.append("direct_answer_sufficient")

    if risk == RiskLevel.HIGH:
        depth: Literal["direct", "verify", "critic"] = "critic"
        recommended = AIExecutionMode.STRICT
    elif risk == RiskLevel.MEDIUM or complexity_value == "complex":
        depth = "verify"
        recommended = AIExecutionMode.BALANCED
    else:
        depth = "direct"
        recommended = AIExecutionMode.ECONOMY

    return TaskProfile(
        complexity=complexity_value,
        risk_level=risk,
        needs_tools=requires_tools,
        needs_verification=depth != "direct",
        execution_depth=depth,
        reason_codes=reasons,
        route_confidence=0.96 if risk != RiskLevel.MEDIUM else 0.88,
        recommended_mode=recommended,
    )


def effective_policy_for_task(
    configured: AIExecutionPolicy, profile: TaskProfile
) -> AIExecutionPolicy:
    """Keep tenant preference while never weakening high-risk verification."""
    configured = _normalize_policy(configured)
    rank = {
        AIExecutionMode.ECONOMY: 0,
        AIExecutionMode.BALANCED: 1,
        AIExecutionMode.STRICT: 2,
    }
    resolved_mode = configured.mode
    if rank[profile.recommended_mode] > rank[configured.mode]:
        resolved_mode = profile.recommended_mode
    resolved = AIExecutionPolicy.for_mode(resolved_mode)
    resolved.premium_model = configured.premium_model
    resolved.retain_inference_receipts = configured.retain_inference_receipts
    resolved.high_risk_terms = configured.high_risk_terms
    resolved.medium_risk_terms = configured.medium_risk_terms
    return _normalize_policy(resolved)


def check_step_budget(
    policy: AIExecutionPolicy,
    *,
    calls_used: int,
    cost_used_usd: float,
    tokens_used: int,
    elapsed_ms: int,
    estimated_step_cost_usd: float = 0.0,
    estimated_step_tokens: int = 0,
) -> BudgetDecision:
    stop_reason: ExecutionStopReason | None = None
    if calls_used >= policy.max_calls:
        stop_reason = ExecutionStopReason.CALL_BUDGET
    elif cost_used_usd + estimated_step_cost_usd > policy.max_task_cost_usd:
        stop_reason = ExecutionStopReason.COST_BUDGET
    elif tokens_used + estimated_step_tokens > (
        policy.max_input_tokens + policy.max_output_tokens
    ):
        stop_reason = ExecutionStopReason.TOKEN_BUDGET
    elif elapsed_ms >= policy.max_latency_ms:
        stop_reason = ExecutionStopReason.DEADLINE

    return BudgetDecision(
        allowed=stop_reason is None,
        stop_reason=stop_reason,
        remaining_calls=max(0, policy.max_calls - calls_used),
        remaining_cost_usd=round(max(0.0, policy.max_task_cost_usd - cost_used_usd), 6),
        remaining_tokens=max(
            0,
            policy.max_input_tokens + policy.max_output_tokens - tokens_used,
        ),
        remaining_latency_ms=max(0, policy.max_latency_ms - elapsed_ms),
    )


def worker_registry(policy: AIExecutionPolicy | None = None) -> list[WorkerDefinition]:
    active = _normalize_policy(policy or AIExecutionPolicy.for_mode("balanced"))
    return [
        WorkerDefinition(
            code="direct",
            label="直接执行",
            capability="Produce the first grounded answer or tool plan",
            model=active.primary_model,
            may_call_tools=True,
            readable_artifacts=["request", "approved_context", "tool_catalog"],
            writable_artifacts=["candidate_answer", "tool_plan"],
        ),
        WorkerDefinition(
            code="verifier_editor",
            label="校验与修订",
            capability="Verify evidence and revise once",
            model=active.primary_model,
            readable_artifacts=["candidate_answer", "tool_evidence", "citations"],
            writable_artifacts=["verified_answer", "verification_report"],
            enabled=active.max_verifications > 0,
        ),
        WorkerDefinition(
            code="critic",
            label="风险校验",
            capability="Check high-risk actions and unsupported claims",
            model=active.primary_model,
            readable_artifacts=["candidate_answer", "tool_evidence", "risk_policy"],
            writable_artifacts=["critic_report"],
            enabled=active.mode == AIExecutionMode.STRICT,
        ),
        WorkerDefinition(
            code="finalizer",
            label="结果收敛",
            capability="Return the best available result within budget",
            model=active.primary_model,
            readable_artifacts=[
                "candidate_answer",
                "verified_answer",
                "critic_report",
            ],
            writable_artifacts=["final_answer"],
        ),
    ]


def build_inference_receipt(
    *,
    policy: AIExecutionPolicy,
    profile: TaskProfile,
    steps: list[str],
    answer: str,
    trace: Any,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: float,
    actual_cost_usd: float,
    latency_ms: int,
    stop_reason: ExecutionStopReason = ExecutionStopReason.COMPLETED,
) -> InferenceReceipt:
    trace_json = json.dumps(trace, ensure_ascii=False, sort_keys=True, default=str)
    return InferenceReceipt(
        policy_version=policy.version,
        policy_mode=policy.mode,
        task_risk=profile.risk_level,
        execution_depth=profile.execution_depth,
        model=policy.primary_model,
        steps=steps,
        input_tokens=max(0, input_tokens),
        output_tokens=max(0, output_tokens),
        estimated_cost_usd=round(max(0.0, estimated_cost_usd), 8),
        actual_cost_usd=round(max(0.0, actual_cost_usd), 8),
        latency_ms=max(0, latency_ms),
        stop_reason=stop_reason,
        answer_hash=hashlib.sha256(answer.encode("utf-8")).hexdigest(),
        trace_hash=hashlib.sha256(trace_json.encode("utf-8")).hexdigest(),
    )


class AIExecutionPolicyService:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, AIExecutionPolicy]] = {}
        self._cache_ttl_seconds = 60.0

    def default_policy(self) -> AIExecutionPolicy:
        configured = getattr(settings, "AI_EXECUTION_MODE", "balanced")
        try:
            return AIExecutionPolicy.for_mode(configured)
        except ValueError:
            return AIExecutionPolicy.for_mode(AIExecutionMode.BALANCED)

    async def get_policy(self, org_id: str | None, db=None) -> AIExecutionPolicy:
        cache_key = org_id or "__default__"
        cached = self._cache.get(cache_key)
        now = time.monotonic()
        if cached and now - cached[0] < self._cache_ttl_seconds:
            return cached[1]

        policy = self.default_policy()
        if org_id and db is None:
            # A gateway call may not own a request-scoped DB client. Never cache
            # a tenant default in that path, otherwise it could shadow the real
            # tenant policy loaded by the next authenticated graph request.
            return policy
        if org_id and db is not None:
            try:
                from app.services.system_config_service import system_config_service

                row = await system_config_service.get_config(
                    org_id,
                    POLICY_CONFIG_TYPE,
                    POLICY_CONFIG_KEY,
                    db=db,
                )
                if row and isinstance(row.get("config_value"), dict):
                    policy = AIExecutionPolicy.model_validate(row["config_value"])
            except Exception:
                logger.warning(
                    "AI execution policy unavailable; using safe defaults org=%s",
                    org_id,
                    exc_info=True,
                )

        policy = _normalize_policy(policy)
        self._cache[cache_key] = (now, policy)
        return policy

    async def save_policy(
        self, org_id: str, policy: AIExecutionPolicy, db
    ) -> AIExecutionPolicy:
        from app.services.system_config_service import system_config_service

        normalized = _normalize_policy(policy)
        await system_config_service.upsert_config(
            org_id,
            POLICY_CONFIG_TYPE,
            POLICY_CONFIG_KEY,
            normalized.model_dump(mode="json"),
            db=db,
        )
        self._cache.pop(org_id, None)
        return normalized

    async def simulate(
        self,
        cases: list[SimulationCase],
        configured: AIExecutionPolicy,
    ) -> list[SimulationResult]:
        results: list[SimulationResult] = []
        for case in cases:
            profile = assess_task(
                case.query,
                complexity=case.complexity,
                scene_code=case.scene_code,
                agent_code=case.agent_code,
                requires_tools=case.requires_tools,
                scheduled=case.scheduled,
                policy=configured,
            )
            policy = effective_policy_for_task(configured, profile)
            steps = ["direct"]
            if profile.execution_depth == "verify":
                steps.append("verifier_editor")
            elif profile.execution_depth == "critic":
                steps.extend(["critic", "finalizer"])
            results.append(
                SimulationResult(
                    query=case.query,
                    profile=profile,
                    policy=policy,
                    planned_steps=steps,
                    estimated_calls=min(len(steps), policy.max_calls),
                    estimated_latency_ms=min(
                        policy.max_latency_ms,
                        1_200 + max(0, len(steps) - 1) * 900,
                    ),
                    model=policy.primary_model,
                )
            )
        return results


ai_execution_policy_service = AIExecutionPolicyService()
