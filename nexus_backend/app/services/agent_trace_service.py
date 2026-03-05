"""
P0 Observability: Agent Trace Service

Implements comprehensive agent execution tracing for debugging and monitoring.
Fixes Issues #26, #27: Agent trajectory tracking and real-time monitoring.
"""

import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TraceStatus(Enum):
    """Status of a trace"""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class NodeType(Enum):
    """Types of agent nodes"""

    ROUTER = "router"
    PLAN = "plan"
    EXECUTE = "execute"
    REFLECT = "reflect"
    RESPOND = "respond"
    ERROR = "error"


@dataclass
class TraceStep:
    """Single step in agent execution"""

    step_id: str
    node_type: str
    timestamp: float
    input_data: dict = field(default_factory=dict)
    output_data: dict = field(default_factory=dict)
    duration_ms: int | None = None
    status: str = "running"
    error: str | None = None
    tokens_used: int = 0
    tool_calls: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentTrace:
    """Complete trace of an agent execution"""

    trace_id: str
    thread_id: str
    user_id: str
    org_id: str | None
    query: str
    status: TraceStatus
    start_time: float
    end_time: float | None = None
    total_duration_ms: int | None = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    steps: list[TraceStep] = field(default_factory=list)
    final_response: str | None = None
    metadata: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "thread_id": self.thread_id,
            "user_id": self.user_id,
            "org_id": self.org_id,
            "query": self.query,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": self.total_duration_ms,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
            "steps": [s.to_dict() for s in self.steps],
            "final_response": self.final_response,
            "metadata": self.metadata,
            "tags": self.tags,
        }


@dataclass
class MetricPoint:
    """Single metric data point"""

    timestamp: float
    metric_name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)


class AgentTraceService:
    """
    P0 Observability: Comprehensive agent tracing and metrics.

    Features:
    - Real-time trace collection
    - Step-by-step execution recording
    - Token/cost tracking
    - Performance metrics
    - Error tracking and debugging
    """

    def __init__(self):
        self._active_traces: dict[str, AgentTrace] = {}
        self._completed_traces: dict[str, AgentTrace] = {}
        self._metrics_buffer: list[MetricPoint] = []
        self._max_completed_traces = 1000

    def start_trace(
        self, trace_id: str, thread_id: str, user_id: str, query: str, org_id: str = None, metadata: dict = None
    ) -> AgentTrace:
        """Start a new trace."""
        trace = AgentTrace(
            trace_id=trace_id,
            thread_id=thread_id,
            user_id=user_id,
            org_id=org_id,
            query=query,
            status=TraceStatus.RUNNING,
            start_time=time.time(),
            metadata=metadata or {},
        )
        self._active_traces[trace_id] = trace
        self._record_metric("trace_started", 1, {"user_id": user_id})
        logger.info(f"Trace started: {trace_id} for user {user_id}")
        return trace

    def add_step(
        self,
        trace_id: str,
        step_id: str,
        node_type: str,
        input_data: dict = None,
        output_data: dict = None,
        status: str = "completed",
        error: str = None,
        tokens_used: int = 0,
        tool_calls: list[dict] = None,
    ) -> TraceStep | None:
        """Add a step to an active trace."""
        trace = self._active_traces.get(trace_id)
        if not trace:
            logger.warning(f"Trace not found: {trace_id}")
            return None

        # Calculate duration from previous step
        duration_ms = None
        if trace.steps:
            prev_step = trace.steps[-1]
            duration_ms = int((time.time() - prev_step.timestamp) * 1000)

        step = TraceStep(
            step_id=step_id,
            node_type=node_type,
            timestamp=time.time(),
            input_data=input_data or {},
            output_data=output_data or {},
            duration_ms=duration_ms,
            status=status,
            error=error,
            tokens_used=tokens_used,
            tool_calls=tool_calls or [],
        )

        trace.steps.append(step)
        trace.total_tokens += tokens_used

        # Record metrics
        self._record_metric(f"step_{node_type}", duration_ms or 0, {"trace_id": trace_id})
        if tokens_used > 0:
            self._record_metric("tokens_used", tokens_used, {"node_type": node_type})

        return step

    def end_trace(
        self,
        trace_id: str,
        status: TraceStatus,
        final_response: str = None,
        error: str = None,
        db=None,
    ) -> AgentTrace | None:
        """End a trace and move to completed. Auto-persists to DB if db is provided."""
        trace = self._active_traces.pop(trace_id, None)
        if not trace:
            return None

        trace.end_time = time.time()
        trace.total_duration_ms = int((trace.end_time - trace.start_time) * 1000)
        trace.status = status
        trace.final_response = final_response

        if error:
            trace.metadata["error"] = error

        # Calculate cost (approximate)
        trace.total_cost_usd = self._calculate_cost(trace.total_tokens)

        # Move to completed
        self._completed_traces[trace_id] = trace
        self._cleanup_old_traces()

        # Record metrics
        self._record_metric("trace_completed", 1, {"status": status.value})
        self._record_metric("trace_duration_ms", trace.total_duration_ms)
        self._record_metric("trace_tokens", trace.total_tokens)
        self._record_metric("trace_cost_usd", trace.total_cost_usd)

        logger.info(f"Trace ended: {trace_id}, status={status.value}, duration={trace.total_duration_ms}ms")

        # P0-5: Auto-persist to DB (fire-and-forget)
        if db:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.persist_trace(trace_id, db=db))
            except RuntimeError:
                # No running loop, skip auto-persist
                logger.debug(f"No event loop for auto-persist of trace {trace_id}")

        return trace

    def get_trace(self, trace_id: str) -> AgentTrace | None:
        """Get a trace by ID."""
        return self._active_traces.get(trace_id) or self._completed_traces.get(trace_id)

    def get_thread_traces(self, thread_id: str) -> list[AgentTrace]:
        """Get all traces for a thread."""
        return [
            t
            for t in list(self._active_traces.values()) + list(self._completed_traces.values())
            if t.thread_id == thread_id
        ]

    def replay_trace(self, trace_id: str) -> dict:
        """Get trace data for replay/debugging."""
        trace = self.get_trace(trace_id)
        if not trace:
            return {"error": "Trace not found"}

        return {
            "trace": trace.to_dict(),
            "replay": [
                {
                    "step": i + 1,
                    "node": step.node_type,
                    "input": step.input_data,
                    "output": step.output_data,
                    "duration_ms": step.duration_ms,
                    "tokens": step.tokens_used,
                    "tools": step.tool_calls,
                }
                for i, step in enumerate(trace.steps)
            ],
        }

    def get_metrics(self, metric_name: str = None, since: float = None) -> list[dict]:
        """Get collected metrics."""
        metrics = self._metrics_buffer
        if metric_name:
            metrics = [m for m in metrics if m.metric_name == metric_name]
        if since:
            metrics = [m for m in metrics if m.timestamp >= since]
        return [
            {"timestamp": m.timestamp, "name": m.metric_name, "value": m.value, "labels": m.labels} for m in metrics
        ]

    def get_stats(self, org_id: str = None, user_id: str = None) -> dict:
        """Get aggregate statistics."""
        traces = list(self._completed_traces.values())

        if org_id:
            traces = [t for t in traces if t.org_id == org_id]
        if user_id:
            traces = [t for t in traces if t.user_id == user_id]

        if not traces:
            return {"total_traces": 0}

        total_tokens = sum(t.total_tokens for t in traces)
        total_cost = sum(t.total_cost_usd for t in traces)
        durations = [t.total_duration_ms for t in traces if t.total_duration_ms]

        return {
            "total_traces": len(traces),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "success_rate": len([t for t in traces if t.status == TraceStatus.COMPLETED]) / len(traces),
            "by_status": {status.value: len([t for t in traces if t.status == status]) for status in TraceStatus},
        }

    async def persist_trace(self, trace_id: str, db=None):
        """Persist trace to database."""
        trace = self.get_trace(trace_id)
        if not trace or not db:
            return

        try:
            await (
                db.table("agent_traces")
                .upsert(
                    {
                        "trace_id": trace.trace_id,
                        "thread_id": trace.thread_id,
                        "user_id": trace.user_id,
                        "org_id": trace.org_id,
                        "query": trace.query,
                        "status": trace.status.value,
                        "start_time": datetime.fromtimestamp(trace.start_time).isoformat(),
                        "end_time": datetime.fromtimestamp(trace.end_time).isoformat() if trace.end_time else None,
                        "total_duration_ms": trace.total_duration_ms,
                        "total_tokens": trace.total_tokens,
                        "total_cost_usd": trace.total_cost_usd,
                        "steps_json": [s.to_dict() for s in trace.steps],
                        "final_response": trace.final_response,
                        "metadata_json": trace.metadata,
                        "tags": trace.tags,
                    }
                )
                .execute()
            )
        except Exception as e:
            logger.error(f"Failed to persist trace: {e}")

    def _record_metric(self, metric_name: str, value: float, labels: dict = None):
        """Record a metric point."""
        self._metrics_buffer.append(
            MetricPoint(timestamp=time.time(), metric_name=metric_name, value=value, labels=labels or {})
        )
        # Keep buffer manageable
        if len(self._metrics_buffer) > 10000:
            self._metrics_buffer = self._metrics_buffer[-5000:]

    def _calculate_cost(self, tokens: int) -> float:
        """Approximate cost calculation."""
        # Rough estimate: $5 per 1M tokens
        return (tokens / 1_000_000) * 5.0

    def _cleanup_old_traces(self):
        """Remove old traces to prevent memory leak."""
        if len(self._completed_traces) > self._max_completed_traces:
            # Remove oldest traces
            sorted_ids = sorted(self._completed_traces.keys(), key=lambda x: self._completed_traces[x].start_time)
            for trace_id in sorted_ids[: len(self._completed_traces) - self._max_completed_traces]:
                del self._completed_traces[trace_id]


# Global instance
agent_trace_service = AgentTraceService()
