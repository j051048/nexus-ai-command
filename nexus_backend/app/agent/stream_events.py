"""
Stream Event Processing — Extracted from stream.py to eliminate code duplication.
P0 Audit Fix: The main event loop and retry path in stream.py shared ~200 lines
of near-identical event handling code. This module extracts the common logic into
reusable async generators, following DRY principle.

Usage in stream.py:
    from app.agent.stream_events import process_graph_events
"""

import json
import logging
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


def _filter_think_content(content: str) -> str:
    """Remove <think>...</think> blocks from a single chunk (complete blocks only)."""
    import re
    return re.sub(r"<think>.*?</think>\n?", "", content, flags=re.DOTALL)


class ThinkTagTracker:
    """Stateful tracker for <think>...</think> blocks that may span multiple chunks."""

    __slots__ = ("_inside",)

    def __init__(self):
        self._inside = False

    def filter(self, content: str) -> str:
        """Filter content, tracking think state across chunks. Returns filtered text."""
        if not content:
            return ""

        if self._inside:
            if "</think>" in content:
                self._inside = False
                return content.split("</think>", 1)[1].lstrip("\n")
            return ""

        if "<think>" in content:
            before = content.split("<think>", 1)[0]
            remainder = content.split("<think>", 1)[1]
            if "</think>" in remainder:
                after = remainder.split("</think>", 1)[1].lstrip("\n")
                return before + after
            else:
                self._inside = True
                return before

        return content


async def process_stream_event(
    event: dict,
    accumulated_state: dict,
    all_thinking_steps: list,
    think_tracker: ThinkTagTracker,
    streamed_chars: int,
    output_token_budget: int,
    budget_breached: bool,
    streamed_plan_content: bool,
    streamed_plan_text: str,
    *,
    _is_mutation_fast_path_fn,
    _sse_content_fn,
    _sse_keepalive_fn,
    _sse_data_fn,
    _sse_thinking_fn,
    _sse_status_fn,
    _sse_tool_progress_fn,
    _sse_tool_result_fn,
    thinking_step_cls,
    agent_phase_cls,
    user_id: str = "",
    session_id: str = "",
) -> AsyncIterator[tuple[str, int, bool, bool, str]]:
    """
    Process a single graph stream event and yield SSE chunks.

    Yields tuples of:
        (sse_chunk, updated_streamed_chars, updated_budget_breached,
         updated_streamed_plan_content, updated_streamed_plan_text)

    Returns None as sse_chunk for state-only updates (no SSE emission).

    This function is designed to be called from both the primary and retry
    event loops in stream.py, eliminating the code duplication identified
    in the P0 audit.
    """
    kind = event.get("event")

    # ── A. Content Streaming ──
    if kind == "on_chat_model_stream":
        node_name = event.get("metadata", {}).get("langgraph_node")
        chunk = event["data"]["chunk"]
        content = chunk.content

        # Skip reasoning_content from reasoning models
        chunk_kwargs = getattr(chunk, "additional_kwargs", {}) or {}
        if chunk_kwargs.get("reasoning_content"):
            return

        if content and node_name == "respond":
            emit = think_tracker.filter(content)
            if emit:
                yield (_sse_content_fn(emit), streamed_chars + len(emit),
                       budget_breached, True, streamed_plan_text + (emit or ""))
                streamed_chars += len(emit)
                streamed_plan_content = True
            else:
                yield (None, streamed_chars, budget_breached,
                       streamed_plan_content, streamed_plan_text + (emit or ""))
            streamed_plan_text += emit or ""

        elif content and node_name == "plan":
            if _is_mutation_fast_path_fn(accumulated_state):
                plan_filtered = _filter_think_content(content)
                if plan_filtered:
                    yield (_sse_content_fn(plan_filtered), streamed_chars + len(plan_filtered),
                           budget_breached, True, streamed_plan_text + content)
                    streamed_chars += len(plan_filtered)
                    streamed_plan_content = True
                else:
                    yield (None, streamed_chars, budget_breached,
                           streamed_plan_content, streamed_plan_text + content)
            else:
                yield (None, streamed_chars, budget_breached,
                       streamed_plan_content, streamed_plan_text + content)
            streamed_plan_text += content

        # Mid-flight budget check
        if not budget_breached and streamed_chars // 3 > output_token_budget:
            budget_breached = True
            logger.warning(
                "[Stream] Output token budget breached: ~%d tokens (chars=%d, limit=%d) user=%s session=%s",
                streamed_chars // 3, streamed_chars, output_token_budget, user_id, session_id,
            )
            yield (_sse_data_fn({
                "budget_breaker": {
                    "reason": "output_token_limit",
                    "estimated_tokens": streamed_chars // 3,
                    "limit": output_token_budget,
                    "message": "回复已达到输出 token 上限，已自动截断。",
                }
            }), streamed_chars, True, streamed_plan_content, streamed_plan_text)
            yield (_sse_content_fn("\n\n⚠️ 回复已达到输出上限，已自动截断。"),
                   streamed_chars, True, streamed_plan_content, streamed_plan_text)

    # ── B. State Updates ──
    elif kind == "on_chain_end":
        data = event.get("data", {})
        output = data.get("output")

        if isinstance(output, dict) and any(
            k in output for k in ("current_phase", "thinking_steps", "messages")
        ):
            for key, value in output.items():
                if key == "messages" and isinstance(value, list):
                    existing = accumulated_state.get("messages", [])
                    accumulated_state["messages"] = existing + value

                elif key == "thinking_steps" and isinstance(value, list):
                    for step in value:
                        if isinstance(step, thinking_step_cls):
                            all_thinking_steps.append(step)
                            if getattr(step, "tool_name", None) == "__orch_meta":
                                try:
                                    _orch_data = json.loads(step.content)
                                    yield (_sse_data_fn({"orchestration": _orch_data}),
                                           streamed_chars, budget_breached,
                                           streamed_plan_content, streamed_plan_text)
                                except Exception:
                                    yield (_sse_thinking_fn(step), streamed_chars,
                                           budget_breached, streamed_plan_content, streamed_plan_text)
                            else:
                                yield (_sse_thinking_fn(step), streamed_chars,
                                       budget_breached, streamed_plan_content, streamed_plan_text)

                elif key == "completed_tool_calls" and isinstance(value, list):
                    existing = accumulated_state.get("completed_tool_calls", [])
                    accumulated_state["completed_tool_calls"] = existing + value
                    for rec in value:
                        if hasattr(rec, "tool_name"):
                            yield (_sse_tool_progress_fn(rec.tool_name, rec.status or "success", rec.duration_ms),
                                   streamed_chars, budget_breached, streamed_plan_content, streamed_plan_text)
                            if rec.status == "success" and rec.result:
                                yield (_sse_tool_result_fn(rec.tool_name, rec.result, rec.status),
                                       streamed_chars, budget_breached, streamed_plan_content, streamed_plan_text)
                else:
                    accumulated_state[key] = value

            # Phase status updates
            phase = output.get("current_phase")
            if phase:
                iteration = accumulated_state.get("iteration", 0)
                status_map = {
                    agent_phase_cls.ROUTING: "正在分析意图...",
                    agent_phase_cls.PLANNING: "正在规划...",
                    agent_phase_cls.EXECUTING: "正在执行工具...",
                    agent_phase_cls.REFLECTING: "正在验证结果...",
                    agent_phase_cls.CRITIQUING: "正在质量评审...",
                    agent_phase_cls.RESPONDING: "正在生成回复...",
                }
                if phase == agent_phase_cls.REFLECTING and iteration >= 2:
                    yield (_sse_status_fn(f"正在深度验证... (第{iteration}轮)"),
                           streamed_chars, budget_breached, streamed_plan_content, streamed_plan_text)
                elif phase == agent_phase_cls.PLANNING and iteration >= 3:
                    yield (_sse_status_fn(f"正在重新规划... (第{iteration}轮)"),
                           streamed_chars, budget_breached, streamed_plan_content, streamed_plan_text)
                else:
                    status_text = status_map.get(phase)
                    if status_text:
                        yield (_sse_status_fn(status_text), streamed_chars,
                               budget_breached, streamed_plan_content, streamed_plan_text)
