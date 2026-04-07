"""
Intent Router classify_query 单元测试

覆盖：4 级复杂度分类、否定前缀过滤、记忆回顾模式、长文写作、实时信息、
      查询/执行动词语义区分、Agent 角色检测、多 Agent 编排检测
"""
import pytest

from app.agent.router import _filter_negated_keywords, classify_query, detect_agent_role
from app.agent.state import QueryComplexity


class TestClassifyQuerySimple:
    """SIMPLE 级别：问候、闲聊、自我介绍"""

    @pytest.mark.parametrize("query", [
        "你好", "hi", "hello", "嗨", "早上好", "谢谢", "ok",
        "你是谁", "帮我", "好的", "了解",
    ])
    def test_greetings(self, query):
        complexity, _ = classify_query(query)
        assert complexity == QueryComplexity.SIMPLE

    @pytest.mark.parametrize("query", [
        "你能做什么", "你会哪些技能", "介绍一下你自己",
        "你能帮我做什么吗", "你的功能有哪些",
    ])
    def test_self_description(self, query):
        complexity, _ = classify_query(query)
        assert complexity == QueryComplexity.SIMPLE

    @pytest.mark.parametrize("query", [
        "聊聊天", "讲个笑话", "你觉得怎么样", "哈哈", "晚安",
    ])
    def test_chitchat(self, query):
        complexity, _ = classify_query(query)
        assert complexity == QueryComplexity.SIMPLE

    def test_very_short_input(self):
        complexity, _ = classify_query("a")
        assert complexity == QueryComplexity.SIMPLE

    def test_empty_input(self):
        complexity, _ = classify_query("")
        assert complexity == QueryComplexity.SIMPLE


class TestClassifyQueryModerate:
    """MODERATE 级别：单工具查询、记忆回顾、实时信息"""

    @pytest.mark.parametrize("query", [
        "查一下我的请假记录", "帮我看看项目进度", "客户列表",
        "查询本月考勤", "合同到期提醒",
    ])
    def test_business_queries(self, query):
        complexity, _ = classify_query(query)
        assert complexity == QueryComplexity.MODERATE

    @pytest.mark.parametrize("query", [
        "你还记得我之前说过什么吗",
        "记得林凯吗", "我之前提过的方案",
    ])
    def test_memory_recall(self, query):
        complexity, _ = classify_query(query)
        assert complexity == QueryComplexity.MODERATE

    @pytest.mark.parametrize("query", [
        "推荐几部好看的电影", "今天天气怎么样", "最近有什么新闻",
    ])
    def test_realtime_info(self, query):
        complexity, _ = classify_query(query)
        assert complexity == QueryComplexity.MODERATE

    def test_query_verb_downgrades_critical_keyword(self):
        """查看审批 → 只有查询动词，应降级为 MODERATE"""
        complexity, _ = classify_query("查看审批记录")
        assert complexity == QueryComplexity.MODERATE


class TestClassifyQueryComplex:
    """COMPLEX 级别：多步分析、报告、长文写作"""

    @pytest.mark.parametrize("query", [
        "分析本季度销售趋势", "生成竞品对比报告",
        "统计各部门绩效排名", "仪表盘数据总结",
    ])
    def test_analysis_queries(self, query):
        complexity, _ = classify_query(query)
        assert complexity == QueryComplexity.COMPLEX

    @pytest.mark.parametrize("query", [
        "写一篇3000字的产品推广软文",
        "撰写年度销售报告",
        "编写客户拜访方案书",
    ])
    def test_longform_writing(self, query):
        complexity, _ = classify_query(query)
        assert complexity == QueryComplexity.COMPLEX

    def test_long_text_auto_complex(self):
        """超过 200 字的输入自动升级为 COMPLEX"""
        long_query = "请帮我分析" + "这个数据" * 50
        complexity, _ = classify_query(long_query)
        assert complexity == QueryComplexity.COMPLEX


class TestClassifyQueryCritical:
    """CRITICAL 级别：不可逆操作（审批、财务、HR 敏感）"""

    @pytest.mark.parametrize("query", [
        "批准张三的报销申请", "拒绝这个审批",
        "发起付款转账", "批量删除过期数据",
        "提交报销申请",
    ])
    def test_critical_operations(self, query):
        complexity, _ = classify_query(query)
        assert complexity == QueryComplexity.CRITICAL

    def test_execute_verb_required(self):
        """有执行动词 + 关键词 → CRITICAL"""
        complexity, _ = classify_query("批准这个审批请求")
        assert complexity == QueryComplexity.CRITICAL


class TestNegationFilter:
    """否定前缀过滤：不需要报销 → 报销被过滤"""

    def test_negation_removes_keyword(self):
        result = _filter_negated_keywords("不需要报销了", {"报销"})
        assert "报销" not in result

    def test_no_negation_keeps_keyword(self):
        result = _filter_negated_keywords("我要报销", {"报销"})
        assert "报销" in result

    def test_negation_only_affects_adjacent(self):
        result = _filter_negated_keywords("不需要加班，但要报销", {"加班", "报销"})
        assert "加班" not in result
        assert "报销" in result


class TestDetectAgentRole:
    """VMD Agent 角色检测"""

    def test_content_agent(self):
        code, scene, multi = detect_agent_role("帮我写一篇白皮书", QueryComplexity.COMPLEX)
        assert code == "content_agent"
        assert scene == "content_generation"
        assert multi is False

    def test_sales_agent(self):
        code, scene, multi = detect_agent_role("生成销售话术Battlecard", QueryComplexity.MODERATE)
        assert code == "sales_agent"

    def test_multi_agent_orchestration(self):
        code, scene, multi = detect_agent_role("制定完整的营销方案", QueryComplexity.COMPLEX)
        assert code == "director_agent"
        assert multi is True

    def test_simple_query_no_role(self):
        code, scene, multi = detect_agent_role("你好", QueryComplexity.SIMPLE)
        assert code == ""
        assert multi is False

    def test_no_match_returns_empty(self):
        code, scene, multi = detect_agent_role("今天吃什么", QueryComplexity.MODERATE)
        assert code == ""


class TestQueryComplexityModelTier:
    """QueryComplexity → model_tier 映射"""

    def test_simple_economy(self):
        assert QueryComplexity.SIMPLE.model_tier == "economy"

    def test_moderate_balanced(self):
        assert QueryComplexity.MODERATE.model_tier == "balanced"

    def test_complex_power(self):
        assert QueryComplexity.COMPLEX.model_tier == "power"

    def test_critical_flagship(self):
        assert QueryComplexity.CRITICAL.model_tier == "flagship"

class TestWorkflowRecipeMatching:
    @pytest.mark.asyncio
    async def test_contract_approval_recipe(self):
        from unittest.mock import MagicMock

        from langchain_core.messages import HumanMessage

        from app.agent.router import route_node
        config = MagicMock()
        config.get_model_for_complexity.return_value = "gpt-4o-mini"
        state = {"messages": [HumanMessage(content="我有一个合同需要提交审批")], "config": config}
        result = await route_node(state)
        assert "workflow_recipe" in result
        assert result["workflow_recipe"]["name"] == "submit_contract_approval"

    @pytest.mark.asyncio
    async def test_contract_approval_recipe_alt(self):
        from unittest.mock import MagicMock

        from langchain_core.messages import HumanMessage

        from app.agent.router import route_node
        config = MagicMock()
        config.get_model_for_complexity.return_value = "gpt-4o-mini"
        state = {"messages": [HumanMessage(content="发起协议核准")], "config": config}
        result = await route_node(state)
        assert "workflow_recipe" in result
        assert result["workflow_recipe"]["name"] == "submit_contract_approval"

    @pytest.mark.asyncio
    async def test_onboard_employee_recipe(self):
        from unittest.mock import MagicMock

        from langchain_core.messages import HumanMessage

        from app.agent.router import route_node
        config = MagicMock()
        config.get_model_for_complexity.return_value = "gpt-4o-mini"
        state = {"messages": [HumanMessage(content="给新员工办理入职")], "config": config}
        result = await route_node(state)
        assert "workflow_recipe" in result
        assert result["workflow_recipe"]["name"] == "onboard_employee"

    @pytest.mark.asyncio
    async def test_no_recipe_matched(self):
        from unittest.mock import MagicMock

        from langchain_core.messages import HumanMessage

        from app.agent.router import route_node
        config = MagicMock()
        config.get_model_for_complexity.return_value = "gpt-4o-mini"
        state = {"messages": [HumanMessage(content="查询天气")], "config": config}
        result = await route_node(state)
        assert "workflow_recipe" not in result
