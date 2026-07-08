"""Chat response acceleration controls.

The service keeps the product promise: faster perceived response without
removing Agent, RAG, tool, or safety quality gates.  It separates fast-path
answers from standard/deep agent work, caps context loading latency, caches
safe read-only tool results, and emits latency traces that can be surfaced in
Agent Ops.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.core.config import settings
from app.core.redis_keys import rk
from app.services.agent_operational_hardening import (
    LOW_COST_DEFAULT_MODEL,
    enforce_model_policy,
)
from app.services.cache_service import cache_service

ChatPath = Literal["fast_path", "standard_path", "deep_agent_path"]
ContextPriority = Literal["critical", "deferred"]
ToolExecutionTier = Literal["read_parallel", "write_serial_hitl", "background_slow"]
ReflectDecision = Literal["skip", "reflect", "reflect_and_critic"]

ACCELERATION_AREAS = (
    "three_layer_chat_path",
    "streaming_first_response",
    "layered_context_injection",
    "parallel_context_load_budget",
    "read_write_tool_execution_tiers",
    "semantic_tool_result_cache",
    "low_cost_model_quality_fallback",
    "prompt_template_and_tool_schema_slimming",
    "conditional_reflect_critic_policy",
    "latency_harness",
)

FAST_PATH_PATTERNS = (
    re.compile(
        r"^\s*(hi|hello|hey|你好|您好|在吗|早上好|下午好|晚上好)[!！。.\s]*$", re.I
    ),
    re.compile(r"^\s*(help|帮助|怎么用|你能做什么|能干什么)[?？!！。.\s]*$", re.I),
)

DEEP_AGENT_HINTS = (
    "审批",
    "批准",
    "驳回",
    "报销",
    "合同",
    "付款",
    "删除",
    "批量",
    "生成",
    "招标",
    "投标",
    "分析",
    "周报",
    "写入",
    "创建",
    "更新",
    "followup",
    "approve",
    "reject",
    "contract",
    "tender",
)

READ_ONLY_TOOL_PREFIXES = (
    "get_",
    "list_",
    "query_",
    "search_",
    "fetch_",
    "read_",
)

WRITE_TOOL_PREFIXES = (
    "create_",
    "update_",
    "delete_",
    "approve_",
    "reject_",
    "submit_",
    "send_",
    "publish_",
    "sync_",
)

SLOW_TOOL_HINTS = ("export", "report", "pdf", "crawl", "batch", "embedding")
REFLECTION_BUDGET_BY_COMPLEXITY = {
    "simple": 0,
    "moderate": 1,
    "complex": 2,
    "critical": 3,
}


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _sse_data(payload: Any) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_content(text: str) -> str:
    return _sse_data({"choices": [{"delta": {"content": text}}]})


def _complexity_value(complexity: Any) -> str:
    value = getattr(complexity, "value", complexity)
    return str(value or "moderate").lower()


def _get_reflection_budget(
    complexity: Any,
    completed_tools: list[Any] | None = None,
) -> int:
    budget = REFLECTION_BUDGET_BY_COMPLEXITY.get(_complexity_value(complexity), 2)
    if completed_tools and any(
        getattr(tool, "is_irreversible", False) for tool in completed_tools
    ):
        budget = min(budget + 1, 4)
    return budget


@dataclass(frozen=True)
class FastPathDecision:
    path: ChatPath
    can_answer: bool
    response_text: str = ""
    reason: str = ""
    confidence: float = 0.0
    bypasses_llm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContextLoadBudget:
    timeout_ms: int = 600
    critical_context: tuple[str, ...] = (
        "user_profile",
        "role",
        "org",
        "recent_messages",
        "route_context",
    )
    deferred_context: tuple[str, ...] = (
        "graph_rag",
        "long_memory",
        "knowledge_evidence",
        "tool_health",
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolResultCachePolicy:
    cacheable: bool
    cache_key: str
    ttl_seconds: int
    reason: str
    tier: ToolExecutionTier

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConditionalReflectPolicy:
    decision: ReflectDecision
    reason: str
    max_reflections: int
    requires_critic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChatLatencyTrace:
    trace_id: str
    route: ChatPath = "deep_agent_path"
    started_at: float = field(default_factory=time.perf_counter)
    marks: dict[str, float] = field(default_factory=dict)
    model: str = LOW_COST_DEFAULT_MODEL
    quality_score: float | None = None
    tool_success_rate: float | None = None

    def mark(self, stage: str) -> None:
        self.marks[stage] = round((time.perf_counter() - self.started_at) * 1000, 2)

    def to_dict(self) -> dict[str, Any]:
        total_ms = round((time.perf_counter() - self.started_at) * 1000, 2)
        return {
            "trace_id": self.trace_id,
            "route": self.route,
            "model": self.model,
            "marks_ms": self.marks,
            "total_ms": total_ms,
            "quality_score": self.quality_score,
            "tool_success_rate": self.tool_success_rate,
        }


class ChatResponseAccelerationService:
    """Runtime and contract helpers for faster chat response paths."""

    def classify_chat_path(
        self,
        *,
        message: str,
        agent: str | None = None,
        image_urls: list[str] | None = None,
        confirmed_tool: dict[str, Any] | None = None,
    ) -> FastPathDecision:
        text = (message or "").strip()
        lowered = text.lower()
        if not text:
            return FastPathDecision(
                path="fast_path",
                can_answer=True,
                response_text="我在，可以直接告诉我你想处理的业务。",
                reason="empty_or_ping",
                confidence=0.98,
                bypasses_llm=True,
            )
        if image_urls or confirmed_tool:
            return FastPathDecision(
                path="deep_agent_path",
                can_answer=False,
                reason="multimodal_or_confirmed_tool",
                confidence=0.95,
            )
        if len(text) <= 24 and any(
            pattern.search(text) for pattern in FAST_PATH_PATTERNS
        ):
            if re.search(r"help|帮助|怎么用|你能做什么|能干什么", lowered, re.I):
                response = (
                    "我可以帮你处理 CRM 跟进、审批、合同、招投标、报表和知识查询。"
                    "你也可以直接说：查 30 天未跟进客户，或生成本周销售摘要。"
                )
            else:
                response = "我在。你可以直接告诉我客户、审批、合同或报表相关的任务。"
            return FastPathDecision(
                path="fast_path",
                can_answer=True,
                response_text=response,
                reason="safe_greeting_or_help",
                confidence=0.98,
                bypasses_llm=True,
            )
        if any(hint in lowered or hint in text for hint in DEEP_AGENT_HINTS):
            return FastPathDecision(
                path="deep_agent_path",
                can_answer=False,
                reason="business_or_tool_task",
                confidence=0.9,
            )
        if len(text) < 80 and not agent:
            return FastPathDecision(
                path="standard_path",
                can_answer=False,
                reason="short_general_query",
                confidence=0.75,
            )
        return FastPathDecision(
            path="deep_agent_path",
            can_answer=False,
            reason="default_quality_preserving_path",
            confidence=0.7,
        )

    async def stream_fast_path(
        self,
        decision: FastPathDecision,
        *,
        trace: ChatLatencyTrace,
    ):
        trace.route = "fast_path"
        trace.mark("fast_path_selected")
        yield ": keepalive\n\n"
        yield self.progress_sse(
            "fast_path_selected",
            detail=decision.reason,
            trace=trace.to_dict(),
        )
        yield _sse_content(decision.response_text)
        trace.mark("fast_path_done")
        yield self.progress_sse(
            "done",
            detail="llm_bypassed",
            trace=trace.to_dict(),
        )
        yield "data: [DONE]\n\n"

    def progress_sse(
        self,
        stage: str,
        *,
        detail: str = "",
        trace: dict[str, Any] | None = None,
    ) -> str:
        return _sse_data(
            {
                "chat_acceleration": {
                    "stage": stage,
                    "detail": detail,
                    "trace": trace or {},
                }
            }
        )

    async def run_budgeted_context_loaders(
        self,
        loaders: dict[str, Callable[[], Awaitable[Any]]],
        *,
        budget: ContextLoadBudget | None = None,
    ) -> dict[str, Any]:
        context_budget = budget or ContextLoadBudget()
        tasks = {
            name: asyncio.create_task(loader()) for name, loader in loaders.items()
        }
        done, pending = await asyncio.wait(
            tasks.values(),
            timeout=context_budget.timeout_ms / 1000,
        )
        results: dict[str, Any] = {"loaded": {}, "deferred": [], "errors": {}}
        task_to_name = {task: name for name, task in tasks.items()}
        for task in done:
            name = task_to_name[task]
            try:
                results["loaded"][name] = task.result()
            except Exception as exc:  # pragma: no cover - defensive boundary
                results["errors"][name] = str(exc)
        for task in pending:
            name = task_to_name[task]
            task.cancel()
            results["deferred"].append(name)
        return results

    def classify_tool_tier(
        self, tool_name: str, tool: Any | None = None
    ) -> ToolExecutionTier:
        name = (tool_name or "").lower()
        is_irreversible = bool(getattr(tool, "is_irreversible", False))
        if is_irreversible or name.startswith(WRITE_TOOL_PREFIXES):
            return "write_serial_hitl"
        if any(hint in name for hint in SLOW_TOOL_HINTS):
            return "background_slow"
        return "read_parallel"

    def build_tool_result_cache_policy(
        self,
        *,
        tool_name: str,
        args: dict[str, Any],
        user_id: str,
        org_id: str | None,
        user_role: str | None = None,
        tool: Any | None = None,
        ttl_seconds: int = 120,
    ) -> ToolResultCachePolicy:
        tier = self.classify_tool_tier(tool_name, tool)
        name = (tool_name or "").lower()
        safe_prefix = name.startswith(READ_ONLY_TOOL_PREFIXES)
        cacheable = (
            tier == "read_parallel"
            and safe_prefix
            and not bool(getattr(tool, "is_irreversible", False))
        )
        digest = hashlib.sha256(
            _stable_json(
                {
                    "tool": tool_name,
                    "args": args,
                    "user_id": user_id,
                    "org_id": org_id,
                    "role": user_role,
                }
            ).encode("utf-8")
        ).hexdigest()
        key = rk(org_id, "tool_result_cache", digest)
        return ToolResultCachePolicy(
            cacheable=cacheable,
            cache_key=key,
            ttl_seconds=ttl_seconds,
            reason="safe_read_only_tool" if cacheable else f"not_cacheable:{tier}",
            tier=tier,
        )

    async def get_cached_tool_result(self, policy: ToolResultCachePolicy) -> Any | None:
        if not policy.cacheable:
            return None
        return await cache_service.get(policy.cache_key)

    async def set_cached_tool_result(
        self,
        policy: ToolResultCachePolicy,
        result: Any,
    ) -> bool:
        if not policy.cacheable or not self._is_cacheable_tool_result(result):
            return False
        return await cache_service.set(
            policy.cache_key,
            result,
            ttl=policy.ttl_seconds,
        )

    @staticmethod
    def _is_cacheable_tool_result(result: Any) -> bool:
        text = result if isinstance(result, str) else _stable_json(result)
        stripped = text.strip()
        return not (
            stripped.startswith("Error:")
            or "Permission Denied" in stripped
            or "confirmation_required" in stripped
        )

    def build_conditional_reflect_policy(
        self,
        *,
        complexity: Any,
        completed_tools: list[Any] | None = None,
        confidence_score: float = 0.0,
        has_write_or_high_risk_tool: bool = False,
        tool_failed: bool = False,
        elapsed_ms: float = 0,
    ) -> ConditionalReflectPolicy:
        completed_tools = completed_tools or []
        max_reflections = _get_reflection_budget(complexity, completed_tools)
        if has_write_or_high_risk_tool:
            return ConditionalReflectPolicy(
                decision="reflect_and_critic",
                reason="write_or_high_risk_tool",
                max_reflections=max_reflections,
                requires_critic=True,
            )
        if tool_failed:
            return ConditionalReflectPolicy(
                decision="reflect",
                reason="tool_failure",
                max_reflections=max_reflections,
            )
        if confidence_score and confidence_score < 0.72:
            return ConditionalReflectPolicy(
                decision="reflect",
                reason="low_confidence",
                max_reflections=max_reflections,
            )
        if elapsed_ms > int(getattr(settings, "AI_RESPONSE_P95_MS", 5000)) * 0.8:
            return ConditionalReflectPolicy(
                decision="skip",
                reason="latency_slo_guard",
                max_reflections=max_reflections,
            )
        if max_reflections <= 0:
            return ConditionalReflectPolicy(
                decision="skip",
                reason="reflection_budget_zero",
                max_reflections=max_reflections,
            )
        return ConditionalReflectPolicy(
            decision="reflect",
            reason="quality_gate_default",
            max_reflections=max_reflections,
        )

    def build_prompt_and_tool_slimming_plan(
        self,
        *,
        tool_count: int,
        path: ChatPath,
        max_tools: int = 8,
    ) -> dict[str, Any]:
        if path == "fast_path":
            allowed_tools = 0
        elif path == "standard_path":
            allowed_tools = min(max_tools, 5)
        else:
            allowed_tools = min(max_tools, max(5, min(tool_count, 8)))
        return {
            "stable_prompt_segments": [
                "system_identity",
                "safety_rules",
                "role_policy",
            ],
            "dynamic_prompt_segments": [
                "route_context",
                "current_entities",
                "retrieved_evidence",
            ],
            "tool_schema_strategy": "ToolSearch top-k before prompt injection",
            "tool_schema_limit": allowed_tools,
            "tool_count": tool_count,
        }

    def build_model_quality_policy(
        self, requested_model: str | None = None
    ) -> dict[str, Any]:
        model_decision = enforce_model_policy(
            requested_model,
            source="chat_response_acceleration",
            environment="production",
        )
        return {
            "default_model": LOW_COST_DEFAULT_MODEL,
            "model_policy_decision": asdict(model_decision),
            "fallback": "repair_with_low_cost_model_before_any_higher_cost_escalation",
            "quality_triggers": [
                "missing_evidence",
                "tool_failure",
                "low_confidence",
                "unsafe_or_high_risk_action",
            ],
        }

    def get_acceleration_contract(self) -> dict[str, Any]:
        budget = ContextLoadBudget()
        return {
            "source": "Nexus chat response acceleration",
            "areas": list(ACCELERATION_AREAS),
            "default_model_literal": "deepseek-v4-flash",
            "path_model": {
                "fast_path": "safe greetings, help, no-tool answers",
                "standard_path": "short business/general queries with slim context",
                "deep_agent_path": "tool, RAG, write, approval, tender, or multi-step tasks",
            },
            "streaming_first_response": {
                "time_to_first_status_target_ms": 800,
                "status_before_agent": True,
                "progress_envelope": "chat_acceleration",
            },
            "context_load_budget": budget.to_dict(),
            "tool_execution_tiers": {
                "read_parallel": "parallel and cacheable when safe",
                "write_serial_hitl": "serial, audited, confirmation-gated",
                "background_slow": "progress-first, non-blocking when possible",
            },
            "tool_result_cache": {
                "key_scope": "org_id + user_id + role + tool + args",
                "ttl_seconds": 120,
                "cache_only_read_prefixes": READ_ONLY_TOOL_PREFIXES,
            },
            "model_quality_policy": self.build_model_quality_policy(),
            "prompt_slimming": self.build_prompt_and_tool_slimming_plan(
                tool_count=100,
                path="deep_agent_path",
            ),
            "conditional_reflect_policy": {
                "reflect_on": [
                    "write_or_high_risk_tool",
                    "tool_failure",
                    "low_confidence",
                ],
                "skip_on": [
                    "simple_fast_path",
                    "reflection_budget_zero",
                    "latency_slo_guard",
                ],
            },
            "latency_harness": {
                "metrics": [
                    "time_to_first_token",
                    "intent_route_ms",
                    "context_load_ms",
                    "llm_first_token_ms",
                    "tool_total_ms",
                    "graph_rag_ms",
                    "total_response_ms",
                    "quality_score",
                    "tool_success_rate",
                ],
                "simple_target_first_token_ms": 1000,
                "standard_target_total_ms": 5000,
                "deep_agent_requires_progress": True,
            },
        }

    def validate_acceleration_contract(self) -> dict[str, Any]:
        contract = self.get_acceleration_contract()
        checks = {
            "covers_ten_areas": set(ACCELERATION_AREAS).issubset(
                set(contract["areas"])
            ),
            "has_three_layer_path_model": set(contract["path_model"])
            == {"fast_path", "standard_path", "deep_agent_path"},
            "has_context_budget": contract["context_load_budget"]["timeout_ms"] <= 800,
            "has_tool_cache_scope": "org_id + user_id"
            in contract["tool_result_cache"]["key_scope"],
            "forces_low_cost_model": contract["model_quality_policy"]["default_model"]
            == LOW_COST_DEFAULT_MODEL,
            "slims_tool_schema": contract["prompt_slimming"]["tool_schema_limit"] <= 8,
            "conditional_reflect": "write_or_high_risk_tool"
            in contract["conditional_reflect_policy"]["reflect_on"],
            "latency_harness_present": "time_to_first_token"
            in contract["latency_harness"]["metrics"],
        }
        return {
            "passed": all(checks.values()),
            "checks": checks,
            "area_count": len(contract["areas"]),
        }


chat_response_acceleration_service = ChatResponseAccelerationService()
