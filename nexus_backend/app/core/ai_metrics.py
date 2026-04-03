"""
AI-Specific OpenTelemetry Metrics.

Provides lightweight wrappers around OpenTelemetry metric instruments that are
relevant to the Nexus AI pipeline: LLM latency, tool execution, hallucination
detection, RAG retrieval, and cache performance.

If the ``opentelemetry`` package is not installed, every helper function
degrades to a no-op so callers never need to guard imports.

Usage::

    from app.core.ai_metrics import record_llm_latency, record_tool_execution

    record_llm_latency(model="gpt-4o", duration_ms=342.1)
    record_tool_execution(tool_name="KnowledgeBaseTool", success=True, duration_ms=58.7)
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Try to import OpenTelemetry metrics; fall back to stubs if unavailable
# ---------------------------------------------------------------------------

_otel_available = False

try:
    from opentelemetry import metrics

    _meter = metrics.get_meter("nexus-ai-metrics")

    # ── Histograms ────────────────────────────────────────────────────────
    _llm_request_duration = _meter.create_histogram(
        name="llm_request_duration_ms",
        description="Duration of LLM API requests in milliseconds",
        unit="ms",
    )
    _tool_execution_duration = _meter.create_histogram(
        name="tool_execution_duration_ms",
        description="Duration of tool executions in milliseconds",
        unit="ms",
    )
    _rag_retrieval_duration = _meter.create_histogram(
        name="rag_retrieval_duration_ms",
        description="Duration of RAG retrieval operations in milliseconds",
        unit="ms",
    )

    # ── Counters ──────────────────────────────────────────────────────────
    _hallucination_detected = _meter.create_counter(
        name="hallucination_detected_count",
        description="Number of hallucinations detected by grounding checks",
    )
    _tool_success = _meter.create_counter(
        name="tool_success_count",
        description="Number of successful tool executions",
    )
    _tool_failure = _meter.create_counter(
        name="tool_failure_count",
        description="Number of failed tool executions",
    )
    _cache_hit = _meter.create_counter(
        name="cache_hit_count",
        description="Number of cache hits (semantic or key-based)",
    )
    _cache_miss = _meter.create_counter(
        name="cache_miss_count",
        description="Number of cache misses",
    )
    _agent_delegation = _meter.create_counter(
        name="agent_delegation_count",
        description="Number of agent delegation events",
    )

    # ── SLO Metrics (by complexity tier) ──────────────────────────────────
    _agent_e2e_duration = _meter.create_histogram(
        name="agent_e2e_duration_ms",
        description="End-to-end agent response duration in milliseconds (by complexity tier)",
        unit="ms",
    )
    _agent_completion = _meter.create_counter(
        name="agent_completion_count",
        description="Agent completion count (success/error by tier)",
    )

    _otel_available = True
    logger.info("OpenTelemetry AI metrics initialised (meter: nexus-ai-metrics)")

except ImportError:
    logger.info("opentelemetry.metrics not available -- AI metrics will be no-ops")
except Exception as exc:
    logger.warning("Failed to initialise OpenTelemetry AI metrics: %s", exc)


# ---------------------------------------------------------------------------
# Helper functions -- safe to call regardless of OTel availability
# ---------------------------------------------------------------------------


def record_llm_latency(model: str, duration_ms: float) -> None:
    """Record the duration of an LLM API request.

    Args:
        model: The model identifier (e.g. ``"gpt-4o"``).
        duration_ms: Wall-clock duration of the request in milliseconds.
    """
    if not _otel_available:
        return
    _llm_request_duration.record(duration_ms, attributes={"model": model})


def record_tool_execution(
    tool_name: str,
    success: bool,
    duration_ms: float,
) -> None:
    """Record a tool execution event with its outcome and duration.

    Args:
        tool_name: The registry name of the tool.
        success: Whether the execution completed without error.
        duration_ms: Wall-clock duration of the execution in milliseconds.
    """
    if not _otel_available:
        return
    attrs = {"tool_name": tool_name}
    _tool_execution_duration.record(duration_ms, attributes=attrs)
    if success:
        _tool_success.add(1, attributes=attrs)
    else:
        _tool_failure.add(1, attributes=attrs)


def record_hallucination(detection_layer: str) -> None:
    """Increment the hallucination counter.

    Args:
        detection_layer: Identifier of the detection layer that caught the
            hallucination (e.g. ``"grounding_check"``, ``"citation_verify"``).
    """
    if not _otel_available:
        return
    _hallucination_detected.add(1, attributes={"detection_layer": detection_layer})


def record_cache_hit(cache_type: str = "semantic") -> None:
    """Increment the cache hit counter."""
    if not _otel_available:
        return
    _cache_hit.add(1, attributes={"type": cache_type})


def record_cache_miss(cache_type: str = "semantic") -> None:
    """Increment the cache miss counter."""
    if not _otel_available:
        return
    _cache_miss.add(1, attributes={"type": cache_type})


def record_agent_e2e(tier: str, duration_ms: float, success: bool) -> None:
    """Record end-to-end agent response duration by complexity tier.

    Args:
        tier: Complexity tier (economy/balanced/power/flagship).
        duration_ms: Wall-clock duration from request start to response.
        success: Whether the agent completed without error.
    """
    if not _otel_available:
        return
    attrs = {"tier": tier, "status": "success" if success else "error"}
    _agent_e2e_duration.record(duration_ms, attributes=attrs)
    _agent_completion.add(1, attributes=attrs)


# ---------------------------------------------------------------------------
# Tool success rate sliding window alert
# ---------------------------------------------------------------------------

from collections import deque as _deque

_tool_call_window: dict[str, _deque] = {}
_WINDOW_SIZE = 100
_CONSECUTIVE_FAIL_THRESHOLD = 3


def check_tool_alert(tool_name: str, success: bool) -> bool:
    """Track tool call outcome and alert on consecutive failures.

    Returns True if an alert was triggered (last N calls all failed).
    """
    if tool_name not in _tool_call_window:
        _tool_call_window[tool_name] = _deque(maxlen=_WINDOW_SIZE)
    _tool_call_window[tool_name].append(success)

    window = _tool_call_window[tool_name]
    if len(window) < _CONSECUTIVE_FAIL_THRESHOLD:
        return False

    # Check if last N calls all failed
    recent = list(window)[-_CONSECUTIVE_FAIL_THRESHOLD:]
    if not any(recent):  # all False
        logger.warning(
            "[ToolAlert] %s failed %d consecutive times — potential issue",
            tool_name,
            _CONSECUTIVE_FAIL_THRESHOLD,
        )
        return True
    return False


# ---------------------------------------------------------------------------
# Agent success rate sliding window alert (1-hour window)
# ---------------------------------------------------------------------------

import time as _time

_agent_outcomes: _deque = _deque(maxlen=500)  # (timestamp, success: bool)
_AGENT_ALERT_WINDOW_S = 3600  # 1 hour
_AGENT_ALERT_THRESHOLD = 0.80  # alert if success rate < 80%
_AGENT_ALERT_MIN_SAMPLES = 10  # need at least 10 samples to trigger


def check_agent_success_rate(success: bool) -> bool:
    """Track agent outcomes and alert if success rate drops below threshold.

    Returns True if an alert was triggered.
    """
    now = _time.time()
    _agent_outcomes.append((now, success))

    # Trim expired entries
    cutoff = now - _AGENT_ALERT_WINDOW_S
    while _agent_outcomes and _agent_outcomes[0][0] < cutoff:
        _agent_outcomes.popleft()

    if len(_agent_outcomes) < _AGENT_ALERT_MIN_SAMPLES:
        return False

    successes = sum(1 for _, s in _agent_outcomes if s)
    rate = successes / len(_agent_outcomes)

    if rate < _AGENT_ALERT_THRESHOLD:
        logger.warning(
            "[AgentAlert] Success rate %.1f%% (%d/%d) below %.0f%% threshold in last hour",
            rate * 100,
            successes,
            len(_agent_outcomes),
            _AGENT_ALERT_THRESHOLD * 100,
        )
        return True
    return False
