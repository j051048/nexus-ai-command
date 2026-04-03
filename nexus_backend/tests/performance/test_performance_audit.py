"""
Performance & Latency Baseline Tests.
验证 Agent 在高压力或长对话上下文下的响应时延基准。
"""

import pytest
import time
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_agent_graph_latency_baseline():
    """
    Agent Graph 决策延迟基准测试。
    目标：单步 Plan 决策应在 5s 内完成（LLM 依赖除外，主要测系统 Overhead）。
    """
    from app.agent.graph import get_agent_graph, AgentGraph

    # 重置单例，确保干净状态
    AgentGraph._instance = None

    with patch("app.agent.graph.get_checkpointer", return_value=MagicMock()), \
         patch("app.services.ai_service.AIService.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '{"plan": [{"tool": "generate_product_manual", "args": {"product_name": "ICP-MS 7800"}}]}'

        agent = get_agent_graph()

        input_state = {
            "messages": [{"role": "user", "content": "帮我看看 ICP-MS 7800 的参数"}]
        }

        start_time = time.time()

        async for chunk in agent.stream(input_state, thread_id="perf-test"):
            pass

        elapsed = time.time() - start_time
        print(f"\n⚡ Agent 决策时延: {elapsed:.2f}s")

        assert elapsed < 5.0, f"Agent 系统开销过大: {elapsed:.2f}s (基准值: 5.0s)"


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
    print(f"\n⚡ PII 过滤平均吞吐延时: {avg_latency*1000:.2f}ms/条")
    
    assert avg_latency < 0.05, "PII 过滤算法性能下降"
