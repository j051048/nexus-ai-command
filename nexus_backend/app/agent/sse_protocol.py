"""SSE protocol formatting utilities for the streaming adapter.

Extracted from stream.py to isolate the SSE wire format from business logic.
All functions produce SSE-formatted strings ready to be yielded by an
AsyncGenerator[str, None] endpoint.
"""

import asyncio
import json
from typing import Any

from app.agent.state import ThinkingStep

# SSE keepalive interval (seconds).  Reverse proxies like CloudFlare (100s)
# and Nginx (60s default proxy_read_timeout) drop idle connections.  Sending
# a harmless SSE comment every 15s prevents that.
SSE_KEEPALIVE_INTERVAL = 15


async def _with_keepalive(event_stream, interval: int = SSE_KEEPALIVE_INTERVAL):
    """Wrap an async event stream with periodic keepalive signals.

    Yields the original events unchanged.  When no event arrives within
    *interval* seconds, yields ``None`` so the caller can emit an SSE
    keepalive comment and keep the HTTP connection alive.
    """
    aiter = event_stream.__aiter__()
    fetch_task = None

    async def _get_next():
        return await anext(aiter)

    try:
        while True:
            if fetch_task is None:
                fetch_task = asyncio.create_task(_get_next())

            done, pending = await asyncio.wait([fetch_task], timeout=interval)

            if done:
                try:
                    event = fetch_task.result()
                    fetch_task = None
                    yield event
                except StopAsyncIteration:
                    break
            else:
                yield None
    finally:
        if fetch_task and not fetch_task.done():
            fetch_task.cancel()


def _sse_keepalive() -> str:
    """SSE comment that keeps the connection alive through reverse proxies."""
    return ": keepalive\n\n"


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


def _sse_confirmation(tool_name: str, message: str, args: dict, confirmation_type: str = "") -> str:
    """Emit a confirmation request for a blocked tool call."""
    return _sse_data(
        {
            "confirmation_required": {
                "tool_name": tool_name,
                "message": message,
                "args": {k: v for k, v in args.items() if k != "api_key"},  # Strip secrets
                "modifiable": True,  # P1-7: Allow user to edit args before confirming
                "confirmation_type": confirmation_type,  # P0-6: tiered confirmation
            }
        }
    )


def _sse_ask_user(question: str, options: list[str] | None = None, context: str = "", fields: list | None = None) -> str:
    """P1-7: Emit an ask_user event for the agent to proactively ask the user."""
    return _sse_data(
        {
            "ask_user": {
                "question": question,
                "options": options or [],
                "context": context,
                "fields": fields,
            }
        }
    )


_CIRCUIT_BREAK_SUGGESTIONS = {
    "loop_detected": "AI 检测到重复操作模式，请尝试用更具体的描述重新提问。",
    "max_iterations": "本次推理已达到最大步数限制，请简化问题或拆分为多个小任务。",
}


def _sse_tool_progress(tool_name: str, status: str, duration_ms: int | None = None) -> str:
    """#15: Emit tool execution progress for frontend progress bar."""
    return _sse_data({
        "tool_progress": {
            "tool_name": tool_name,
            "status": status,  # running | success | error
            "duration_ms": duration_ms,
        }
    })


def _sse_circuit_break(reason: str) -> str:
    """Emit a circuit break event when the agent hits a safety limit."""
    return _sse_data(
        {
            "circuit_break": {
                "reason": reason,
                "suggestion": _CIRCUIT_BREAK_SUGGESTIONS.get(reason, "请尝试重新描述您的需求。"),
            }
        }
    )


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
