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
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.agent.state import (
    AgentConfig,
    AgentPhase,
    AgentState,
    QueryComplexity,
    ThinkingStep,
)
from app.agent.graph import AgentGraph
from app.agent.memory import prepare_initial_state, persist_result
from app.services.token_service import (
    validate_request_tokens,
    record_completion,
    token_counter,
    usage_tracker,
)
from app.services.content_moderation import check_user_input
from app.core.trace_logger import TraceLogger

logger = logging.getLogger(__name__)

# Singleton agent graph instance
_agent_graph = AgentGraph()


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


async def run_agent_stream(
    messages: List[Dict],
    config: Dict,
    user_id: str,
    system_prompt: str,
    tracer: Optional[TraceLogger] = None,
    system_confirmed: bool = False,
    session_id: Optional[str] = None,
    db_client: Optional[Any] = None,
    agent_name: Optional[str] = None,
    user_role: str = "employee",
) -> AsyncGenerator[str, None]:
    """
    Main entry point: runs the LangGraph agent and streams SSE events.

    This function is a drop-in replacement for ChatService.stream_response,
    maintaining the same SSE protocol for the frontend.
    """
    start_time = time.time()

    # ── 0. Build AgentConfig ──
    agent_config = AgentConfig(
        user_id=user_id,
        session_id=session_id or "default",
        agent_name=agent_name or "default",
        api_key=config.get("api_key", ""),
        base_url=config.get("base_url", "https://api.openai.com/v1"),
        model=config.get("model", "gpt-4o"),
        mini_model=config.get("mini_model", "gpt-4o-mini"),
        system_confirmed=system_confirmed,
        user_role=user_role,
    )

    # ── 1. Token budget check ──
    await usage_tracker.ensure_loaded(user_id)
    messages_dicts = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]
    is_allowed, input_tokens, reason = validate_request_tokens(
        messages_dicts, agent_config.model, user_id
    )
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
        messages, system_prompt, agent_config, db_client=db_client,
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
            logger.warning(f"Failed to record cache tokens: {e}")

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
    }

    # ── 5. Run graph with granular event streaming (astream_events) ──
    accumulated_state: Dict[str, Any] = dict(initial_state)
    all_thinking_steps: List[ThinkingStep] = []
    
    # Track metadata to calculate total usage if node doesn't provide it
    # Note: thread_id is used for checkpointer persistence
    config_run = {"configurable": {"thread_id": agent_config.session_id}, "version": "v2"}

    try:
        async for event in _agent_graph.compiled.astream_events(
            initial_state, 
            config=config_run,
            version="v2"
        ):
            kind = event.get("event")
            
            # A. Continuous Token Streaming (Planning Phase - Task 2)
            if kind == "on_chat_model_stream":
                node_name = event.get("metadata", {}).get("langgraph_node")
                content = event["data"]["chunk"].content
                if content and node_name == "plan":
                    # Stream planning tokens as part of the thinking process
                    yield _sse_content(content)

            # B. State Updates (when a node completes)
            elif kind == "on_chain_end":
                # Check if this is a node completion (LangGraph emits on_chain_end for nodes)
                # Filter for nodes we care about
                data = event.get("data", {})
                output = data.get("output")
                
                # In LangGraph v2 astream_events, node outputs come in on_chain_end 
                # where tags contain 'graph:step:node_name' or similar.
                # Simplified: we look at data['output'] if it's a dict and update state.
                if isinstance(output, dict) and any(k in output for k in ("current_phase", "thinking_steps", "messages")):
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
                        status_map = {
                            AgentPhase.ROUTING: "正在分析意图...",
                            AgentPhase.PLANNING: "正在规划...",
                            AgentPhase.EXECUTING: "正在执行工具...",
                            AgentPhase.REFLECTING: "正在验证结果...",
                            AgentPhase.RESPONDING: "正在生成回复...",
                        }
                        status_text = status_map.get(phase)
                        if status_text:
                            yield _sse_status(status_text)
                            
            # elif kind == "on_custom_event":
            #    ...

    except Exception as e:
        logger.error(f"[Stream] Agent graph execution failed: {e}", exc_info=True)
        yield _sse_content(f"\n\n⚠️ 处理请求时发生错误: {str(e)[:200]}")
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
    if final_response:
        yield _sse_status("")  # Clear status
        # Stream word by word for smooth UX
        chunks = _chunk_text(final_response)
        for chunk in chunks:
            yield _sse_content(chunk)
            await asyncio.sleep(0.01)

    # ── 7. Emit thinking chain completion ──
    yield _sse_data({
        "thinking_chain_complete": True,
        "total_steps": len(all_thinking_steps),
    })

    # ── 8. Token tracking ──
    total_in = accumulated_state.get("total_input_tokens", 0) or input_tokens
    total_out = accumulated_state.get("total_output_tokens", 0) or token_counter.count_tokens(
        final_response, agent_config.model
    )

    try:
        await record_completion(user_id, total_in, total_out, agent_config.model)
    except Exception as e:
        logger.warning(f"[Stream] Token recording failed: {e}")

    # ── 9. Persist to DB and cache (fire-and-forget) ──
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
        )
    )

    # ── 10. Finalize trace ──
    if tracer:
        tracer.log_end(total_tokens=total_in + total_out)

    yield "data: [DONE]\n\n"


def _chunk_text(text: str, chunk_size: int = 4) -> List[str]:
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
        if len(current) >= chunk_size or char in ("\\n", "。", "！", "？", ".", "!", "?"):
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks
