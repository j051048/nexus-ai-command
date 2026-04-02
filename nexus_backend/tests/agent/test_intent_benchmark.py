import pytest
from app.agent.router import classify_intent
import asyncio

# P0: AI Agent 意图识别准确率基准测试 (Benchmark)
# 涵盖 15 年大厂经验中的核心业务指令场景

BENCHMARK_CASES = [
    # 1. 财务类 (Finance)
    ("对比去年和今年的研发部预算占比", {"main_intent": "finance", "complexity": "medium"}),
    ("上个月差旅费报销总计是多少？", {"main_intent": "finance", "complexity": "low"}),
    
    # 2. OA/审批类 (Approval & OA)
    ("帮我批准这个合同", {"main_intent": "approval", "complexity": "low"}),
    ("帮我定个明天下午三点的会议室，拉上建林和志强", {"main_intent": "oa", "complexity": "medium"}),
    
    # 3. CRM/销售类 (Sales)
    ("查询潜在客户建林的转化率", {"main_intent": "crm", "complexity": "low"}),
    ("显示这个月的销售流水线", {"main_intent": "crm", "complexity": "low"}),
    
    # 4. 复杂 WBS 任务分解类 (Strategy/Task Management)
    ("最近销售下滑严重，帮我分析原因并整理成任务分发给华南区经理，同时更新总控看板", 
     {"main_intent": "strategy", "complexity": "high", "requires_wbs": True}),
    
    # 5. 知识库/语义路由类 (Knowledge Base)
    ("公司关于加班补休的政策是怎么规定的？", {"main_intent": "knowledge_base", "complexity": "low"}),
    
    # 6. 模糊/边界案例 (Edge Cases)
    ("帮我批准一下", {"main_intent": "approval", "need_more_info": True}),
    ("今天天气怎么样", {"main_intent": "fallback", "complexity": "low"})
]

@pytest.mark.asyncio
@pytest.mark.parametrize("query,expected", BENCHMARK_CASES)
async def test_intent_accuracy_benchmark(query, expected):
    """验证 Agent 核心大脑的路由分发是否正确"""
    try:
        # classify_intent 是 app.agent.router 中的核心分类函数
        result = await classify_intent(query)
        
        # 验证主意图
        assert result.main_intent == expected["main_intent"], \
            f"Query: {query}, Expected: {expected['main_intent']}, Got: {result.main_intent}"
        
        # 验证复杂度
        if "complexity" in expected:
            assert result.complexity == expected["complexity"]
            
        # 验证 WBS 触发标志
        if expected.get("requires_wbs"):
            assert result.requires_wbs is True
            
    except Exception as e:
        pytest.fail(f"Intent classification failed for query '{query}': {e}")

if __name__ == "__main__":
    # 方便手动运行
    import asyncio
    asyncio.run(test_intent_accuracy_benchmark("测试指令", {"main_intent": "test"}))
