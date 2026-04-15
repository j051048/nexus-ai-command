"""Structured decision logging for agent tracing."""

import logging

from app.services.agent_trace_service import agent_trace_service

logger = logging.getLogger(__name__)


def log_decision(
    trace_id: str | None,
    step_id: str,
    decision: str,
    reasoning: str,
    alternatives: list[str] | None = None,
):
    """Log a structured decision to the agent trace (fire-and-forget, never raises)."""
    if not trace_id:
        return
    try:
        agent_trace_service.add_step(
            trace_id=trace_id,
            step_id=step_id,
            node_type="decision",
            output_data={
                "decision": decision,
                "reasoning": reasoning,
                "alternatives": alternatives or [],
            },
        )
    except Exception as e:
        logger.debug("[Tracing] Decision trace failed (non-blocking): %s", e)
