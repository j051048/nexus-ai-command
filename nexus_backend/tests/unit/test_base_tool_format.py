"""
P0-2: BaseTool.format_result 标准化输出测试

验证 format_result 静态方法输出结构一致性。
"""

from app.tools.base_tool import BaseTool


class TestFormatResult:

    def test_basic_output_structure(self):
        """基本输出结构包含 data/summary/actions"""
        result = BaseTool.format_result(
            data={"customers": [{"id": 1, "name": "测试"}]},
            summary="找到 1 个客户",
        )
        assert "data" in result
        assert "summary" in result
        assert "actions" in result
        assert result["summary"] == "找到 1 个客户"
        assert result["actions"] == []

    def test_with_actions(self):
        """带推荐操作的输出"""
        actions = [
            {"label": "查看详情", "tool": "get_customer_detail", "args": {"id": "123"}},
            {"label": "添加跟进", "tool": "add_follow_up", "args": {"customer_id": "123"}},
        ]
        result = BaseTool.format_result(
            data={"name": "张三"},
            summary="客户信息已获取",
            actions=actions,
        )
        assert len(result["actions"]) == 2
        assert result["actions"][0]["tool"] == "get_customer_detail"

    def test_none_data(self):
        """data 为 None 的场景"""
        result = BaseTool.format_result(data=None, summary="无结果")
        assert result["data"] is None
        assert result["summary"] == "无结果"

    def test_list_data(self):
        """data 为列表"""
        items = [{"id": i} for i in range(5)]
        result = BaseTool.format_result(data=items, summary="返回5条记录")
        assert len(result["data"]) == 5

    def test_empty_actions_default(self):
        """不传 actions 默认为空列表"""
        result = BaseTool.format_result(data={}, summary="ok")
        assert isinstance(result["actions"], list)
        assert len(result["actions"]) == 0


class TestBasetoolCategory:

    def test_category_falls_back_to_domain(self):
        """category 属性回退到 domain"""
        from unittest.mock import MagicMock
        tool = MagicMock(spec=BaseTool)
        # 直接测试属性逻辑
        # 因为 category 是 property，我们通过实际子类测试
        from app.tools import _load_all, get_tool
        _load_all()
        crm_tool = get_tool("get_customers")
        assert crm_tool is not None
        assert crm_tool.category == "crm"

    def test_category_general_fallback(self):
        """无 domain 时回退到 general"""
        from app.tools import _load_all, get_tool
        _load_all()
        # compact_context 没有 domain
        tool = get_tool("compact_context")
        if tool is not None:
            assert tool.category in ("general", tool.domain or "general")
