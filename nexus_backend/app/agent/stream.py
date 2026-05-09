"""
SSE Streaming Adapter — bridges the LangGraph agent to FastAPI StreamingResponse.

This module:
1. Accepts the same parameters as the old ChatService.stream_response
2. Builds the initial AgentState
3. Runs the compiled graph via astream()
4. Yields SSE-formatted events for each state update (thinking steps, final response)
5. Handles token tracking, moderation, and persistence post-completion

The frontend receives the same SSE protocol as before, so this is a
drop-in replacement.
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

_background_tasks: set[asyncio.Task] = set()

import contextlib

from app.agent.graph import get_agent_graph
from app.agent.memory import persist_result, prepare_initial_state
from app.agent.safety_guards import is_mutation_fast_path as _is_mutation_fast_path
from app.agent.sse_protocol import (
    _chunk_text,
    _sse_ask_user,
    _sse_circuit_break,
    _sse_confirmation,
    _sse_content,
    _sse_data,
    _sse_keepalive,
    _sse_status,
    _sse_thinking,
    _sse_tool_progress,
    _sse_tool_result,
    _with_keepalive,
)
from app.agent.state import (
    CURRENT_SCHEMA_VERSION,
    AgentConfig,
    AgentPhase,
    AgentState,
    QueryComplexity,
    ThinkingStep,
)
from app.agent.stream_checks import run_pre_checks
from app.agent.think_tags import extract_clean_content, strip_think_tags
from app.core.config import settings
from app.core.database import supabase
from app.core.tenant_throttle import tenant_throttle
from app.core.trace_logger import TraceLogger
from app.services.agent_trace_service import TraceStatus, agent_trace_service
from app.services.token_service import (
    record_completion,
    token_counter,
    usage_tracker,
)

logger = logging.getLogger(__name__)


# ── Shared stream helpers (DRY extraction) ──────────────────────────────────


async def _emit_error_and_cleanup(
    all_thinking_steps: list,
    tracer: "TraceLogger | None",
    trace_id: str,
    error: Exception,
) -> AsyncGenerator[str, None]:
    """Yield standard error SSE sequence and clean up tracing."""
    yield _sse_content(
        "\n\n⚠️ 处理请求时发生内部错误，请稍后重试。如问题持续，请联系管理员。"
    )
    yield _sse_data(
        {"thinking_chain_complete": True, "total_steps": len(all_thinking_steps)}
    )
    yield "data: [DONE]\n\n"
    if tracer:
        tracer.log_error(str(error))
        tracer.log_end()
    with contextlib.suppress(Exception):
        agent_trace_service.end_trace(
            trace_id, TraceStatus.FAILED, error=str(error)[:500]
        )


async def _cleanup_on_disconnect(
    throttle_ctx: Any,
    trace_id: str,
    tracer: "TraceLogger | None" = None,
    log_msg: str = "",
) -> None:
    """Release throttle and end trace on client disconnect."""
    await throttle_ctx.__aexit__(None, None, None)
    if log_msg:
        logger.info(log_msg)
    if tracer:
        tracer.log_end(total_tokens=0)
    with contextlib.suppress(Exception):
        agent_trace_service.end_trace(trace_id, TraceStatus.CANCELLED)


def _filter_think_content(content: str) -> str:
    """Strip <think> tags from content (single-pass, no cross-chunk state)."""
    if "<think>" in content or "</think>" in content:
        return strip_think_tags(content)
    return content


# Use the singleton agent graph instance
_agent_graph = get_agent_graph()


async def run_agent_stream(**kwargs) -> AsyncGenerator[str, None]:
    """
    Wrapper for _run_agent_stream_impl that yields a status immediately
    and catches all errors to prevent StreamingResponse failures.

    P0: Includes backpressure protection — if the output buffer grows too large
    (client not consuming), we abort to prevent memory exhaustion.
    """
    yield _sse_status("正在准备 Agent...")

    # We need to capture these for possible error cleanup
    tracer = kwargs.get("tracer")
    _trace_id = kwargs.get("_trace_id") or str(uuid.uuid4())
    all_thinking_steps = []

    # P0 backpressure: track buffered output to detect stalled consumers
    _buffered_bytes = 0
    _MAX_BUFFER_BYTES = 2 * 1024 * 1024  # 2 MB — if client not consuming, abort

    try:
        async for chunk in _run_agent_stream_impl(**{**kwargs, "_trace_id": _trace_id}):
            _buffered_bytes += (
                len(chunk.encode("utf-8")) if isinstance(chunk, str) else len(chunk)
            )
            if _buffered_bytes > _MAX_BUFFER_BYTES:
                logger.warning(
                    "[Stream] Backpressure limit hit (%d bytes buffered), aborting stream "
                    "to prevent memory exhaustion. Client may have disconnected.",
                    _buffered_bytes,
                )
                yield _sse_content("\n\n⚠️ 响应数据过大，已自动中断。")
                yield "data: [DONE]\n\n"
                return
            yield chunk
    except asyncio.CancelledError:
        # Client disconnected — FastAPI/Starlette cancels the generator
        logger.info("[Stream] Client disconnected (CancelledError), cleaning up")
        return
    except Exception as e:
        logger.error(f"[Stream] Global agent failure: {e}", exc_info=True)
        async for evt in _emit_error_and_cleanup(
            all_thinking_steps, tracer, _trace_id, e
        ):
            yield evt


async def _run_agent_stream_impl(
    messages: list[dict],
    config: dict,
    user_id: str,
    system_prompt: str,
    tracer: TraceLogger | None = None,
    system_confirmed: bool = False,
    confirmed_tool: dict | None = None,
    session_id: str | None = None,
    db_client: Any | None = None,
    agent_name: str | None = None,
    user_role: str = "employee",
    org_id: str | None = None,
    # VMD extensions
    scene_code: str | None = None,
    vmd_agent_code: str | None = None,
    _trace_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Main entry point: runs the LangGraph agent and streams SSE events.

    This function is a drop-in replacement for ChatService.stream_response,
    maintaining the same SSE protocol for the frontend.
    """
    # Use provided trace_id or generate new
    _trace_id = _trace_id or str(uuid.uuid4())
    all_thinking_steps: list[ThinkingStep] = []
    start_time = time.time()

    # ── 0. Build AgentConfig with settings ──
    agent_config = AgentConfig(
        user_id=user_id,
        session_id=session_id or "default",
        agent_name=agent_name or "default",
        api_key=config.get("api_key", "") or settings.OPENAI_API_KEY,
        base_url=config.get("base_url", "https://api.openai.com/v1")
        or settings.AI_BASE_URL,
        model=config.get("model", "gpt-4o") or settings.AI_DEFAULT_MODEL,
        mini_model=config.get("mini_model", "gpt-4o-mini"),
        system_confirmed=system_confirmed,
        confirmed_tool=confirmed_tool,
        user_role=user_role,
        org_id=org_id,
        token=config.get("token", ""),
        max_iterations=settings.LANGGRAPH_MAX_ITERATIONS,
        tool_timeout=settings.LANGGRAPH_TOOL_TIMEOUT,
        gather_timeout=settings.LANGGRAPH_GATHER_TIMEOUT,
        enable_rag_inject=settings.LANGGRAPH_ENABLE_RAG_INJECT,
        rag_inject_threshold=settings.LANGGRAPH_RAG_INJECT_THRESHOLD,
        rag_inject_limit=settings.LANGGRAPH_RAG_INJECT_LIMIT,
        reflect_use_llm=settings.LANGGRAPH_REFLECT_USE_LLM,
    )

    # ── 0b. Start agent trace for observability (P3) ──
    _user_query = ""
    for _m in reversed(messages):
        if _m.get("role") == "user":
            _user_query = (_m.get("content") or "")[:500]
            break
    try:
        from app.agent.ab_testing import get_active_assignments

        _ab_assignments = get_active_assignments(
            user_id, user_role=agent_config.user_role
        )
    except Exception:
        _ab_assignments = {}

    try:
        agent_trace_service.start_trace(
            trace_id=_trace_id,
            thread_id=f"{org_id or 'default'}::{session_id or 'default'}",
            user_id=user_id,
            query=_user_query,
            org_id=org_id,
            metadata={
                "agent_name": agent_name,
                "scene_code": scene_code,
                **(
                    {f"ab_{k}": v for k, v in _ab_assignments.items()}
                    if _ab_assignments
                    else {}
                ),
            },
        )
    except Exception:
        logger.error("[Stream] Failed to start agent trace", exc_info=True)

    # ── 0c. Pre-resolve model configs for all tiers (Step 2: centralized resolution) ──
    # P0 #1: Parallel resolution via asyncio.gather (was 4x serial await)
    try:
        from app.services.llm_helpers import resolve_model_config

        _tiers = ("economy", "balanced", "power", "flagship")

        async def _resolve_one(tier: str):
            try:
                return tier, await resolve_model_config(
                    org_id=org_id,
                    scene_code=scene_code or "",
                    complexity_tier=tier,
                )
            except Exception:
                return tier, None

        _resolve_results = await asyncio.gather(*[_resolve_one(t) for t in _tiers])
        _resolved_configs = {t: rc for t, rc in _resolve_results if rc is not None}
        if _resolved_configs:
            agent_config.resolved_configs = _resolved_configs
            logger.info(
                f"[Stream] Pre-resolved model configs for tiers: {list(_resolved_configs.keys())}"
            )
    except Exception:
        logger.error("[Stream] Failed to pre-resolve model configs", exc_info=True)

    # ── 1-2. Pre-flight checks (token budget, PII) ──
    # P0 #5: skip_moderation=True because chat.py already ran content moderation
    checks_passed, check_events, last_user_content = await run_pre_checks(
        messages=messages,
        user_id=user_id,
        model=agent_config.model,
        session_id=session_id,
        org_id=org_id,
        skip_moderation=True,
    )
    if not checks_passed:
        for evt in check_events:
            yield evt
        return

    # Estimate input tokens for later token tracking (was computed inside pre-checks)
    input_tokens = token_counter.count_tokens(
        " ".join(m.get("content", "") for m in messages), agent_config.model
    )

    # ── 2b. Early SIMPLE detection — skip RAG for casual chat ──
    # Also gate RAG for MODERATE queries: only enable when query suggests
    # the user needs information from uploaded documents / knowledge base.

    # ── P0 #11: Trim ENTERPRISE_CAPABILITIES by user role ──
    try:
        from app.core.prompts_registry import (
            ENTERPRISE_CAPABILITIES,
            get_capabilities_for_role,
        )

        _trimmed_caps = get_capabilities_for_role(user_role)
        if _trimmed_caps != ENTERPRISE_CAPABILITIES:
            system_prompt = system_prompt.replace(
                ENTERPRISE_CAPABILITIES, _trimmed_caps
            )
            logger.debug(f"[Stream] Trimmed capabilities for role={user_role}")
    except Exception:
        pass

    # ── P1 #6: Early complexity classification (moved up from L368) ──
    # Determines _is_simple BEFORE behavior_preferences and soul_document
    # so SIMPLE queries can skip those expensive lookups.
    _is_simple = False
    early_complexity = None
    intent_summary = ""
    if last_user_content:
        from app.agent.router import _should_enable_rag, classify_query

        early_complexity, intent_summary = classify_query(last_user_content)
        if early_complexity == QueryComplexity.SIMPLE:
            _prev_was_contextual = False
            if len(last_user_content.strip()) <= 4 and len(messages) >= 3:
                for prev_msg in reversed(messages[:-1]):
                    if prev_msg.get("role") == "user":
                        prev_text = prev_msg.get("content", "")
                        prev_cx, _ = classify_query(prev_text)
                        if prev_cx != QueryComplexity.SIMPLE:
                            _prev_was_contextual = True
                        break
            if _prev_was_contextual:
                early_complexity = QueryComplexity.MODERATE
                intent_summary = "短消息跟进(保留上下文)"
                logger.debug(
                    f"[Stream] Short follow-up detected, upgraded to MODERATE: '{last_user_content}'"
                )
            else:
                agent_config.enable_rag_inject = False
                _is_simple = True
        elif agent_config.enable_rag_inject and not _should_enable_rag(
            last_user_content
        ):
            agent_config.enable_rag_inject = False
            logger.debug(
                "[Stream] RAG skipped: query has no document/knowledge indicators"
            )

    # ── 2a-bis. Load user behavior preferences ──
    # P1 #6: Skip for SIMPLE queries — greetings don't need style preferences
    _behavior_prefs: dict = {}
    if not _is_simple:
        try:
            _prefs_res = (
                await (db_client or supabase)
                .table("ai_settings")
                .select("behavior_preferences")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if _prefs_res.data and _prefs_res.data[0].get("behavior_preferences"):
                _behavior_prefs = _prefs_res.data[0]["behavior_preferences"]
        except Exception:
            pass

    if _behavior_prefs:
        _pref_lines: list[str] = []
        if _behavior_prefs.get("response_style") == "concise":
            _pref_lines.append(
                "用户偏好简洁回复，请控制在300字以内，直接给出核心信息。"
            )
        elif _behavior_prefs.get("response_style") == "detailed":
            _pref_lines.append(
                "用户偏好详细回复，请提供完整分析、数据支撑和可执行建议。"
            )
        if _behavior_prefs.get("preferred_chart"):
            _pref_lines.append(
                f"当需要展示数据可视化时，用户偏好的图表类型: {_behavior_prefs['preferred_chart']}"
            )
        if _behavior_prefs.get("language") == "en":
            _pref_lines.append("Please respond in English.")
        if _pref_lines:
            system_prompt += "\n\n## 用户个人偏好\n" + "\n".join(_pref_lines)

    # ── 2a-ab. A/B test — apply experiment config to system prompt ──
    if _ab_assignments:
        try:
            from app.agent.ab_testing import get_experiment_config

            for exp_name in _ab_assignments:
                exp_config = get_experiment_config(
                    exp_name, user_id, user_role=agent_config.user_role
                )
                suffix = exp_config.get("prompt_suffix")
                if suffix:
                    system_prompt += suffix
        except Exception:
            logger.debug("[Stream] A/B prompt injection skipped", exc_info=True)

    # ── 2b. Soul Document — 用灵魂文档替换默认身份认知 ──
    # P1 #6: Skip for SIMPLE queries — soul document is expensive and unnecessary for greetings
    if not _is_simple:
        try:
            from app.services.soul_document_service import soul_document_service

            _soul_prompt = await soul_document_service.get_compiled_prompt(org_id)
            if _soul_prompt:
                from app.core.prompts_registry import SELF_AWARENESS

                # 如果 system_prompt 包含默认 SELF_AWARENESS，替换之
                _sa_marker = SELF_AWARENESS[:30]
                if _sa_marker in system_prompt:
                    system_prompt = system_prompt.replace(SELF_AWARENESS, _soul_prompt)
                else:
                    # DB/YAML 加载的 prompt 可能不含 SELF_AWARENESS，追加到头部
                    system_prompt = _soul_prompt + "\n\n" + system_prompt
        except Exception:
            logger.debug("[Stream] Soul document injection skipped", exc_info=True)

    # ── P0 #10: On-demand GenUI protocol injection ──
    # Only inject the ~1,800 token GenUI prompt when intent suggests UI output
    _GENUI_INTENT_KEYWORDS = (
        "数据",
        "报表",
        "图表",
        "分析",
        "对比",
        "排名",
        "审批",
        "日报",
        "周报",
        "写邮件",
        "待办",
        "日程",
        "看板",
        "漏斗",
        "进度",
        "热力",
        "甘特",
        "表格",
        "统计",
        "趋势",
        "同比",
        "环比",
        "占比",
        "分布",
        "report",
        "chart",
        "dashboard",
        "compare",
        "status",
    )
    if last_user_content and not _is_simple:
        _need_genui = any(kw in last_user_content for kw in _GENUI_INTENT_KEYWORDS)
        if _need_genui:
            from app.core.prompts_registry import GEN_UI_PROTOCOL

            system_prompt += "\n" + GEN_UI_PROTOCOL
            logger.debug("[Stream] GenUI protocol injected (intent match)")

    if tracer:
        tracer.log_start(
            [
                {"role": m.get("role", "user"), "content": m.get("content", "")}
                for m in messages
            ]
        )

    # ── 3. Prepare initial state via Memory Manager ──
    yield _sse_status("正在思考...")

    prep_result = await prepare_initial_state(
        messages,
        system_prompt,
        agent_config,
        db_client=db_client,
        skip_semantic=_is_simple,
        state=(
            {"complexity": early_complexity, "intent_summary": intent_summary}
            if early_complexity
            else None
        ),
    )
    lc_messages = prep_result["messages"]
    cached_response = prep_result["cached_response"]
    rag_context = prep_result["rag_context"]
    rag_sources = prep_result["rag_sources"]

    # Fast path: semantic cache hit
    # Skip cache when system_confirmed=True — user confirmed a blocked action
    # and we must execute the tool, not return a cached response.
    if cached_response is not None and not system_confirmed:
        # Cache poisoning defense: sanitize cached content before returning
        from app.services.content_moderation import sanitize_output

        cached_response = sanitize_output(cached_response)
        logger.info("[Stream] Semantic cache hit, streaming cached response")
        words = cached_response.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield _sse_content(chunk)
            await asyncio.sleep(0.005)

        try:
            cache_tokens = token_counter.count_tokens(
                cached_response, agent_config.model
            )
            await record_completion(
                user_id, input_tokens, cache_tokens, agent_config.model
            )
        except Exception as e:
            logger.warning(f"Failed to record cache tokens: {e}", exc_info=True)

        yield "data: [DONE]\n\n"
        if tracer:
            tracer.log_end(total_tokens=input_tokens)
        return

    # ── 4. Build initial AgentState ──
    initial_state: AgentState = {
        "messages": lc_messages,
        "current_phase": AgentPhase.ROUTING,
        "iteration": 0,
        "complexity": early_complexity or QueryComplexity.MODERATE,
        "intent_summary": intent_summary,
        "selected_model": agent_config.model,
        "plan": "",
        "requires_tools": False,
        "pending_tool_calls": [],
        "completed_tool_calls": [],
        "reflection": "",
        "is_hallucination": False,
        "needs_replanning": False,
        "confidence_score": 0.0,
        "reflection_guidance": "",
        "critic_feedback": "",
        "critic_passed": True,
        "final_response": "",
        "thinking_steps": [],
        "config": agent_config,
        "error": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "rag_context": rag_context,
        "rag_sources": rag_sources,
        "error_recovery_attempted": False,
        "error_recovery_level": 0,
        # VMD multi-agent orchestration fields
        "agent_code": vmd_agent_code or "",
        "scene_code": scene_code or "",
        "main_task_id": None,
        "sub_task_id": None,
        "parent_agent_code": None,
        "delegation_results": [],
        "wbs_structure": None,
        # Memory already injected by prepare_initial_state — skip middleware re-fetch
        "_memory_injected": True,
        # P0: Context compaction
        "context_compacted_summary": "",
        # P1: Task decomposition
        "_task_decomposition_done": False,
        "_task_steps": [],
        "_active_step_index": 0,
        # Schema version for checkpoint compatibility
        "_schema_version": CURRENT_SCHEMA_VERSION,
    }

    # ── 5. Run graph with granular event streaming (astream_events) ──
    accumulated_state: dict[str, Any] = dict(initial_state)
    all_thinking_steps: list[ThinkingStep] = []
    streamed_plan_content = False  # Track whether plan tokens were already streamed
    streamed_plan_text = ""  # Track what was streamed during plan phase
    _graph_start_time = time.time()

    # ── Mid-flight output token budget breaker ──
    # Counts streamed characters → approximate tokens to cap runaway output.
    # Uses char÷3 as a mixed Chinese/English approximation (cheap, no tiktoken).
    _streamed_chars = 0
    _output_token_budget = settings.TOKEN_BUDGET_MAX_PER_SESSION  # 50 000 by default
    _budget_breached = False

    # Checkpointer corrupt state detection keywords
    corrupt_state_keywords = (
        "deserializ",
        "pickle",
        "ToolCallRecord",
        "unmarshal",
        "decode",
        "SerializationError",
    )

    try:
        # P1 Security: Prefix thread_id with org_id to prevent cross-tenant
        # state leakage via the LangGraph checkpointer.
        # CRITICAL FIX: Always use a unique thread_id per message to prevent
        # the checkpointer from merging old state into new runs.
        # AgentState.messages uses operator.add (accumulator), so reusing
        # the same thread_id causes the checkpoint's old messages to be
        # APPENDED to the new input messages, creating massive duplication.
        # The frontend already sends the full conversation history, so the
        # checkpointer provides no value for multi-turn context — it only
        # causes confusion (LLM sees duplicated messages and may repeat
        # old responses).
        base_thread = f"{agent_config.org_id or 'default'}::{agent_config.session_id}"
        scoped_thread_id = f"{base_thread}::msg-{int(start_time)}"

        # Durable observability run id shared by graph nodes and final stream
        try:
            from app.services.agent_run_observability import agent_run_observer

            _agent_run_id = await agent_run_observer.start_run(
                thread_id=scoped_thread_id,
                org_id=agent_config.org_id,
                user_id=user_id,
                session_id=session_id or "default",
                trace_id=_trace_id,
                metadata={
                    "mode": "sse",
                    "agent_name": agent_name,
                    "scene_code": scene_code,
                    "vmd_agent_code": vmd_agent_code,
                },
            )
            initial_state["agent_run_id"] = _agent_run_id
            accumulated_state["agent_run_id"] = _agent_run_id
        except Exception:
            _agent_run_id = None
            logger.debug("[Stream] agent_runs start skipped", exc_info=True)

        # Track whether we're inside a <think>...</think> block during streaming.
        # Reasoning models (step-3.5-flash, DeepSeek-R1, QwQ, etc.) emit these
        # tags which must be suppressed before reaching the frontend.
        _inside_think = False

        # ── Tenant-level concurrency throttle (fair-share) ──
        _throttle_ctx = tenant_throttle.acquire(org_id or "default")
        await _throttle_ctx.__aenter__()

        async for event in _with_keepalive(
            _agent_graph.astream_events(
                initial_state,
                thread_id=scoped_thread_id,
                config={
                    "configurable": {
                        "trace_logger": tracer,
                        "trace_id": _trace_id,
                    },
                },
                version="v2",
            )
        ):
            if event is None:
                yield _sse_keepalive()
                continue

            kind = event.get("event")

            # A. Continuous Token Streaming
            if kind == "on_chat_model_stream":
                node_name = event.get("metadata", {}).get("langgraph_node")
                chunk = event["data"]["chunk"]
                content = chunk.content

                # --- Reasoning model detection ---
                # Some proxy APIs merge reasoning_content into the content
                # stream. If the chunk has reasoning_content in additional_kwargs,
                # the real answer hasn't started yet — skip the content.
                chunk_kwargs = getattr(chunk, "additional_kwargs", {}) or {}
                if chunk_kwargs.get("reasoning_content"):
                    # This chunk is reasoning, not the real answer — skip
                    continue

                if content and node_name == "respond":
                    # --- Filter reasoning model <think> tags ---
                    # Handle <think>...</think> that may span multiple chunks
                    emit = content
                    if _inside_think:
                        # We're inside a think block, suppress until </think>
                        if "</think>" in content:
                            _inside_think = False
                            emit = content.split("</think>", 1)[1].lstrip("\n")
                        else:
                            emit = ""
                    elif "<think>" in content:
                        # Think block starts in this chunk
                        before = content.split("<think>", 1)[0]
                        remainder = content.split("<think>", 1)[1]
                        if "</think>" in remainder:
                            # Complete <think>...</think> in one chunk
                            after = remainder.split("</think>", 1)[1].lstrip("\n")
                            emit = before + after
                        else:
                            # Think block continues into next chunks
                            _inside_think = True
                            emit = before

                    if emit:
                        yield _sse_content(emit)
                        _streamed_chars += len(emit)
                        streamed_plan_content = True
                    streamed_plan_text += emit  # Use filtered content, not raw
                elif content and node_name == "plan":
                    # Mutation fast-path: when all completed tools are successful
                    # irreversible mutations, reflect+critic will be skipped, so
                    # we can stream plan tokens directly for instant UX.
                    if _is_mutation_fast_path(accumulated_state):
                        # Also filter think tags for plan streaming
                        plan_filtered = _filter_think_content(content)
                        if plan_filtered:
                            yield _sse_content(plan_filtered)
                            _streamed_chars += len(plan_filtered)
                        streamed_plan_content = True
                    # Always accumulate plan text for final_response dedup check
                    streamed_plan_text += content

                # ── Mid-flight budget check (both respond & plan paths) ──
                if not _budget_breached and _streamed_chars // 3 > _output_token_budget:
                    _budget_breached = True
                    logger.warning(
                        "[Stream] Output token budget breached: ~%d tokens "
                        "(chars=%d, limit=%d) user=%s session=%s",
                        _streamed_chars // 3,
                        _streamed_chars,
                        _output_token_budget,
                        user_id,
                        session_id,
                    )
                    yield _sse_data(
                        {
                            "budget_breaker": {
                                "reason": "output_token_limit",
                                "estimated_tokens": _streamed_chars // 3,
                                "limit": _output_token_budget,
                                "message": "回复已达到输出 token 上限，已自动截断。",
                            }
                        }
                    )
                    yield _sse_content("\n\n⚠️ 回复已达到输出上限，已自动截断。")
                    break

            # B. State Updates (when a node completes)
            elif kind == "on_chain_end":
                data = event.get("data", {})
                output = data.get("output")

                if isinstance(output, dict) and any(
                    k in output for k in ("current_phase", "thinking_steps", "messages")
                ):
                    state_delta = output

                    # Merge delta into accumulated state
                    for key, value in state_delta.items():
                        if key == "messages" and isinstance(value, list):
                            existing = accumulated_state.get("messages", [])
                            accumulated_state["messages"] = existing + value
                        elif key == "thinking_steps" and isinstance(value, list):
                            new_steps = value
                            for step in new_steps:
                                if isinstance(step, ThinkingStep):
                                    all_thinking_steps.append(step)
                                    # P2-10: Intercept __orch_meta steps → orchestration SSE
                                    if (
                                        getattr(step, "tool_name", None)
                                        == "__orch_meta"
                                    ):
                                        try:
                                            _orch_data = json.loads(step.content)
                                            yield _sse_data(
                                                {"orchestration": _orch_data}
                                            )
                                        except Exception:
                                            yield _sse_thinking(step)
                                    else:
                                        yield _sse_thinking(step)
                        elif key == "completed_tool_calls" and isinstance(value, list):
                            existing = accumulated_state.get("completed_tool_calls", [])
                            accumulated_state["completed_tool_calls"] = existing + value
                            # #15: Emit tool progress events for frontend
                            for rec in value:
                                if hasattr(rec, "tool_name"):
                                    yield _sse_tool_progress(
                                        rec.tool_name,
                                        rec.status or "success",
                                        rec.duration_ms,
                                    )
                                    # P0 FIX: Also push the raw result for GenUI/Data visualization
                                    if rec.status == "success" and rec.result:
                                        yield _sse_tool_result(
                                            rec.tool_name, rec.result, rec.status
                                        )
                        else:
                            accumulated_state[key] = value

                    # Emit phase status updates
                    phase = state_delta.get("current_phase")
                    if phase:
                        iteration = accumulated_state.get("iteration", 0)
                        status_map = {
                            AgentPhase.ROUTING: "正在分析意图...",
                            AgentPhase.PLANNING: "正在规划...",
                            AgentPhase.EXECUTING: "正在执行工具...",
                            AgentPhase.REFLECTING: "正在验证结果...",
                            AgentPhase.CRITIQUING: "正在质量评审...",
                            AgentPhase.RESPONDING: "正在生成回复...",
                        }
                        # Escalating reflect status for deeper iterations
                        if phase == AgentPhase.REFLECTING and iteration >= 2:
                            yield _sse_status(f"正在深度验证... (第{iteration}轮)")
                        elif phase == AgentPhase.PLANNING and iteration >= 3:
                            yield _sse_status(f"正在重新规划... (第{iteration}轮)")
                        else:
                            status_text = status_map.get(phase)
                            if status_text:
                                yield _sse_status(status_text)

                    # P3: Record step in agent trace
                    try:
                        _node_name = event.get("metadata", {}).get(
                            "langgraph_node", "unknown"
                        )
                        _step_tools = []
                        for _tc in state_delta.get("completed_tool_calls", []):
                            _step_tools.append(
                                {
                                    "name": getattr(_tc, "tool_name", ""),
                                    "status": getattr(_tc, "status", ""),
                                }
                            )
                        agent_trace_service.add_step(
                            trace_id=_trace_id,
                            step_id=f"{_node_name}_{accumulated_state.get('iteration', 0)}",
                            node_type=_node_name,
                            input_data={"phase": str(phase) if phase else ""},
                            output_data={
                                "has_plan": bool(state_delta.get("plan")),
                                "has_response": bool(state_delta.get("final_response")),
                                "confidence": state_delta.get("confidence_score"),
                                "prompt_snapshot": state_delta.get("prompt_snapshot")
                                or accumulated_state.get("prompt_snapshot"),
                                "context_ledger": state_delta.get("context_ledger")
                                or accumulated_state.get("context_ledger"),
                            },
                            tokens_used=(state_delta.get("total_input_tokens", 0) or 0)
                            + (state_delta.get("total_output_tokens", 0) or 0),
                            tool_calls=_step_tools or None,
                        )
                    except Exception:
                        pass  # trace failure must never break the stream

                    try:
                        from app.services.agent_run_observability import (
                            agent_run_observer,
                        )

                        await agent_run_observer.event(
                            run_id=accumulated_state.get("agent_run_id"),
                            org_id=agent_config.org_id,
                            event_type="node_end",
                            node_name=event.get("metadata", {}).get(
                                "langgraph_node", "unknown"
                            ),
                            payload={
                                "phase": str(phase) if phase else "",
                                "iteration": accumulated_state.get("iteration", 0),
                                "has_plan": bool(state_delta.get("plan")),
                                "has_response": bool(state_delta.get("final_response")),
                                "prompt_snapshot": state_delta.get("prompt_snapshot")
                                or accumulated_state.get("prompt_snapshot"),
                                "context_ledger": state_delta.get("context_ledger")
                                or accumulated_state.get("context_ledger"),
                                "completed_tools": [
                                    getattr(tc, "tool_name", "")
                                    for tc in state_delta.get(
                                        "completed_tool_calls", []
                                    )
                                ],
                            },
                        )
                    except Exception:
                        pass

        # Release tenant throttle after graph execution completes normally
        await _throttle_ctx.__aexit__(None, None, None)

    except asyncio.CancelledError:
        duration_ms = int((time.time() - start_time) * 1000)
        await _cleanup_on_disconnect(
            _throttle_ctx,
            _trace_id,
            tracer,
            f"[Stream] Client disconnected after {duration_ms}ms (user={user_id}, session={session_id})",
        )
        return

    except GeneratorExit:
        await _cleanup_on_disconnect(
            _throttle_ctx,
            _trace_id,
            log_msg=f"[Stream] Generator closed (user={user_id})",
        )
        return

    except Exception as e:
        await _throttle_ctx.__aexit__(None, None, None)
        error_str = str(e)

        # Checkpointer corrupt state detection: if deserialization fails
        # (e.g., old ToolCallRecord types, pickle errors), retry with a
        # fresh thread_id to bypass the corrupted checkpoint.
        if any(kw in error_str.lower() for kw in corrupt_state_keywords):
            logger.warning(
                f"[Stream] Checkpointer state corruption detected, retrying with fresh thread: {e}"
            )
            # Log corruption event to Langfuse for observability
            try:
                if settings.LANGFUSE_ENABLED:
                    from langfuse import Langfuse

                    langfuse = Langfuse()
                    langfuse.event(
                        name="checkpointer_corruption",
                        metadata={
                            "thread_id": scoped_thread_id,
                            "error": error_str[:200],
                        },
                    )
            except Exception:
                pass
            try:
                fresh_thread = f"{scoped_thread_id}::fresh-{int(time.time())}"
                accumulated_state = dict(initial_state)
                all_thinking_steps = []
                streamed_plan_content = False
                streamed_plan_text = ""
                _streamed_chars = 0
                _budget_breached = False

                async for event in _with_keepalive(
                    _agent_graph.astream_events(
                        initial_state,
                        thread_id=fresh_thread,
                        config={
                            "configurable": {
                                "trace_logger": tracer,
                                "trace_id": _trace_id,
                            }
                        },
                        version="v2",
                    )
                ):
                    if event is None:
                        yield _sse_keepalive()
                        continue

                    kind = event.get("event")
                    if kind == "on_chat_model_stream":
                        node_name = event.get("metadata", {}).get("langgraph_node")
                        chunk = event["data"]["chunk"]
                        content = chunk.content
                        # Skip reasoning content from reasoning models
                        chunk_kwargs = getattr(chunk, "additional_kwargs", {}) or {}
                        if chunk_kwargs.get("reasoning_content"):
                            continue
                        if content and node_name == "respond":
                            # Filter <think> tags in retry path too
                            filtered = _filter_think_content(content)
                            if filtered:
                                yield _sse_content(filtered)
                                _streamed_chars += len(filtered)
                                streamed_plan_content = True
                            streamed_plan_text += filtered or ""
                        elif content and node_name == "plan":
                            if _is_mutation_fast_path(accumulated_state):
                                plan_filtered = _filter_think_content(content)
                                if plan_filtered:
                                    yield _sse_content(plan_filtered)
                                    _streamed_chars += len(plan_filtered)
                                streamed_plan_content = True
                            streamed_plan_text += content

                        # ── Mid-flight budget check (retry path) ──
                        if (
                            not _budget_breached
                            and _streamed_chars // 3 > _output_token_budget
                        ):
                            _budget_breached = True
                            logger.warning(
                                "[Stream] Output token budget breached (retry): ~%d tokens "
                                "(chars=%d, limit=%d) user=%s",
                                _streamed_chars // 3,
                                _streamed_chars,
                                _output_token_budget,
                                user_id,
                            )
                            yield _sse_data(
                                {
                                    "budget_breaker": {
                                        "reason": "output_token_limit",
                                        "estimated_tokens": _streamed_chars // 3,
                                        "limit": _output_token_budget,
                                        "message": "回复已达到输出 token 上限，已自动截断。",
                                    }
                                }
                            )
                            yield _sse_content("\n\n⚠️ 回复已达到输出上限，已自动截断。")
                            break
                    elif kind == "on_chain_end":
                        data = event.get("data", {})
                        output = data.get("output")
                        if isinstance(output, dict) and any(
                            k in output
                            for k in ("current_phase", "thinking_steps", "messages")
                        ):
                            for key, value in output.items():
                                if key == "messages" and isinstance(value, list):
                                    accumulated_state["messages"] = (
                                        accumulated_state.get("messages", []) + value
                                    )
                                elif key == "thinking_steps" and isinstance(
                                    value, list
                                ):
                                    for step in value:
                                        if isinstance(step, ThinkingStep):
                                            all_thinking_steps.append(step)
                                            if (
                                                getattr(step, "tool_name", None)
                                                == "__orch_meta"
                                            ):
                                                try:
                                                    _orch_data = json.loads(
                                                        step.content
                                                    )
                                                    yield _sse_data(
                                                        {"orchestration": _orch_data}
                                                    )
                                                except Exception:
                                                    yield _sse_thinking(step)
                                            else:
                                                yield _sse_thinking(step)
                                elif key == "completed_tool_calls" and isinstance(
                                    value, list
                                ):
                                    accumulated_state["completed_tool_calls"] = (
                                        accumulated_state.get(
                                            "completed_tool_calls", []
                                        )
                                        + value
                                    )
                                    # #15: Emit tool progress events (retry path)
                                    for rec in value:
                                        if hasattr(rec, "tool_name"):
                                            yield _sse_tool_progress(
                                                rec.tool_name,
                                                rec.status or "success",
                                                rec.duration_ms,
                                            )
                                            # P0 FIX: Also push results in retry path
                                            if rec.status == "success" and rec.result:
                                                yield _sse_tool_result(
                                                    rec.tool_name,
                                                    rec.result,
                                                    rec.status,
                                                )
                                else:
                                    accumulated_state[key] = value
            except Exception as retry_err:
                logger.error(
                    f"[Stream] Retry with fresh thread also failed: {retry_err}",
                    exc_info=True,
                )
                async for chunk in _emit_error_and_cleanup(
                    all_thinking_steps, tracer, _trace_id, retry_err
                ):
                    yield chunk
                return
        else:
            logger.error(f"[Stream] Agent graph execution failed: {e}", exc_info=True)
            async for chunk in _emit_error_and_cleanup(
                all_thinking_steps, tracer, _trace_id, e
            ):
                yield chunk
            return

    # ── 6. Stream the final response ──
    final_response = accumulated_state.get("final_response", "")

    # Fallback: if final_response is empty, try to extract from last AI message
    if not final_response:
        from langchain_core.messages import AIMessage as _AIMsg

        for msg in reversed(accumulated_state.get("messages", [])):
            if isinstance(msg, _AIMsg) and msg.content:
                final_response = extract_clean_content(msg)
                break

    # Belt-and-suspenders: strip any remaining reasoning artifacts
    if final_response:
        final_response = strip_think_tags(final_response)

        # P1: Validate gen-ui blocks in final response before streaming
        if "```gen-ui" in final_response:
            from app.agent.sse_protocol import validate_genui_blocks

            final_response = validate_genui_blocks(final_response)

    # Last resort fallback — provide actionable guidance instead of generic error
    if not final_response:
        complexity = accumulated_state.get("complexity")
        intent = accumulated_state.get("intent_summary", "")
        logger.warning(
            "[Stream] No final_response found in accumulated state "
            "(complexity=%s intent=%s model=%s)",
            complexity,
            intent,
            accumulated_state.get("selected_model", "?"),
        )
        # If the user asked for long-form content, suggest shorter or split approach
        if (
            complexity
            and complexity.value in ("complex", "critical")
            and any(
                kw in intent for kw in ("写作", "创作", "软文", "文章", "报告", "方案")
            )
        ):
            final_response = (
                "抱歉，这次内容生成未能成功完成。可能是因为内容篇幅较大或模型处理超时。\n\n"
                "建议您：\n"
                "1. 尝试重新发送请求（系统会自动优化上下文）\n"
                "2. 拆分为多次请求，例如先写大纲，再逐节展开"
            )
        else:
            final_response = "抱歉，处理您的请求时遇到了问题。请稍后重试。"

    # Stream the final response content
    # Skip if the respond node already streamed the same content to the user.
    # streamed_plan_content is True only when respond-node tokens were yielded.
    # Also skip if confirmation is pending — the confirmation card will display
    # the message, so streaming it as text would cause duplicate display.
    has_confirmation_pending = not system_confirmed and any(
        getattr(tc, "status", None) == "blocked"
        for tc in accumulated_state.get("completed_tool_calls", [])
    )
    already_streamed = (
        streamed_plan_content
        and final_response
        and final_response.strip() == streamed_plan_text.strip()
    )

    # Diagnostic logging for HITL confirmation flow
    logger.info(
        f"[Stream] Post-loop: system_confirmed={system_confirmed}, "
        f"has_confirmation_pending={has_confirmation_pending}, "
        f"already_streamed={already_streamed}, "
        f"final_response_len={len(final_response)}, "
        f"streamed_plan_content={streamed_plan_content}, "
        f"completed_tool_calls_count={len(accumulated_state.get('completed_tool_calls', []))}"
    )

    if final_response and not already_streamed and not has_confirmation_pending:
        yield _sse_status("")  # Clear status
        # Stream word by word for smooth UX
        chunks = _chunk_text(final_response)
        for chunk in chunks:
            yield _sse_content(chunk)
            await asyncio.sleep(0.01)
    else:
        logger.warning(
            f"[Stream] Skipped streaming final_response! "
            f"final_response={'yes' if final_response else 'EMPTY'}, "
            f"already_streamed={already_streamed}, "
            f"has_confirmation_pending={has_confirmation_pending}"
        )

    # ── 7. Emit thinking chain completion ──
    from app.core.ai_metrics import record_llm_latency

    _graph_elapsed_ms = (time.time() - _graph_start_time) * 1000
    record_llm_latency(agent_config.model, _graph_elapsed_ms)

    yield _sse_data(
        {
            "thinking_chain_complete": True,
            "total_steps": len(all_thinking_steps),
        }
    )

    # ── 7.1 Circuit break event — structured notification for frontend ──
    _cb_reason = accumulated_state.get("circuit_break_reason")
    if _cb_reason:
        yield _sse_circuit_break(_cb_reason)

    # ── 7.5 HITL: Emit confirmation request if any tools were blocked ──
    # Skip when system_confirmed=True — old blocked records from the first
    # attempt are still in accumulated state but the user already confirmed.
    blocked_calls = (
        []
        if system_confirmed
        else [
            tc
            for tc in accumulated_state.get("completed_tool_calls", [])
            if getattr(tc, "status", None) == "blocked"
        ]
    )
    if blocked_calls:
        # Mark that we have confirmation events — used to suppress cache below
        has_confirmation = True
        for tc in blocked_calls:
            yield _sse_confirmation(
                tool_name=tc.tool_name,
                message=tc.result or "此操作需要您的确认才能执行。",
                args=tc.tool_args,
                confirmation_type=getattr(tc, "confirmation_type", ""),
            )
            # HITL: Persist confirmation to DB for async approval
            try:
                from app.services.hitl_service import persist_confirmation

                asyncio.create_task(
                    persist_confirmation(
                        org_id=agent_config.org_id or "",
                        user_id=user_id,
                        session_id=session_id or "default",
                        thread_id=scoped_thread_id,
                        tool_name=tc.tool_name,
                        tool_args=tc.tool_args or {},
                        tool_call_id=getattr(tc, "tool_call_id", ""),
                        confirmation_type=getattr(tc, "confirmation_type", ""),
                        message=tc.result or "",
                    )
                )
            except Exception:
                pass  # non-fatal
    else:
        has_confirmation = False

    # ── 7.6 P1-7: Emit ask_user events for agent proactive questioning ──
    ask_user_calls = [
        tc
        for tc in accumulated_state.get("completed_tool_calls", [])
        if getattr(tc, "status", None) == "ask_user"
    ]
    if ask_user_calls:
        for tc in ask_user_calls:
            args = tc.tool_args or {}
            yield _sse_ask_user(
                question=args.get("question", tc.result or ""),
                options=args.get("options"),
                context=args.get("context", ""),
                fields=args.get("fields"),
            )

    # ── 8. Token tracking ──
    total_in = accumulated_state.get("total_input_tokens", 0) or input_tokens
    # Use the tier-selected model (from router) for accurate tracking, not the base config model
    actual_model = accumulated_state.get("selected_model") or agent_config.model

    total_out = accumulated_state.get(
        "total_output_tokens", 0
    ) or token_counter.count_tokens(final_response, actual_model)

    try:
        await record_completion(user_id, total_in, total_out, actual_model)
    except Exception as e:
        logger.warning(f"[Stream] Token recording failed: {e}", exc_info=True)

    # ── 8.1 G5: Record usage to token budget manager ──
    try:
        from app.core.token_budget import token_budget_manager

        await token_budget_manager.record_usage(
            session_id=session_id or "default",
            user_id=user_id,
            tenant_id=agent_config.org_id,
            input_tokens=total_in,
            output_tokens=total_out,
            model=actual_model,
        )
    except Exception as e:
        logger.warning(f"[Stream] Token budget recording failed: {e}")

    # ── 8.5 Emit quota info for frontend quota display ──
    try:
        summary = usage_tracker.get_usage_summary(user_id)
        yield _sse_data(
            {
                "quota": {
                    "tokens_used": summary.get("tokens_used", 0),
                    "tokens_limit": summary.get("tokens_limit", 0),
                    "tokens_remaining": summary.get("tokens_remaining", 0),
                    "requests": summary.get("requests", 0),
                    "requests_limit": summary.get("requests_limit", 0),
                    "cost_usd": summary.get("cost_usd", 0),
                }
            }
        )
    except Exception as e:
        logger.error(f"[Stream] Quota emission failed: {e}")

    # ── 9. Persist to DB and cache (fire-and-forget) ──
    # Extract tool call data for knowledge graph and pattern learning
    raw_tool_calls = []
    for tc in accumulated_state.get("completed_tool_calls", []):
        raw_tool_calls.append(
            {
                "tool_name": getattr(tc, "tool_name", "") or "",
                "result": (getattr(tc, "result", "") or "")[:500],
                "tool_args": getattr(tc, "tool_args", {}) or {},
            }
        )

    # Calculate per-conversation cost
    def _calc_cost_usd(mdl: str, in_tok: int, out_tok: int) -> float:
        try:
            from app.core.model_pricing import estimate_cost as _est

            return _est(in_tok, out_tok, mdl)
        except Exception:
            return 0.0

    _t = asyncio.create_task(
        persist_result(
            user_id=user_id,
            session_id=session_id or "default",
            user_message=last_user_content,
            assistant_response=final_response,
            agent_name=agent_name,
            metadata={
                "model": agent_config.model,
                "thinking_steps": len(all_thinking_steps),
                "duration_ms": int((time.time() - start_time) * 1000),
                "total_tokens": total_in + total_out,
                "input_tokens": total_in,
                "output_tokens": total_out,
                "cost_usd": _calc_cost_usd(actual_model, total_in, total_out),
                "confidence_score": accumulated_state.get("confidence_score", 0.0),
                "complexity": str(accumulated_state.get("complexity", "moderate")),
                "plan": accumulated_state.get("plan", "")[:500],
            },
            db_client=db_client,
            org_id=agent_config.org_id,
            completed_tool_calls=raw_tool_calls or None,
            skip_cache=has_confirmation or bool(accumulated_state.get("error")),
            skip_semantic=False,  # SIMPLE queries are ideal cache candidates
        )
    )
    _background_tasks.add(_t)
    _t.add_done_callback(_background_tasks.discard)

    # Structured metrics log for observability
    duration_ms = int((time.time() - start_time) * 1000)
    completed_tools = accumulated_state.get("completed_tool_calls", [])
    logger.info(
        "[AgentMetrics] session=%s complexity=%s tools=%d cache_hit=%s nodes=%d duration=%dms tokens=%d",
        session_id or "default",
        str(accumulated_state.get("complexity", "unknown")),
        cached_response is not None,
        len(completed_tools),
        len(all_thinking_steps),
        duration_ms,
        total_in + total_out,
    )

    # SLO: Record end-to-end duration by complexity tier
    from app.core.ai_metrics import check_agent_success_rate, record_agent_e2e

    _tier = str(accumulated_state.get("complexity", "moderate"))
    _success = not accumulated_state.get("error")
    record_agent_e2e(_tier, duration_ms, _success)
    check_agent_success_rate(_success)

    try:
        from app.services.agent_cost_attribution import build_cost_attribution
        from app.services.agent_run_observability import agent_run_observer

        _run_cost = _calc_cost_usd(actual_model, total_in, total_out)
        _prompt_snapshot = accumulated_state.get("prompt_snapshot")
        _context_ledger = accumulated_state.get("context_ledger")
        _cost_attribution = build_cost_attribution(
            prompt_snapshot=_prompt_snapshot,
            context_ledger=_context_ledger,
            input_tokens=total_in,
            output_tokens=total_out,
            cost_usd=_run_cost,
        )

        await agent_run_observer.finish_run(
            run_id=accumulated_state.get("agent_run_id"),
            status="completed" if _success else "error",
            error=accumulated_state.get("error"),
            final_response=final_response,
            input_tokens=total_in,
            output_tokens=total_out,
            cost_usd=_run_cost,
            duration_ms=duration_ms,
            metadata={
                "complexity": _tier,
                "model": actual_model,
                "tool_count": len(completed_tools),
                "thinking_steps": len(all_thinking_steps),
                "prompt_snapshot": _prompt_snapshot,
                "context_ledger": _context_ledger,
                "cost_attribution": _cost_attribution,
            },
        )
    except Exception:
        logger.debug("[Stream] agent_runs finish skipped", exc_info=True)

    # ── 10. Finalize trace ──
    if tracer:
        tracer.log_end(total_tokens=total_in + total_out)

    # P3: End agent trace and persist to DB
    try:
        _trace = agent_trace_service.get_trace(_trace_id)
        if _trace:
            _trace.metadata.update(
                {
                    "prompt_snapshot": accumulated_state.get("prompt_snapshot"),
                    "context_ledger": accumulated_state.get("context_ledger"),
                }
            )
        agent_trace_service.end_trace(
            _trace_id,
            TraceStatus.COMPLETED,
            final_response=(final_response or "")[:500],
            db=db_client or supabase,
        )
    except Exception:
        logger.error("[Stream] Failed to end agent trace", exc_info=True)

    # ── P2-13: Generate follow-up suggestions ──
    try:
        if final_response and len(final_response) > 30:
            from langchain_core.messages import HumanMessage as _HMsg
            from langchain_core.messages import SystemMessage as _SMsg
            from langchain_openai import ChatOpenAI as _ChatOAI

            _fu_llm = _ChatOAI(
                model=agent_config.mini_model,
                api_key=agent_config.api_key,
                base_url=agent_config.base_url,
                temperature=0.7,
                timeout=10.0,
            )
            _fu_resp = await _fu_llm.ainvoke(
                [
                    _SMsg(
                        content="基于AI的回复，生成3条用户可能继续追问的简短问题。每条一行，不带序号。"
                    ),
                    _HMsg(
                        content=f"用户问: {last_user_content[:200]}\nAI回复: {final_response[:500]}"
                    ),
                ]
            )
            _fu_lines = [
                s.strip() for s in _fu_resp.content.strip().split("\n") if s.strip()
            ][:3]
            if _fu_lines:
                yield _sse_data({"follow_up_suggestions": _fu_lines})
    except Exception as e:
        logger.error(f"[Stream] Follow-up suggestions failed: {e}")

    yield "data: [DONE]\n\n"
