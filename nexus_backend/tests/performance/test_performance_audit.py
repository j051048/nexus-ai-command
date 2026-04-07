"""
Performance & Latency Baseline Tests.
验证关键子系统的性能基准。
"""

import pytest
import time
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_agent_graph_latency_baseline():
    """
    Agent Graph 编译与初始化延迟基准测试。
    目标：graph compile（不含外部 IO）应在 5s 内完成。
    """
    from app.agent.graph import AgentGraph, build_agent_graph
    from langgraph.checkpoint.memory import InMemorySaver

    # 重置单例
    AgentGraph._instance = None

    with patch("app.agent.graph.get_checkpointer", return_value=InMemorySaver()):
        start_time = time.time()

        # 测量 graph 构建 + 编译（这是纯 CPU 开销，不涉及 IO）
        graph = build_agent_graph()
        checkpointer = InMemorySaver()
        compiled = graph.compile(checkpointer=checkpointer)

        compile_elapsed = time.time() - start_time

        # 验证编译产出合法
        assert compiled is not None
        assert hasattr(compiled, "astream")

        assert compile_elapsed < 5.0, (
            f"Agent Graph 编译耗时过大: {compile_elapsed:.2f}s (基准值: 5.0s)"
        )


@pytest.mark.benchmark
def test_pii_filter_throughput():
    """验证 PII 过滤服务的吞吐能力。"""
    from app.services.conversation_memory.pii_filter import mask_pii

    text = "张三 (手机 13800138000) 在华为 (HUAWEI) 负责 ICP-MS 7800 项目。" * 50

    start_time = time.time()
    for _ in range(100):
        mask_pii(text)
    end_time = time.time()

    avg_latency = (end_time - start_time) / 100

    assert avg_latency < 0.05, "PII 过滤算法性能下降"
