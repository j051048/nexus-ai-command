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

    _otel_available = True
    logger.info("OpenTelemetry AI metrics initialised (meter: nexus-ai-metrics)")

except ImportError:
    logger.info(
        "opentelemetry.metrics not available -- AI metrics will be no-ops"
    )
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
    _hallucination_detected.add(
        1, attributes={"detection_layer": detection_layer}
    )


def record_cache_event(hit: bool) -> None:
    """Record a cache hit or miss.

    Args:
        hit: ``True`` for a cache hit, ``False`` for a miss.
    """
    if not _otel_available:
        return
    if hit:
        _cache_hit.add(1)
    else:
        _cache_miss.add(1)


def record_rag_retrieval(duration_ms: float, source: str = "default") -> None:
    """Record the duration of a RAG retrieval operation.

    Args:
        duration_ms: Wall-clock duration in milliseconds.
        source: Label for the retrieval source (e.g. ``"pinecone"``, ``"supabase"``).
    """
    if not _otel_available:
        return
    _rag_retrieval_duration.record(
        duration_ms, attributes={"source": source}
    )


def record_agent_delegation(
    from_agent: str,
    to_agent: str,
) -> None:
    """Record an agent-to-agent delegation event.

    Args:
        from_agent: Name of the delegating agent.
        to_agent: Name of the target agent.
    """
    if not _otel_available:
        return
    _agent_delegation.add(
        1, attributes={"from_agent": from_agent, "to_agent": to_agent}
    )
