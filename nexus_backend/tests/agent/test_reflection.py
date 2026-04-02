import pytest
import asyncio
from app.agent.node_reflect import reflect_logic

@pytest.mark.asyncio
async def test_agent_hallucination_detection():
    """
    P2: 模拟明显的逻辑冲突场景，验证自反思 (Reflect) 节点的鲁棒性。
    """
     hall_context = {
        "tools_output": "{\"data\": {\"balance\": 12000, \"currency\": \"USD\"}}",
        "agent_prediction": "太好了！公司账户余额现在显示有 1.2 亿美金，我们的资金非常充裕。",
        "original_query": "查询公司账户余额",
        "history": "User: 我们现在还有多少盈余？"
    }

    try:
        reflection = await reflect_logic(hall_context)
        
        # 核心断言：必须识别为幻觉
        assert reflection.is_hallucination is True
        # 核心断言：反思原因应包含数值对比逻辑
        assert any(x in reflection.reason for x in ["数据", "不符", "数值", "偏差"])
        # 建议修正值
        assert "12,000" in reflection.suggestion or "12k" in reflection.suggestion.lower()
        
    except Exception as e:
        pytest.fail(f"Reflection logic crashed on high-risk scenario: {e}")

@pytest.mark.asyncio
async def test_reflection_concurrency_stability():
    """验证并发请求下，反思节点的检出一致性。"""
    tasks = [reflect_logic({"tools_output": "100", "agent_prediction": "9999"}) for _ in range(10)]
    results = await asyncio.gather(*tasks)
    
    detected_count = sum(1 for r in results if r.is_hallucination)
    assert detected_count >= 9, "并发情况下 Reflect 节点的检测率显著抖动"
