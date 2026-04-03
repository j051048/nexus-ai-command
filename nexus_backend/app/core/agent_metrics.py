"""
Agent 监控指标收集
放在 nexus_backend/app/core/agent_metrics.py
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 简单的内存指标存储（生产环境建议用 Prometheus）
_metrics: dict[str, Any] = {
    "total_requests": 0,
    "total_tokens": 0,
    "total_cost": 0.0,
    "avg_response_time": 0.0,
    "error_count": 0,
}


def record_agent_execution(
    user_id: str, complexity: str, model: str, tokens: int, cost: float, duration: float, success: bool
):
    """记录 Agent 执行指标"""
    _metrics["total_requests"] += 1
    _metrics["total_tokens"] += tokens
    _metrics["total_cost"] += cost

    # 更新平均响应时间
    prev_avg = _metrics["avg_response_time"]
    n = _metrics["total_requests"]
    _metrics["avg_response_time"] = (prev_avg * (n - 1) + duration) / n

    if not success:
        _metrics["error_count"] += 1

    logger.info(
        f"Agent执行: user={user_id}, complexity={complexity}, "
        f"model={model}, tokens={tokens}, cost=${cost:.4f}, "
        f"duration={duration:.2f}s, success={success}"
    )


def get_metrics() -> dict[str, Any]:
    """获取当前指标"""
    return _metrics.copy()


# 使用示例（在 graph.py 或 nodes.py 中）:
# from app.core.agent_metrics import record_agent_execution
#
# start_time = time.time()
# result = await agent.run(...)
# duration = time.time() - start_time
#
# record_agent_execution(
#     user_id=state["user_id"],
#     complexity=state["complexity"],
#     model=state["model"],
#     tokens=result["usage"]["total_tokens"],
#     cost=calculate_cost(result["usage"]),
#     duration=duration,
#     success=True
# )
