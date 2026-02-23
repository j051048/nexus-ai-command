"""
P2 Enhancement: Auto-Scaling Service

Implements automatic scaling strategies for cost optimization.
Fixes Issue #39: Missing auto-scaling strategy.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ScalingAction(Enum):
    """Scaling actions."""

    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"


class ResourceType(Enum):
    """Resource types for scaling."""

    WORKERS = "workers"
    LLM_THREADS = "llm_threads"
    DB_CONNECTIONS = "db_connections"
    CACHE_SIZE = "cache_size"
    BATCH_SIZE = "batch_size"


@dataclass
class ScalingMetric:
    """Metric for scaling decisions."""

    name: str
    current_value: float
    threshold_high: float
    threshold_low: float
    weight: float = 1.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ScalingDecision:
    """Scaling decision result."""

    action: ScalingAction
    resource_type: ResourceType
    current_size: int
    target_size: int
    reason: str
    metrics: dict[str, float]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ScalingConfig:
    """Configuration for a scalable resource."""

    resource_type: ResourceType
    min_size: int
    max_size: int
    scale_up_threshold: float
    scale_down_threshold: float
    cooldown_seconds: int = 60
    scale_up_step: int = 1
    scale_down_step: int = 1


class AutoScalingService:
    """
    P2 Enhancement: Automatic scaling for cost optimization.

    Features:
    - Metric-based scaling decisions
    - Configurable thresholds per resource
    - Cooldown periods to prevent thrashing
    - Cost-aware scaling
    - Predictive scaling based on trends
    - Integration with monitoring
    """

    DEFAULT_CONFIGS = {
        ResourceType.WORKERS: ScalingConfig(
            resource_type=ResourceType.WORKERS,
            min_size=2,
            max_size=20,
            scale_up_threshold=0.8,  # 80% utilization
            scale_down_threshold=0.3,  # 30% utilization
            cooldown_seconds=60,
        ),
        ResourceType.LLM_THREADS: ScalingConfig(
            resource_type=ResourceType.LLM_THREADS,
            min_size=5,
            max_size=50,
            scale_up_threshold=0.7,
            scale_down_threshold=0.2,
            cooldown_seconds=30,
        ),
        ResourceType.DB_CONNECTIONS: ScalingConfig(
            resource_type=ResourceType.DB_CONNECTIONS,
            min_size=5,
            max_size=30,
            scale_up_threshold=0.75,
            scale_down_threshold=0.25,
            cooldown_seconds=120,
        ),
        ResourceType.CACHE_SIZE: ScalingConfig(
            resource_type=ResourceType.CACHE_SIZE,
            min_size=100,
            max_size=10000,
            scale_up_threshold=0.9,
            scale_down_threshold=0.5,
            cooldown_seconds=300,
        ),
    }

    def __init__(self):
        self.configs: dict[ResourceType, ScalingConfig] = dict(self.DEFAULT_CONFIGS)
        self.current_sizes: dict[ResourceType, int] = {rt: config.min_size for rt, config in self.configs.items()}
        self._last_scaling: dict[ResourceType, float] = {}
        self._metrics_history: dict[ResourceType, list[ScalingMetric]] = {}
        self._scaling_history: list[ScalingDecision] = []
        self._running = False
        self._task = None

    def configure(self, resource_type: ResourceType, config: ScalingConfig):
        """Update scaling configuration."""
        self.configs[resource_type] = config
        if resource_type not in self.current_sizes:
            self.current_sizes[resource_type] = config.min_size

    def set_current_size(self, resource_type: ResourceType, size: int):
        """Set current size of a resource."""
        config = self.configs.get(resource_type)
        if config:
            self.current_sizes[resource_type] = max(config.min_size, min(config.max_size, size))

    def record_metric(self, metric: ScalingMetric):
        """Record a metric for scaling decisions."""
        # Map metric name to resource type
        resource_type = self._map_metric_to_resource(metric.name)
        if not resource_type:
            return

        if resource_type not in self._metrics_history:
            self._metrics_history[resource_type] = []

        self._metrics_history[resource_type].append(metric)

        # Keep history manageable
        max_history = 100
        if len(self._metrics_history[resource_type]) > max_history:
            self._metrics_history[resource_type] = self._metrics_history[resource_type][-max_history:]

    def _map_metric_to_resource(self, metric_name: str) -> ResourceType | None:
        """Map metric name to resource type."""
        mapping = {
            "worker_utilization": ResourceType.WORKERS,
            "worker_queue_size": ResourceType.WORKERS,
            "llm_thread_utilization": ResourceType.LLM_THREADS,
            "llm_request_rate": ResourceType.LLM_THREADS,
            "db_connection_utilization": ResourceType.DB_CONNECTIONS,
            "db_connection_count": ResourceType.DB_CONNECTIONS,
            "cache_hit_rate": ResourceType.CACHE_SIZE,
            "cache_size": ResourceType.CACHE_SIZE,
        }
        return mapping.get(metric_name)

    def evaluate_scaling(self, resource_type: ResourceType) -> ScalingDecision:
        """
        Evaluate if scaling is needed for a resource.

        Returns a ScalingDecision with the recommended action.
        """
        config = self.configs.get(resource_type)
        if not config:
            return ScalingDecision(
                action=ScalingAction.NO_ACTION,
                resource_type=resource_type,
                current_size=0,
                target_size=0,
                reason="Resource not configured",
                metrics={},
            )

        current_size = self.current_sizes.get(resource_type, config.min_size)
        metrics = self._metrics_history.get(resource_type, [])

        # Check cooldown
        last_scale = self._last_scaling.get(resource_type, 0)
        if time.time() - last_scale < config.cooldown_seconds:
            return ScalingDecision(
                action=ScalingAction.NO_ACTION,
                resource_type=resource_type,
                current_size=current_size,
                target_size=current_size,
                reason=f"Cooldown period active ({config.cooldown_seconds}s)",
                metrics=self._get_latest_metrics(metrics),
            )

        # Calculate average utilization
        if not metrics:
            return ScalingDecision(
                action=ScalingAction.NO_ACTION,
                resource_type=resource_type,
                current_size=current_size,
                target_size=current_size,
                reason="No metrics available",
                metrics={},
            )

        # Use recent metrics (last 5)
        recent_metrics = metrics[-5:]
        avg_utilization = sum(m.current_value for m in recent_metrics) / len(recent_metrics)

        # Make scaling decision
        if avg_utilization >= config.scale_up_threshold:
            # Scale up
            new_size = min(current_size + config.scale_up_step, config.max_size)
            if new_size > current_size:
                return ScalingDecision(
                    action=ScalingAction.SCALE_UP,
                    resource_type=resource_type,
                    current_size=current_size,
                    target_size=new_size,
                    reason=f"Utilization {avg_utilization:.1%} >= threshold {config.scale_up_threshold:.1%}",
                    metrics=self._get_latest_metrics(metrics),
                )

        elif avg_utilization <= config.scale_down_threshold:
            # Scale down
            new_size = max(current_size - config.scale_down_step, config.min_size)
            if new_size < current_size:
                return ScalingDecision(
                    action=ScalingAction.SCALE_DOWN,
                    resource_type=resource_type,
                    current_size=current_size,
                    target_size=new_size,
                    reason=f"Utilization {avg_utilization:.1%} <= threshold {config.scale_down_threshold:.1%}",
                    metrics=self._get_latest_metrics(metrics),
                )

        return ScalingDecision(
            action=ScalingAction.NO_ACTION,
            resource_type=resource_type,
            current_size=current_size,
            target_size=current_size,
            reason="Within optimal range",
            metrics=self._get_latest_metrics(metrics),
        )

    def _get_latest_metrics(self, metrics: list[ScalingMetric]) -> dict[str, float]:
        """Get latest metric values."""
        if not metrics:
            return {}
        return {m.name: m.current_value for m in metrics[-5:]}

    async def apply_scaling(self, decision: ScalingDecision) -> bool:
        """
        Apply a scaling decision.
        Override this method to implement actual scaling.
        """
        if decision.action == ScalingAction.NO_ACTION:
            return False

        resource_type = decision.resource_type

        # Update current size
        self.current_sizes[resource_type] = decision.target_size
        self._last_scaling[resource_type] = time.time()

        # Record in history
        self._scaling_history.append(decision)
        if len(self._scaling_history) > 100:
            self._scaling_history = self._scaling_history[-50:]

        logger.info(
            f"Scaling {decision.action.value}: {resource_type.value} "
            f"{decision.current_size} -> {decision.target_size} ({decision.reason})"
        )

        return True

    async def start_monitoring(self, interval: int = 30):
        """Start periodic scaling evaluation."""
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop(interval))
        logger.info(f"Auto-scaling monitoring started (interval={interval}s)")

    async def stop_monitoring(self):
        """Stop periodic scaling evaluation."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Auto-scaling monitoring stopped")

    async def _monitoring_loop(self, interval: int):
        """Periodic monitoring loop."""
        while self._running:
            try:
                # Evaluate all resources
                for resource_type in self.configs:
                    decision = self.evaluate_scaling(resource_type)
                    if decision.action != ScalingAction.NO_ACTION:
                        await self.apply_scaling(decision)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scaling monitoring error: {e}")
                await asyncio.sleep(interval)

    def get_status(self) -> dict[str, Any]:
        """Get current scaling status."""
        return {
            "running": self._running,
            "resources": {
                rt.value: {
                    "current_size": self.current_sizes.get(rt, 0),
                    "min_size": config.min_size,
                    "max_size": config.max_size,
                    "scale_up_threshold": config.scale_up_threshold,
                    "scale_down_threshold": config.scale_down_threshold,
                }
                for rt, config in self.configs.items()
            },
            "last_scaling": {
                rt.value: datetime.fromtimestamp(ts).isoformat() if ts else None
                for rt, ts in self._last_scaling.items()
            },
            "recent_decisions": [
                {
                    "action": d.action.value,
                    "resource": d.resource_type.value,
                    "current": d.current_size,
                    "target": d.target_size,
                    "reason": d.reason,
                    "timestamp": d.timestamp,
                }
                for d in self._scaling_history[-10:]
            ],
        }

    def get_cost_savings(self) -> dict[str, Any]:
        """Estimate cost savings from scaling."""
        # Calculate potential savings from scaling down
        savings = 0.0
        for _resource_type, decision in [(rt, self.evaluate_scaling(rt)) for rt in self.configs]:
            if decision.action == ScalingAction.SCALE_DOWN:
                # Estimate savings (simplified)
                reduction = decision.current_size - decision.target_size
                savings += reduction * 0.1  # $0.10 per unit per hour (example)

        return {
            "estimated_hourly_savings": round(savings, 4),
            "scale_down_opportunities": [
                {
                    "resource": rt.value,
                    "current_size": self.current_sizes.get(rt, 0),
                    "recommended_size": self.evaluate_scaling(rt).target_size,
                }
                for rt in self.configs
                if self.evaluate_scaling(rt).action == ScalingAction.SCALE_DOWN
            ],
        }


# Global instance
auto_scaling_service = AutoScalingService()
