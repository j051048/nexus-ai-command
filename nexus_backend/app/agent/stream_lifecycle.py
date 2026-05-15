"""Lifecycle helpers for the agent SSE stream.

Kept separate from ``stream.py`` so the main streaming adapter can focus on
graph orchestration instead of error, disconnect, and model-output cleanup.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncGenerator
from typing import Any

from app.agent.sse_protocol import _sse_content, _sse_data
from app.agent.think_tags import strip_think_tags
from app.services.agent_trace_service import TraceStatus, agent_trace_service

logger = logging.getLogger(__name__)


async def emit_error_and_cleanup(
    all_thinking_steps: list,
    tracer: Any | None,
    trace_id: str,
    error: Exception,
) -> AsyncGenerator[str, None]:
    """Yield the standard terminal error SSE sequence and close tracing."""
    yield _sse_content(
        "\n\n处理请求时发生内部错误，请稍后重试。如问题持续，请联系管理员。"
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


async def cleanup_on_disconnect(
    throttle_ctx: Any,
    trace_id: str,
    tracer: Any | None = None,
    log_msg: str = "",
) -> None:
    """Release tenant throttle and end trace on client disconnect."""
    await throttle_ctx.__aexit__(None, None, None)
    if log_msg:
        logger.info(log_msg)
    if tracer:
        tracer.log_end(total_tokens=0)
    with contextlib.suppress(Exception):
        agent_trace_service.end_trace(trace_id, TraceStatus.CANCELLED)


def filter_think_content(content: str) -> str:
    """Strip reasoning-only ``<think>`` tags from model output chunks."""
    if "<think>" in content or "</think>" in content:
        return strip_think_tags(content)
    return content
