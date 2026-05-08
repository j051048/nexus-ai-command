"""Agent performance metrics."""

import contextlib
from datetime import UTC, datetime

from prometheus_client import Counter, Histogram

agent_node_duration = Histogram(
    "agent_node_duration_seconds", "Agent node execution duration", ["node_name"]
)

agent_node_success = Counter(
    "agent_node_success_total", "Agent node success count", ["node_name"]
)

agent_node_failure = Counter(
    "agent_node_failure_total", "Agent node failure count", ["node_name"]
)


class AgentMetrics:
    """Collect agent node metrics for Prometheus and durable analysis."""

    async def record_node_execution(
        self, node_name: str, duration: float, success: bool
    ):
        agent_node_duration.labels(node_name=node_name).observe(duration)

        if success:
            agent_node_success.labels(node_name=node_name).inc()
        else:
            agent_node_failure.labels(node_name=node_name).inc()

        with contextlib.suppress(Exception):
            from app.core.database import supabase

            if supabase:
                await supabase.table("agent_node_metrics").insert(
                    {
                        "node_name": node_name,
                        "duration_ms": int(duration * 1000),
                        "success": success,
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                ).execute()


agent_metrics = AgentMetrics()
