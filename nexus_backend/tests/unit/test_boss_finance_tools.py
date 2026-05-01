"""
Boss & Finance 工具层测试

覆盖 Top 10 中的剩余工具:
- SmartApprovalTool: 空列表 / 预览模式 / 条件筛选 / 批量上限
- DailyBriefingTool: 正常简报 / 无待审批
- BudgetQueryTool: 正常 / 无用户信息
- WebSearchTool: 空query / 未配置API Key / 超时 / 空结果
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FAKE_USER_ID = str(uuid.uuid4())
CONFIG = {"org_id": "org-test-001", "token": None}


def _mock_db():
    m = MagicMock()
    m.table.return_value = m
    m.select.return_value = m
    m.insert.return_value = m
    m.update.return_value = m
    m.eq.return_value = m
    m.neq.return_value = m
    m.in_.return_value = m
    m.ilike.return_value = m
    m.gte.return_value = m
    m.lte.return_value = m
    m.lt.return_value = m
    m.order.return_value = m
    m.limit.return_value = m
    m.single.return_value = m
    m.maybe_single.return_value = m
    m.rpc.return_value = m
    return m


def _load_tool(name: str):
    from app.tools import _load_all, get_tool
    _load_all()
    tool = get_tool(name)
    assert tool is not None, f"工具 {name} 未注册"
    return tool


# ═══════════════════════════════════════════════════════════════
#  SmartApprovalTool 测试
# ═══════════════════════════════════════════════════════════════


class TestSmartApprovalTool:

    @pytest.mark.asyncio
    async def test_no_pending(self):
        """无待审批事项"""
        tool = _load_tool("smart_approve")
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=[]))

        with patch("app.tools.boss_tools.smart_approval._get_client", return_value=db):
            result = await tool.run({"action": "batch_approve"}, FAKE_USER_ID, CONFIG)
        assert "没有待审批" in result["summary"]

    @pytest.mark.asyncio
    async def test_preview_mode(self):
        """预览模式返回汇总信息"""
        tool = _load_tool("smart_approve")
        pending = [
            {"id": str(uuid.uuid4()), "type": "expense", "amount": 2000,
             "submitted_by": "u1", "users": {"name": "张三"}, "status": "pending"},
            {"id": str(uuid.uuid4()), "type": "travel", "amount": 5000,
             "submitted_by": "u2", "users": {"name": "李四"}, "status": "pending"},
        ]
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=pending))

        with patch("app.tools.boss_tools.smart_approval._get_client", return_value=db):
            result = await tool.run({"action": "batch_approve", "confirm": False}, FAKE_USER_ID, CONFIG)
        assert "批量批准预览" in result["summary"]
        assert "2" in result["summary"]
        assert "7,000" in result["summary"]

    @pytest.mark.asyncio
    async def test_conditional_filter(self):
        """条件筛选 - 金额小于5000"""
        tool = _load_tool("smart_approve")
        pending = [
            {"id": str(uuid.uuid4()), "type": "expense", "amount": 2000,
             "submitted_by": "u1", "users": {"name": "A"}, "status": "pending"},
            {"id": str(uuid.uuid4()), "type": "purchase", "amount": 50000,
             "submitted_by": "u2", "users": {"name": "B"}, "status": "pending"},
        ]
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=pending))

        with patch("app.tools.boss_tools.smart_approval._get_client", return_value=db):
            result = await tool.run({
                "action": "conditional_approve",
                "condition": "金额小于5000的全部通过",
                "confirm": False,
            }, FAKE_USER_ID, CONFIG)
        # 应该只筛选出1条
        assert "1" in result["summary"]

    @pytest.mark.asyncio
    async def test_batch_size_limit(self):
        """超出批量上限"""
        tool = _load_tool("smart_approve")
        pending = [
            {"id": str(uuid.uuid4()), "type": "expense", "amount": 100,
             "submitted_by": f"u{i}", "users": {"name": f"U{i}"}, "status": "pending"}
            for i in range(15)
        ]
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=pending))

        with patch("app.tools.boss_tools.smart_approval._get_client", return_value=db):
            result = await tool.run({"action": "batch_approve", "confirm": True}, FAKE_USER_ID, CONFIG)
        assert "安全限制" in result["summary"]

    @pytest.mark.asyncio
    async def test_delegate_no_target(self):
        """委托审批未指定委托人"""
        tool = _load_tool("smart_approve")
        pending = [{"id": str(uuid.uuid4()), "type": "expense", "amount": 100,
                     "submitted_by": "u1", "users": {"name": "X"}, "status": "pending"}]
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=pending))

        with patch("app.tools.boss_tools.smart_approval._get_client", return_value=db):
            result = await tool.run({"action": "delegate", "confirm": True}, FAKE_USER_ID, CONFIG)
        assert "请指定委托人" in result


# ═══════════════════════════════════════════════════════════════
#  DailyBriefingTool 测试
# ═══════════════════════════════════════════════════════════════


class TestDailyBriefingTool:

    @pytest.mark.asyncio
    async def test_no_pending_items(self):
        """无待审批时显示轻松提示"""
        tool = _load_tool("get_daily_briefing")
        db = _mock_db()
        # 每个 .execute() 调用返回空
        db.execute = AsyncMock(return_value=MagicMock(data=[], count=0))

        with patch("app.tools.boss_tools.daily_briefing._get_client", return_value=db):
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        # 实际输出: "🎉 **太棒了！当前没有待处理事项**"
        assert "没有待处理事项" in result


# ═══════════════════════════════════════════════════════════════
#  BudgetQueryTool 测试
# ═══════════════════════════════════════════════════════════════


class TestBudgetQueryTool:

    @pytest.mark.asyncio
    async def test_placeholder_response(self):
        """预算功能尚在建设中"""
        tool = _load_tool("query_budget")
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data={"department": "销售部", "role": "manager"}))

        with patch("app.tools.finance_tools._get_client", return_value=db):
            result = await tool.run({"department": "销售部"}, FAKE_USER_ID, CONFIG)
        assert "暂无预算数据" in result

    @pytest.mark.asyncio
    async def test_no_user_info(self):
        """无法获取用户信息"""
        tool = _load_tool("query_budget")
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=None))

        with patch("app.tools.finance_tools._get_client", return_value=db):
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "无法获取用户信息" in result


# ═══════════════════════════════════════════════════════════════
#  WebSearchTool 测试
# ═══════════════════════════════════════════════════════════════


class TestWebSearchTool:

    @pytest.mark.asyncio
    async def test_empty_query(self):
        """空查询"""
        tool = _load_tool("web_search")
        result = await tool.run({"query": ""}, FAKE_USER_ID, CONFIG)
        assert "请提供搜索关键词" in result["summary"]

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        """未配置 API Key"""
        tool = _load_tool("web_search")
        with patch("app.tools.web_search_tool.settings") as mock_settings:
            mock_settings.BRAVE_SEARCH_API_KEY = ""
            result = await tool.run({"query": "测试搜索"}, FAKE_USER_ID, CONFIG)
        assert "未配置" in result["summary"]

    @pytest.mark.asyncio
    async def test_timeout(self):
        """搜索超时"""
        import httpx
        tool = _load_tool("web_search")

        with patch("app.tools.web_search_tool.settings") as mock_settings, \
             patch("httpx.AsyncClient") as MockClient:
            mock_settings.BRAVE_SEARCH_API_KEY = "test-key"
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.TimeoutException("timeout")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance

            # 清除缓存以避免命中
            from app.tools.web_search_tool import _CACHE
            _CACHE.clear()

            result = await tool.run({"query": "超时测试"}, FAKE_USER_ID, CONFIG)
        assert "超时" in result["summary"]

    @pytest.mark.asyncio
    async def test_empty_results(self):
        """搜索无结果"""
        tool = _load_tool("web_search")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("app.tools.web_search_tool.settings") as mock_settings, \
             patch("httpx.AsyncClient") as MockClient:
            mock_settings.BRAVE_SEARCH_API_KEY = "test-key"
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            MockClient.return_value = mock_instance

            from app.tools.web_search_tool import _CACHE
            _CACHE.clear()

            result = await tool.run({"query": "不存在的关键词xyz"}, FAKE_USER_ID, CONFIG)
        assert "未找到相关结果" in result["summary"]
