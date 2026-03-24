"""
Item 45: Agent Replay Engine

Provides session trace loading, step-by-step replay, and cross-session
comparison for debugging and auditing agent executions.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.services.agent_trace_service import AgentTrace, agent_trace_service

logger = logging.getLogger(__name__)


@dataclass
class ReplayStep:
    """A single step in the replay timeline."""

    index: int
    node_name: str
    input_snapshot: dict = field(default_factory=dict)
    output_snapshot: dict = field(default_factory=dict)
    timestamp: str = ""
    duration_ms: int | None = None
    tokens_used: int = 0
    tool_calls: list[dict] = field(default_factory=list)
    status: str = "completed"
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "node_name": self.node_name,
            "input_snapshot": self.input_snapshot,
            "output_snapshot": self.output_snapshot,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
            "tool_calls": self.tool_calls,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class SessionDiff:
    """Differences between two agent sessions."""

    thread_id_a: str
    thread_id_b: str
    summary: dict = field(default_factory=dict)
    step_diffs: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "thread_id_a": self.thread_id_a,
            "thread_id_b": self.thread_id_b,
            "summary": self.summary,
            "step_diffs": self.step_diffs,
        }


class AgentReplayService:
    """
    Agent Replay Engine — loads historical execution traces and provides
    step-by-step replay and cross-session comparison capabilities.

    Data sources (priority order):
    1. In-memory trace cache (AgentTraceService)
    2. Database agent_traces table (via Supabase)
    3. LangGraph checkpointer state snapshots
    """

    async def load_session_trace(
        self, thread_id: str, *, db=None
    ) -> dict[str, Any] | None:
        """
        Load the full execution trace for a session (thread_id).

        Checks in-memory cache first, then falls back to DB.
        Returns the trace dict or None if not found.
        """
        # 1. Check in-memory traces
        traces = agent_trace_service.get_thread_traces(thread_id)
        if traces:
            # Return the most recent trace for this thread
            traces.sort(key=lambda t: t.start_time, reverse=True)
            return traces[0].to_dict()

        # 2. Fall back to DB
        if db:
            try:
                result = (
                    await db.table("agent_traces")
                    .select("*")
                    .eq("thread_id", thread_id)
                    .order("start_time", desc=True)
                    .limit(1)
                    .execute()
                )
                if result.data:
                    return result.data[0]
            except Exception as e:
                logger.warning(f"[Replay] DB lookup failed for thread {thread_id}: {e}")

        return None

    async def get_replay_steps(
        self, thread_id: str, *, db=None
    ) -> list[dict]:
        """
        Return a list of replay steps (state snapshots) for a session.

        Each step includes: node name, input/output, timestamp, token usage.
        """
        trace_data = await self.load_session_trace(thread_id, db=db)
        if not trace_data:
            return []

        # Determine steps source
        steps_raw = trace_data.get("steps") or trace_data.get("steps_json") or []

        replay_steps: list[dict] = []
        for i, step in enumerate(steps_raw):
            ts_raw = step.get("timestamp")
            if isinstance(ts_raw, (int, float)):
                ts_str = datetime.fromtimestamp(ts_raw, tz=UTC).isoformat()
            elif isinstance(ts_raw, str):
                ts_str = ts_raw
            else:
                ts_str = ""

            rs = ReplayStep(
                index=i,
                node_name=step.get("node_type", "unknown"),
                input_snapshot=step.get("input_data", {}),
                output_snapshot=step.get("output_data", {}),
                timestamp=ts_str,
                duration_ms=step.get("duration_ms"),
                tokens_used=step.get("tokens_used", 0),
                tool_calls=step.get("tool_calls", []),
                status=step.get("status", "completed"),
                error=step.get("error"),
            )
            replay_steps.append(rs.to_dict())

        return replay_steps

    async def replay_step(
        self, thread_id: str, step_index: int, *, db=None
    ) -> dict | None:
        """
        Get detailed state for a specific step in the replay.

        Returns None if the step index is out of range.
        """
        steps = await self.get_replay_steps(thread_id, db=db)
        if not steps or step_index < 0 or step_index >= len(steps):
            return None
        return steps[step_index]

    async def get_session_timeline(
        self, session_id: str, org_id: str, *, db=None
    ) -> dict:
        """
        Build a Time Travel timeline for a chat session.

        Aggregates all agent_traces whose thread_id matches the pattern
        ``{org_id}::{session_id}::msg-*`` and returns them as an ordered
        timeline of message-level execution summaries.
        """
        timeline: list[dict] = []

        # thread_id pattern: "{org_id}::{session_id}::msg-{timestamp}"
        thread_prefix = f"{org_id}::{session_id}::msg-"

        # 1. Check in-memory traces (both active and completed)
        in_memory_traces = [
            t for t in list(agent_trace_service._active_traces.values())
            + list(agent_trace_service._completed_traces.values())
            if t.thread_id.startswith(thread_prefix)
        ]
        for trace in in_memory_traces:
                nodes = [s.node_type for s in trace.steps] if trace.steps else []
                timeline.append({
                    "thread_id": trace.thread_id,
                    "trace_id": trace.trace_id,
                    "timestamp": datetime.fromtimestamp(trace.start_time, tz=UTC).isoformat()
                    if trace.start_time else None,
                    "query": (trace.query or "")[:200],
                    "nodes_executed": nodes,
                    "status": trace.status.value,
                    "steps_count": len(trace.steps),
                    "token_usage": {
                        "total": trace.total_tokens,
                    },
                    "duration_ms": trace.total_duration_ms,
                })

        # 2. Fall back / supplement from DB
        if db:
            try:
                result = (
                    await db.table("agent_traces")
                    .select("trace_id, thread_id, query, status, start_time, "
                            "total_tokens, total_duration_ms, steps_json")
                    .eq("org_id", org_id)
                    .like("thread_id", f"%::{session_id}::msg-%")
                    .order("start_time", desc=False)
                    .limit(100)
                    .execute()
                )
                existing_trace_ids = {t["trace_id"] for t in timeline}
                for row in (result.data or []):
                    if row.get("trace_id") in existing_trace_ids:
                        continue
                    steps_json = row.get("steps_json") or []
                    nodes = [s.get("node_type", "unknown") for s in steps_json] if steps_json else []
                    timeline.append({
                        "thread_id": row.get("thread_id", ""),
                        "trace_id": row.get("trace_id", ""),
                        "timestamp": row.get("start_time"),
                        "query": (row.get("query") or "")[:200],
                        "nodes_executed": nodes,
                        "status": row.get("status", ""),
                        "steps_count": len(steps_json),
                        "token_usage": {
                            "total": row.get("total_tokens", 0),
                        },
                        "duration_ms": row.get("total_duration_ms"),
                    })
            except Exception as e:
                logger.warning(f"[Replay] Session timeline DB query failed: {e}")

        # Sort by timestamp
        timeline.sort(key=lambda t: t.get("timestamp") or "")

        return {
            "session_id": session_id,
            "org_id": org_id,
            "timeline": timeline,
            "total_messages": len(timeline),
        }

    async def compare_sessions(
        self, thread_id_a: str, thread_id_b: str, *, db=None
    ) -> dict:
        trace_a = await self.load_session_trace(thread_id_a, db=db)
        trace_b = await self.load_session_trace(thread_id_b, db=db)

        diff = SessionDiff(thread_id_a=thread_id_a, thread_id_b=thread_id_b)

        if not trace_a and not trace_b:
            diff.summary = {"error": "Neither session found"}
            return diff.to_dict()
        if not trace_a:
            diff.summary = {"error": f"Session A ({thread_id_a}) not found"}
            return diff.to_dict()
        if not trace_b:
            diff.summary = {"error": f"Session B ({thread_id_b}) not found"}
            return diff.to_dict()

        steps_a = trace_a.get("steps") or trace_a.get("steps_json") or []
        steps_b = trace_b.get("steps") or trace_b.get("steps_json") or []

        # Summary comparison
        diff.summary = {
            "session_a": {
                "query": trace_a.get("query", "")[:200],
                "status": trace_a.get("status", ""),
                "total_tokens": trace_a.get("total_tokens", 0),
                "total_duration_ms": trace_a.get("total_duration_ms"),
                "step_count": len(steps_a),
            },
            "session_b": {
                "query": trace_b.get("query", "")[:200],
                "status": trace_b.get("status", ""),
                "total_tokens": trace_b.get("total_tokens", 0),
                "total_duration_ms": trace_b.get("total_duration_ms"),
                "step_count": len(steps_b),
            },
            "delta_tokens": (trace_b.get("total_tokens", 0) or 0)
            - (trace_a.get("total_tokens", 0) or 0),
            "delta_duration_ms": (trace_b.get("total_duration_ms") or 0)
            - (trace_a.get("total_duration_ms") or 0),
        }

        # Per-step comparison (zip to shorter list, then note extras)
        max_steps = max(len(steps_a), len(steps_b))
        for i in range(max_steps):
            sa = steps_a[i] if i < len(steps_a) else None
            sb = steps_b[i] if i < len(steps_b) else None

            step_diff: dict[str, Any] = {"index": i}
            if sa and sb:
                step_diff["node_a"] = sa.get("node_type", "")
                step_diff["node_b"] = sb.get("node_type", "")
                step_diff["same_node"] = step_diff["node_a"] == step_diff["node_b"]
                step_diff["tokens_a"] = sa.get("tokens_used", 0)
                step_diff["tokens_b"] = sb.get("tokens_used", 0)
                step_diff["duration_a_ms"] = sa.get("duration_ms")
                step_diff["duration_b_ms"] = sb.get("duration_ms")
            elif sa:
                step_diff["node_a"] = sa.get("node_type", "")
                step_diff["node_b"] = None
                step_diff["note"] = "Only in session A"
            else:
                step_diff["node_a"] = None
                step_diff["node_b"] = sb.get("node_type", "") if sb else ""
                step_diff["note"] = "Only in session B"

            diff.step_diffs.append(step_diff)

        return diff.to_dict()


# Global singleton
agent_replay_service = AgentReplayService()
