import pytest
from app.agent.node_intent import route_intent
from app.agent.memory import clean_memory_content, format_memory_for_prompt

# P2: Agent 决策核心 95%+ 覆盖率专项测试 (语义消歧与长内容处理)

@pytest.mark.asyncio
async def test_intent_disambiguation_priority():
    """验证意图识别的“最优解”逻辑 (100% 覆盖多类别意图竞争分支)"""
    # 场景：用户说“帮我把这笔报销申请存入知识库”
    # 该指令同时包含“财务（报销）”和“知识库（存入）”两个关键字
    # 期望：Agent 应当能通过优先级算法确定该指令的终点是“知识库”
    query = "帮我把这笔 $1200 的差旅报销申请自动归档到知识库"
    
    intent_result = await route_intent(query)
    
    # 根据业务权重设计，如果包含“归档”、“存入”且指明“知识库”，优先级应高于基础财务查询
    assert intent_result.category == "knowledge", "意图路由错误：未识别出最终归档动作"
    assert intent_result.confidence > 0.8

def test_memory_cleaning_logic():
    """验证长内容的清洗与异常字符过滤 logic (Prevent Prompt Injection)"""
    # 1. 模拟包含 HTML 标签、非法跨站脚本脚本内容
    raw_content = "<script>alert('xss')</script> 用户提及：[重要] 给研发部涨薪 10%。"
    cleaned = clean_memory_content(raw_content)
    
    # 验证清洗比例 (100% 覆盖 cleaning regex)
    assert "<script>" not in cleaned
    assert "研发部涨薪" in cleaned

    # 2. 模拟超长记忆片段的截断处理
    huge_content = "A" * 10000 
    truncated = clean_memory_content(huge_content, max_len=500)
    assert len(truncated) <= 505 # 允许包含省略号标识

def test_memory_formatting_for_prompts():
    """验证将记忆对象格式化为 Prompt 时的各种边界情况"""
    # 1. 数组为空
    empty_prompt = format_memory_for_prompt([])
    assert "无相关历史记录" in empty_prompt

    # 2. 包含无效/None 数据的对象
    noisy_memories = [
        {"content": "valid memory", "id": "01"},
        {"content": None, "id": "02"}
    ]
    formatted = format_memory_for_prompt(noisy_memories)
    assert "valid memory" in formatted
    assert "None" not in formatted, "格式化逻辑未能成功过滤 None 数据"
