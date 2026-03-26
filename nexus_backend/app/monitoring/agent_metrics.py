"""
Agent 性能监控 - 提升可观测性
"""

import time
from typing import Dict
from prometheus_client import Histogram, Counter

# Prometheus 指标
agent_node_duration = Histogram(
    'agent_node_duration_seconds',
    'Agent node execution duration',
    ['node_name']
)

agent_node_success = Counter(
    'agent_node_success_total',
    'Agent node success count',
    ['node_name']
)

agent_node_failure = Counter(
    'agent_node_failure_total',
    'Agent node failure count',
    ['node_name']
)


class AgentMetrics:
    """Agent 性能指标收集"""

    async def record_node_execution(
        self,
        node_name: str,
        duration: float,
        success: bool
    ):
        """记录节点执行"""
        agent_node_duration.labels(node_name=node_name).observe(duration)

        if success:
            agent_node_success.labels(node_name=node_name).inc()
        else:
            agent_node_failure.labels(node_name=node_name).inc()


# 全局实例
agent_metrics = AgentMetrics()
