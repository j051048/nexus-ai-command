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
from collections.abc import AsyncGenerator
from typing import Any

from app.agent.graph import get_agent_graph
from app.agent.memory import persist_result, prepare_initial_state
from app.agent.state import (
    AgentConfig,
    AgentPhase,
    AgentState,
    QueryComplexity,
    ThinkingStep,
)
from app.core.config import settings
from app.core.trace_logger import TraceLogger
from app.services.content_moderation import check_user_input
from app.services.token_service import (
    record_completion,
    token_counter,
    usage_tracker,
    validate_request_tokens,
)

logger = logging.getLogger(__name__)

# Use the singleton agent graph instance
_agent_graph = get_agent_graph()


def _sse_data(payload: Any) -> str:
    """Format a payload as an SSE data line."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_content(text: str) -> str:
    """Format text content in the OpenAI-compatible SSE format."""
    return _sse_data({"choices": [{"delta": {"content": text}}]})


def _sse_thinking(step: ThinkingStep) -> str:
    """Emit a thinking step for the frontend thinking-chain UI."""
    return _sse_data({"thinking_step": step.to_dict()})


def _sse_status(status: str) -> str:
    """Emit a status update."""
    return _sse_data({"status": status})


def _sse_confirmation(tool_name: str, message: str, args: dict) -> str:
    """Emit a confirmation request for a blocked tool call."""
    return _sse_data({
        "confirmation_required": {
            "tool_name": tool_name,
            "message": message,
            "args": {k: v for k, v in args.items() if k != "api_key"},  # Strip secrets
        }
    })


async def run_agent_stream(
    messages: list[dict],
    config: dict,
    user_id: str,
    system_prompt: str,
    tracer: TraceLogger | None = None,
    system_confirmed: bool = False,
    session_id: str | None = None,
    db_client: Any | None = None,
    agent_name: str | None = None,
    user_role: str = "employee",
    org_id: str | None = None,
    # VMD extensions
    scene_code: str | None = None,
    vmd_agent_code: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Main entry point: runs the LangGraph agent and streams SSE events.

    This function is a drop-in replacement for ChatService.stream_response,
    maintaining the same SSE protocol for the frontend.
    """
    start_time = time.time()

    # ── 0. Build AgentConfig with settings ──
    agent_config = AgentConfig(
        user_id=user_id,
        session_id=session_id or "default",
        agent_name=agent_name or "default",
        api_key=config.get("api_key", "") or settings.OPENAI_API_KEY,
        base_url=config.get("base_url", "https://api.openai.com/v1") or settings.AI_BASE_URL,
        model=config.get("model", "gpt-4o") or settings.AI_DEFAULT_MODEL,
        mini_model=config.get("mini_model", "gpt-4o-mini"),
        system_confirmed=system_confirmed,
        user_role=user_role,
        org_id=org_id,
        max_iterations=settings.LANGGRAPH_MAX_ITERATIONS,
        tool_timeout=settings.LANGGRAPH_TOOL_TIMEOUT,
        gather_timeout=settings.LANGGRAPH_GATHER_TIMEOUT,
        enable_rag_inject=settings.LANGGRAPH_ENABLE_RAG_INJECT,
        rag_inject_threshold=settings.LANGGRAPH_RAG_INJECT_THRESHOLD,
        rag_inject_limit=settings.LANGGRAPH_RAG_INJECT_LIMIT,
        reflect_use_llm=settings.LANGGRAPH_REFLECT_USE_LLM,
    )

    # ── 1. Token budget check ──
    await usage_tracker.ensure_loaded(user_id)
    messages_dicts = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]
    is_allowed, input_tokens, reason = validate_request_tokens(messages_dicts, agent_config.model, user_id)
    if not is_allowed:
        yield _sse_content(f"⛔ 请求被拒绝 (超出限制): {reason}")
        yield "data: [DONE]\n\n"
        return

    # ── 2. Input moderation ──
    last_user_content = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_content = msg.get("content", "")
            break

    if last_user_content:
        is_safe, warning = check_user_input(last_user_content)
        if not is_safe:
            yield _sse_content(f"⛔ 安全警告: {warning}")
            yield "data: [DONE]\n\n"
            return

    if tracer:
        tracer.log_start(messages_dicts)

    # ── 3. Prepare initial state via Memory Manager ──
    yield _sse_status("正在思考...")

    prep_result = await prepare_initial_state(
        messages,
        system_prompt,
        agent_config,
        db_client=db_client,
    )
    lc_messages = prep_result["messages"]
    cached_response = prep_result["cached_response"]
    rag_context = prep_result["rag_context"]
    rag_sources = prep_result["rag_sources"]

    # Fast path: semantic cache hit
    if cached_response is not None:
        logger.info("[Stream] Semantic cache hit, streaming cached response")
        words = cached_response.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield _sse_content(chunk)
            await asyncio.sleep(0.005)

        try:
            cache_tokens = token_counter.count_tokens(cached_response, agent_config.model)
            await record_completion(user_id, input_tokens, cache_tokens, agent_config.model)
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
        "complexity": QueryComplexity.MODERATE,
        "selected_model": agent_config.model,
        "intent_summary": "",
        "plan": "",
        "requires_tools": False,
        "pending_tool_calls": [],
        "completed_tool_calls": [],
        "reflection": "",
        "is_hallucination": False,
        "needs_replanning": False,
        "confidence_score": 0.0,
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
    }

    # ── 5. Run graph with granular event streaming (astream_events) ──
    accumulated_state: dict[str, Any] = dict(initial_state)
    all_thinking_steps: list[ThinkingStep] = []
    streamed_plan_content = False  # Track whether plan tokens were already streamed
    streamed_plan_text = ""  # Track what was streamed during plan phase

    client_disconnected = False
    try:
        # P1 Security: Prefix thread_id with org_id to prevent cross-tenant
        # state leakage via the LangGraph checkpointer.
        scoped_thread_id = f"{agent_config.org_id or 'default'}::{agent_config.session_id}"

        async for event in _agent_graph.astream_events(
            initial_state,
            thread_id=scoped_thread_id,
            config={
                "configurable": {
                    "trace_logger": tracer,
                },
            },
            version="v2",
        ):
            kind = event.get("event")

            # A. Continuous Token Streaming
            if kind == "on_chat_model_stream":
                node_name = event.get("metadata", {}).get("langgraph_node")
                content = event["data"]["chunk"].content
                if content and node_name == "respond":
                    # Only stream the final "respond" node tokens to the user.
                    # Plan tokens are NOT streamed directly because reflect/replan
                    # cycles would cause the user to see multiple drafts.
                    yield _sse_content(content)
                    streamed_plan_content = True
                    streamed_plan_text += content
                elif content and node_name == "plan":
                    # Accumulate plan text silently; it will be used for
                    # final_response dedup check but not shown to the user
                    # until the agent decides it's the definitive answer.
                    streamed_plan_text += content

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
                                    yield _sse_thinking(step)
                        elif key == "completed_tool_calls" and isinstance(value, list):
                            existing = accumulated_state.get("completed_tool_calls", [])
                            accumulated_state["completed_tool_calls"] = existing + value
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

    except asyncio.CancelledError:
        # Client disconnected (e.g. user clicked "Stop generating")
        client_disconnected = True
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"[Stream] Client disconnected after {duration_ms}ms "
            f"(user={user_id}, session={session_id})"
        )
        if tracer:
            tracer.log_end(total_tokens=0)
        return

    except GeneratorExit:
        # Generator closed by framework on client disconnect
        client_disconnected = True
        logger.info(f"[Stream] Generator closed (user={user_id})")
        return

    except Exception as e:
        logger.error(f"[Stream] Agent graph execution failed: {e}", exc_info=True)
        # P1 Security: Do not expose internal error details to the client
        yield _sse_content("\n\n⚠️ 处理请求时发生内部错误，请稍后重试。如问题持续，请联系管理员。")
        yield _sse_data({"thinking_chain_complete": True, "total_steps": len(all_thinking_steps)})
        yield "data: [DONE]\n\n"
        if tracer:
            tracer.log_error(str(e))
            tracer.log_end()
        return

    # ── 6. Stream the final response ──
    final_response = accumulated_state.get("final_response", "")

    # Fallback: if final_response is empty, try to extract from last AI message
    if not final_response:
        from langchain_core.messages import AIMessage as _AIMsg

        for msg in reversed(accumulated_state.get("messages", [])):
            if isinstance(msg, _AIMsg) and msg.content:
                final_response = msg.content
                break

    # Last resort fallback
    if not final_response:
        logger.warning("[Stream] No final_response found in accumulated state")
        final_response = "抱歉，处理您的请求时遇到了问题。请稍后重试。"

    # Stream the final response content
    # Skip if the respond node already streamed the same content to the user.
    # streamed_plan_content is True only when respond-node tokens were yielded.
    already_streamed = (
        streamed_plan_content
        and final_response
        and final_response.strip() == streamed_plan_text.strip()
    )
    if final_response and not already_streamed:
        yield _sse_status("")  # Clear status
        # Stream word by word for smooth UX
        chunks = _chunk_text(final_response)
        for chunk in chunks:
            yield _sse_content(chunk)
            await asyncio.sleep(0.01)

    # ── 7. Emit thinking chain completion ──
    yield _sse_data(
        {
            "thinking_chain_complete": True,
            "total_steps": len(all_thinking_steps),
        }
    )

    # ── 7.5 HITL: Emit confirmation request if any tools were blocked ──
    blocked_calls = [
        tc for tc in accumulated_state.get("completed_tool_calls", [])
        if getattr(tc, "status", None) == "blocked"
    ]
    if blocked_calls:
        for tc in blocked_calls:
            yield _sse_confirmation(
                tool_name=tc.tool_name,
                message=tc.result or "此操作需要您的确认才能执行。",
                args=tc.tool_args,
            )

    # ── 8. Token tracking ──
    total_in = accumulated_state.get("total_input_tokens", 0) or input_tokens
    total_out = accumulated_state.get("total_output_tokens", 0) or token_counter.count_tokens(
        final_response, agent_config.model
    )

    try:
        await record_completion(user_id, total_in, total_out, agent_config.model)
    except Exception as e:
        logger.warning(f"[Stream] Token recording failed: {e}", exc_info=True)

    # ── 8.5 Emit quota info for frontend quota display ──
    try:
        summary = usage_tracker.get_usage_summary(user_id)
        yield _sse_data({
            "quota": {
                "tokens_used": summary.get("tokens_used", 0),
                "tokens_limit": summary.get("tokens_limit", 0),
                "tokens_remaining": summary.get("tokens_remaining", 0),
                "requests": summary.get("requests", 0),
                "requests_limit": summary.get("requests_limit", 0),
                "cost_usd": summary.get("cost_usd", 0),
            }
        })
    except Exception as e:
        logger.debug(f"[Stream] Quota emission failed: {e}")

    # ── 9. Persist to DB and cache (fire-and-forget) ──
    # Extract tool call data for knowledge graph and pattern learning
    raw_tool_calls = []
    for tc in accumulated_state.get("completed_tool_calls", []):
        raw_tool_calls.append({
            "tool_name": getattr(tc, "tool_name", "") or "",
            "result": (getattr(tc, "result", "") or "")[:500],
            "tool_args": getattr(tc, "tool_args", {}) or {},
        })

    asyncio.create_task(
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
            },
            db_client=db_client,
            org_id=agent_config.org_id,
            completed_tool_calls=raw_tool_calls or None,
        )
    )

    # ── 10. Finalize trace ──
    if tracer:
        tracer.log_end(total_tokens=total_in + total_out)

    yield "data: [DONE]\n\n"


def _chunk_text(text: str, chunk_size: int = 4) -> list[str]:
    """
    Split text into small chunks for smooth streaming.
    Respects word/character boundaries for Chinese and English.
    """
    if not text:
        return []

    chunks = []
    current = ""
    for char in text:
        current += char
        # Emit at natural boundaries
        if len(current) >= chunk_size or char in ("\n", "。", "！", "？", ".", "!", "?"):
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks
