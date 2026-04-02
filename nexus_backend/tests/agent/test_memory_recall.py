import pytest
from app.agent.memory import save_memory, search_memory
import asyncio

# P2: 长效记忆跨会话检索 (Memory Recall) 专项测试
# 验证：不同 Session 下的信息召回一致性

@pytest.mark.asyncio
async def test_cross_session_preference_recall():
    """
    测试点：
    1. Session A: 告知用户偏好 (喜欢柱状图，优先关注研发部比例)
    2. Session B: 询问销售报告建议
    3. 期望：Agent 能在检索结果中提取到该偏好并体现在决策 (Context) 中
    """
    user_id = "test_qa_expert_02"
    org_id = "test_org_id"
    
    # 模拟第一阶段：注入偏好
    # save_memory 是 app.agent.memory 中的核心存入函数
    await save_memory(
        user_id=user_id, 
        org_id=org_id, 
        content="我比较关注研发部的报销比例，以后对比数据时优先生成研发部的柱状图分析报告。", 
        session_id="session_01",
        importance=0.9
    )
    
    # 模拟第二阶段：跨会话检索
    # search_memory 是 app.agent.memory 中的核心检索函数
    query = "帮我生成一份上季度的预算对比图表建议"
    
    # 检索记忆库
    # 期望：即使 query 没有明确提到研发部，但由于“预算对比”与“报销比例”语义相近，应当召回
    related_memories = await search_memory(user_id=user_id, query=query, top_k=3)
    
    # 验证检索结果
    found_preference = False
    for memory in related_memories:
        if "研发部" in memory.content and "柱状图" in memory.content:
            found_preference = True
            break
            
    assert found_preference is True, f"记忆识别失败：未能在会话中召回跨 session 的研发部偏好。检索结果: {[m.content for m in related_memories]}"

@pytest.mark.asyncio
async def test_memory_conflict_resolution():
    """测试当两个记忆点发生冲突时，Agent 的检索逻辑 (语义权重优先机制)"""
    user_id = "test_qa_expert_03"
    org_id = "test_org_id"
    
    # 1. 旧偏好 (一个月前)
    await save_memory(user_id, "我以前喜欢用表格分析数据", org_id=org_id)
    # 2. 新偏好 (刚刚)
    await save_memory(user_id, "现在我更喜欢用看板视图分析数据", org_id=org_id)
    
    # 3. 询问
    query = "帮我分析下本月数据"
    results = await search_memory(user_id, query, top_k=1)
    
    # 验证：最新的记忆应当排名更靠前
    assert "看板视图" in results[0].content, "记忆召回错误：未优先召回最新/最高权重的偏好"
