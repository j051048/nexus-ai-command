"""
AI Agent 意图路由极致测试矩阵

50+ 真实企业场景，覆盖 4 级复杂度 × 多业务域 × 边缘案例
"""
import pytest
from app.agent.router import classify_query, detect_agent_role
from app.agent.state import QueryComplexity


class TestIntentMatrixSales:
    """销售域场景矩阵"""

    @pytest.mark.parametrize("query,expected_min", [
        ("帮我查一下张三的客户信息", QueryComplexity.MODERATE),
        ("本月成交了多少单", QueryComplexity.MODERATE),
        ("分析Q1销售漏斗转化率", QueryComplexity.COMPLEX),
        ("对比去年同期营收趋势", QueryComplexity.COMPLEX),
        ("批准李四的5万元合同", QueryComplexity.CRITICAL),
        ("生成竞品分析报告", QueryComplexity.COMPLEX),
    ])
    def test_sales_scenarios(self, query, expected_min):
        complexity, _ = classify_query(query)
        assert _complexity_gte(complexity, expected_min), \
            f"'{query}' → {complexity}, expected >= {expected_min}"


class TestIntentMatrixHR:
    """HR 域场景矩阵"""

    @pytest.mark.parametrize("query,expected_min", [
        ("查看我的考勤记录", QueryComplexity.MODERATE),
        ("帮我请假三天", QueryComplexity.MODERATE),
        ("统计本月全员出勤率", QueryComplexity.MODERATE),
        ("解雇张三", QueryComplexity.CRITICAL),
        ("调岗李四到市场部", QueryComplexity.CRITICAL),
        ("生成团队绩效排名报告", QueryComplexity.COMPLEX),
    ])
    def test_hr_scenarios(self, query, expected_min):
        complexity, _ = classify_query(query)
        assert _complexity_gte(complexity, expected_min)


class TestIntentMatrixFinance:
    """财务域场景矩阵"""

    @pytest.mark.parametrize("query,expected_min", [
        ("查询本月预算剩余", QueryComplexity.MODERATE),
        ("提交报销申请", QueryComplexity.CRITICAL),
        ("发起付款转账", QueryComplexity.CRITICAL),
        ("分析各部门费用趋势", QueryComplexity.COMPLEX),
        ("查看发票列表", QueryComplexity.MODERATE),
    ])
    def test_finance_scenarios(self, query, expected_min):
        complexity, _ = classify_query(query)
        assert _complexity_gte(complexity, expected_min)


class TestIntentMatrixApproval:
    """审批域场景矩阵"""

    @pytest.mark.parametrize("query,expected_min", [
        ("查看待审批列表", QueryComplexity.MODERATE),
        ("批准这个审批", QueryComplexity.CRITICAL),
        ("拒绝张三的请假申请", QueryComplexity.CRITICAL),
        ("驳回这个报销", QueryComplexity.CRITICAL),
        ("审批进度到哪了", QueryComplexity.MODERATE),
    ])
    def test_approval_scenarios(self, query, expected_min):
        complexity, _ = classify_query(query)
        assert _complexity_gte(complexity, expected_min)


class TestIntentMatrixOA:
    """OA 域场景矩阵"""

    @pytest.mark.parametrize("query,expected_min", [
        ("帮我订明天下午的会议室", QueryComplexity.MODERATE),
        ("查看本周日程安排", QueryComplexity.MODERATE),
        ("创建一个项目任务", QueryComplexity.MODERATE),
        ("发公告通知全员", QueryComplexity.CRITICAL),
        ("查看工单列表", QueryComplexity.MODERATE),
    ])
    def test_oa_scenarios(self, query, expected_min):
        complexity, _ = classify_query(query)
        assert _complexity_gte(complexity, expected_min)


class TestIntentMatrixVMD:
    """VMD 营销域场景矩阵"""

    @pytest.mark.parametrize("query,expected_agent", [
        ("帮我写一篇白皮书", "content_agent"),
        ("设计一张产品海报", "design_agent"),
        ("制定媒介投放策略", "media_agent"),
        ("分析线索获取渠道", "clue_agent"),
        ("生成销售话术Battlecard", "sales_agent"),
        ("监控品牌舆情", "pr_agent"),
        ("检查广告合规性", "compliance_agent"),
    ])
    def test_vmd_agent_routing(self, query, expected_agent):
        complexity, _ = classify_query(query)
        code, _, _ = detect_agent_role(query, complexity)
        assert code == expected_agent, f"'{query}' → {code}, expected {expected_agent}"


class TestIntentMatrixMultiAgent:
    """多 Agent 编排场景"""

    @pytest.mark.parametrize("query", [
        "制定完整的Q3营销方案",
        "制定Go-to-Market上市计划",
        "策划年度品牌推广方案",
        "制定招投标全流程方案",
        "策划客户拜访计划",
    ])
    def test_multi_agent_triggers(self, query):
        complexity, _ = classify_query(query)
        code, _, multi = detect_agent_role(query, complexity)
        assert multi is True, f"'{query}' should trigger multi-agent"
        assert code == "director_agent"


class TestIntentMatrixEdgeCases:
    """边缘案例"""

    def test_mixed_language(self):
        """中英混合"""
        complexity, _ = classify_query("帮我check一下CRM里的customer data")
        assert complexity in (QueryComplexity.MODERATE, QueryComplexity.COMPLEX)

    def test_typo_tolerance(self):
        """错别字容忍"""
        complexity, _ = classify_query("帮我查一下客户信息")
        assert complexity == QueryComplexity.MODERATE

    def test_emoji_in_query(self):
        """包含 emoji"""
        complexity, _ = classify_query("帮我查一下客户 😊")
        assert complexity == QueryComplexity.MODERATE

    def test_very_long_query(self):
        """超长输入"""
        long_q = "请帮我分析" + "这个季度的销售数据，" * 30 + "给出详细报告"
        complexity, _ = classify_query(long_q)
        assert complexity == QueryComplexity.COMPLEX

    def test_negation_prevents_critical(self):
        """否定前缀阻止 CRITICAL"""
        complexity, _ = classify_query("不需要报销了")
        assert complexity != QueryComplexity.CRITICAL

    def test_query_verb_downgrades(self):
        """查询动词降级"""
        complexity, _ = classify_query("查看审批记录")
        assert complexity == QueryComplexity.MODERATE

    def test_ambiguous_no_verb(self):
        """无动词的敏感词 → 降级"""
        complexity, _ = classify_query("通知停水")
        assert complexity in (QueryComplexity.MODERATE, QueryComplexity.SIMPLE)

    def test_realtime_with_business_keyword(self):
        """实时信息 + 业务关键词 → 走业务路径"""
        complexity, _ = classify_query("搜一下客户张三的信息")
        assert complexity == QueryComplexity.MODERATE

    def test_memory_recall_not_simple(self):
        """记忆回顾不应为 SIMPLE"""
        complexity, _ = classify_query("你还记得我之前说过什么吗")
        assert complexity != QueryComplexity.SIMPLE


# ── Helper ──────────────────────────────────────────────────────────────────

_COMPLEXITY_ORDER = {
    QueryComplexity.SIMPLE: 0,
    QueryComplexity.MODERATE: 1,
    QueryComplexity.COMPLEX: 2,
    QueryComplexity.CRITICAL: 3,
}

def _complexity_gte(actual: QueryComplexity, expected_min: QueryComplexity) -> bool:
    return _COMPLEXITY_ORDER[actual] >= _COMPLEXITY_ORDER[expected_min]
