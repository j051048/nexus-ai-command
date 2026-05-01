"""[H] LLM invocation + circuit breaker + retry, [I] response diagnostics."""

import asyncio
import contextlib
import time

from app.agent.node_helpers import (
    _ALWAYS_INCLUDE_TOOLS,
    AgentConfig,
    AgentPhase,
    QueryComplexity,
    ThinkingStep,
    _get_tool_schemas,
    invoke_with_fallback,
    logger,
    plugin_system_service,
    record_llm_latency,
)
from app.services.error_recovery_service import llm_circuit_breaker
from app.agent.plan.self_consistency import plan_with_self_consistency
from app.services.plugin_system_service import ExtensionPoint


class LLMCallResult:
    """Container for LLM call outputs."""

    __slots__ = (
        "ai_msg",
        "input_tokens",
        "output_tokens",
        "sc_succeeded",
        "sc_candidates",
        "error_result",
    )

    def __init__(self):
        self.ai_msg = None
        self.input_tokens = 0
        self.output_tokens = 0
        self.sc_succeeded = False
        self.sc_candidates: list = []
        self.error_result: dict | None = None


async def call_llm(
    *,
    llm,
    lc_msgs: list,
    agent_config: AgentConfig,
    model: str | None,
    state: dict,
    complexity: QueryComplexity,
    iteration: int,
    resolved: dict | None,
    config,
) -> LLMCallResult:
    """Execute the LLM call with circuit-breaker, retry, self-consistency, plugin hooks, and diagnostics.

    Returns an LLMCallResult. If error_result is set, the caller should return it immediately.
    """
    result = LLMCallResult()

    # P1 Plugin: PRE_CHAT hook
    try:
        hook_ctx = await plugin_system_service.run_hooks(
            ExtensionPoint.PRE_CHAT,
            {"messages": lc_msgs, "model": model, "config": agent_config},
        )
        if "messages" in hook_ctx and isinstance(hook_ctx["messages"], list):
            lc_msgs = hook_ctx["messages"]
    except Exception as e:
        logger.error(f"[PlanNode] PRE_CHAT hook error: {e}")

    # Circuit breaker check
    if not llm_circuit_breaker.allow_request():
        result.error_result = {
            "error": "LLM 服务断路器已打开，请稍后重试。",
            "current_phase": AgentPhase.ERROR,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.PLANNING.value,
                    content="⚠️ LLM 服务暂时不可用（断路器保护），请稍后再试",
                )
            ],
        }
        return result

    # Prepare tool schemas for self-consistency / retry
    if complexity == QueryComplexity.SIMPLE:
        tool_schemas = [
            s
            for s in _get_tool_schemas(
                agent_config.user_role, scene_code=state.get("scene_code")
            )
            if s["function"]["name"] in _ALWAYS_INCLUDE_TOOLS
        ] or None
    else:
        tool_schemas = _get_tool_schemas(
            agent_config.user_role,
            intent_summary=state.get("intent_summary", ""),
            scene_code=state.get("scene_code"),
            intent_domains=state.get("intent_domains"),
        )

    _llm_start = time.time()

    # ── CRITICAL Self-Consistency: 多次采样投票（仅首轮） ──
    if complexity == QueryComplexity.CRITICAL and iteration == 0:
        sc_result, sc_candidates = await plan_with_self_consistency(
            lc_msgs,
            agent_config,
            model,
            tool_schemas,
            resolved_config=resolved,
        )
        if sc_result is not None:
            result.ai_msg = sc_result
            record_llm_latency(
                model=model or agent_config.model,
                duration_ms=(time.time() - _llm_start) * 1000,
            )
            llm_circuit_breaker.record_success()
            result.sc_succeeded = True
            result.sc_candidates = sc_candidates
        else:
            logger.warning(
                "[PlanNode] Self-Consistency failed, falling back to single invoke"
            )

    # Standard invoke with retry
    if not result.sc_succeeded:
        for attempt in range(3):
            try:
                result.ai_msg = await invoke_with_fallback(
                    llm,
                    lc_msgs,
                    config=agent_config,
                    model=model,
                    streaming=True,
                    tool_schemas=tool_schemas,
                    complexity_tier=complexity.model_tier,
                )
                record_llm_latency(
                    model=model or agent_config.model,
                    duration_ms=(time.time() - _llm_start) * 1000,
                )
                llm_circuit_breaker.record_success()
                break
            except Exception as e:
                error_str = str(e).lower()
                is_retryable = any(
                    kw in error_str
                    for kw in ("timeout", "timed out", "connection", "connect")
                )
                if is_retryable and attempt < 2:
                    logger.warning(
                        f"[PlanNode] LLM call timeout (attempt {attempt + 1}/3), retrying..."
                    )
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                llm_circuit_breaker.record_failure()
                logger.error(
                    f"[PlanNode] LLM call failed after {attempt + 1} attempts: {e}"
                )
                result.error_result = {
                    "error": f"LLM 规划失败: {str(e)}",
                    "current_phase": AgentPhase.ERROR,
                    "thinking_steps": [
                        ThinkingStep(
                            phase=AgentPhase.PLANNING.value,
                            content=f"⚠️ LLM 调用异常: {str(e)}",
                        )
                    ],
                }
                return result

    ai_msg = result.ai_msg

    # ── [I] Response diagnostics ──
    usage = ai_msg.response_metadata.get("token_usage", {})
    result.input_tokens = usage.get("prompt_tokens", 0)
    result.output_tokens = usage.get("completion_tokens", 0)
    if hasattr(ai_msg, "_sc_total_input_tokens"):
        result.input_tokens = ai_msg._sc_total_input_tokens
        result.output_tokens = ai_msg._sc_total_output_tokens

    finish_reason = ai_msg.response_metadata.get("finish_reason", "unknown")
    actual_api_model = ai_msg.response_metadata.get(
        "model_name"
    ) or ai_msg.response_metadata.get("model", "")
    content_len = len(ai_msg.content or "")
    tool_call_count = len(ai_msg.tool_calls or [])
    requested_model = model or agent_config.model
    logger.info(
        "[PlanNode] LLM response: requested=%s actual=%s finish=%s content_len=%d "
        "tool_calls=%d in_tok=%d out_tok=%d",
        requested_model,
        actual_api_model or "?",
        finish_reason,
        content_len,
        tool_call_count,
        result.input_tokens,
        result.output_tokens,
    )
    if (
        actual_api_model
        and actual_api_model != requested_model
        and requested_model not in actual_api_model
    ):
        logger.warning(
            "[PlanNode] MODEL MISMATCH: requested '%s' but API returned '%s' — provider may have downgraded",
            requested_model,
            actual_api_model,
        )

    # Langfuse: log LLM generation
    _configurable = (
        (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    )
    trace_logger = _configurable.get("trace_logger")
    if trace_logger:
        with contextlib.suppress(Exception):
            trace_logger.log_generation(
                model=model or agent_config.model,
                input_messages=(
                    [{"role": "user", "content": str(lc_msgs[-1].content)[:500]}]
                    if lc_msgs
                    else []
                ),
                output=str(ai_msg.content or "")[:1000],
                usage={
                    "prompt_tokens": result.input_tokens,
                    "completion_tokens": result.output_tokens,
                },
            )

    # P1 Plugin: POST_CHAT hook
    try:
        await plugin_system_service.run_hooks(
            ExtensionPoint.POST_CHAT,
            {
                "ai_message": ai_msg,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )
    except Exception as e:
        logger.error(f"[PlanNode] POST_CHAT hook error: {e}")

    return result
