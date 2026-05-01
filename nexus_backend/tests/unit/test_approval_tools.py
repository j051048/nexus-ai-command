"""
审批工具层测试

覆盖 approval_tools.py 中 4 个核心审批工具:
- PendingApprovalsTool: 空列表 / 正常列表 / 审批链信息
- ApprovalTool: 预览模式 / 无效UUID / 已处理幂等 / 经理权限上限
- RejectTool: 预览模式 / 无效UUID / 缺少reason / 已处理幂等
- GetEmployeeApprovalHistoryTool: 正常 / 无效UUID / 空记录
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FAKE_USER_ID = str(uuid.uuid4())
FAKE_ORG_ID = "org-test-001"
FAKE_REQ_ID = str(uuid.uuid4())
CONFIG = {"org_id": FAKE_ORG_ID, "token": None}


def _mock_db():
    """通用 supabase mock 链"""
    m = MagicMock()
    m.table.return_value = m
    m.select.return_value = m
    m.insert.return_value = m
    m.update.return_value = m
    m.delete.return_value = m
    m.eq.return_value = m
    m.neq.return_value = m
    m.in_.return_value = m
    m.ilike.return_value = m
    m.or_.return_value = m
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
#  PendingApprovalsTool 测试
# ═══════════════════════════════════════════════════════════════


class TestPendingApprovalsTool:

    @pytest.mark.asyncio
    async def test_no_pending(self):
        """无待审批项"""
        tool = _load_tool("get_pending_approvals")
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=[]))

        with patch("app.tools.approval_tools._get_client", return_value=db):
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "没有任何待处理" in result

    @pytest.mark.asyncio
    async def test_returns_pending_list(self):
        """正常返回待审批列表"""
        tool = _load_tool("get_pending_approvals")
        pending = [
            {"id": FAKE_REQ_ID, "type": "expense", "amount": 3000,
             "description": "差旅报销", "users": {"name": "张三"}, "status": "pending"},
        ]
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=pending))

        with patch("app.tools.approval_tools._get_client", return_value=db):
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "张三" in result
        assert "expense" in result

    @pytest.mark.asyncio
    async def test_chain_info_shown(self):
        """审批链信息应在结果中展示"""
        tool = _load_tool("get_pending_approvals")
        pending = [
            {"id": FAKE_REQ_ID, "type": "purchase", "amount": 50000,
             "description": "采购", "users": {"name": "王五"}, "status": "pending",
             "chain_id": "chain-1", "current_step": 1, "approval_level": "director"},
        ]
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=pending))

        with patch("app.tools.approval_tools._get_client", return_value=db):
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "步骤2" in result
        assert "director" in result


# ═══════════════════════════════════════════════════════════════
#  ApprovalTool 测试
# ═══════════════════════════════════════════════════════════════


class TestApprovalTool:

    @pytest.mark.asyncio
    async def test_invalid_uuid(self):
        """无效 UUID"""
        tool = _load_tool("approve_request")
        result = await tool.run({"request_id": "bad-id"}, FAKE_USER_ID, CONFIG)
        assert "不是有效的UUID" in result['summary']

    @pytest.mark.asyncio
    async def test_preview_mode(self):
        """预览模式(confirm=false)应返回预览信息"""
        tool = _load_tool("approve_request")
        db = _mock_db()
        # 用户角色查询
        db.execute = AsyncMock(side_effect=[
            MagicMock(data={"role": "founder"}),  # user role
            MagicMock(data={"id": FAKE_REQ_ID, "type": "expense", "amount": 1000,
                            "status": "pending", "description": "办公用品",
                            "users": {"name": "李四"}, "created_at": "2026-04-01"}),  # fetch request
        ])

        with patch("app.tools.approval_tools._get_client", return_value=db):
            result = await tool.run({"request_id": FAKE_REQ_ID, "confirm": False}, FAKE_USER_ID, CONFIG)
        assert "审批预览" in result['summary']
        assert "李四" in result['summary']

    @pytest.mark.asyncio
    async def test_already_processed(self):
        """已处理的审批单应返回幂等提示"""
        tool = _load_tool("approve_request")
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            MagicMock(data={"role": "founder"}),  # user role
            MagicMock(data={"id": FAKE_REQ_ID, "status": "approved",
                            "type": "expense", "amount": 100, "users": {"name": "X"}}),
        ])

        with patch("app.tools.approval_tools._get_client", return_value=db):
            result = await tool.run({"request_id": FAKE_REQ_ID, "confirm": True}, FAKE_USER_ID, CONFIG)
        assert "已被处理" in result['summary']

    @pytest.mark.asyncio
    async def test_manager_limit(self):
        """经理审批超5000应被拦截"""
        tool = _load_tool("approve_request")
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            MagicMock(data={"role": "manager"}),  # user role = manager
            MagicMock(data={"amount": 10000}),  # request amount
        ])

        with patch("app.tools.approval_tools._get_client", return_value=db):
            result = await tool.run({"request_id": FAKE_REQ_ID}, FAKE_USER_ID, CONFIG)
        assert "权限不足" in result['summary']
        assert "5,000" in result['summary']


# ═══════════════════════════════════════════════════════════════
#  RejectTool 测试
# ═══════════════════════════════════════════════════════════════


class TestRejectTool:

    @pytest.mark.asyncio
    async def test_invalid_uuid(self):
        tool = _load_tool("reject_request")
        result = await tool.run({"request_id": "xxx", "reason": "不合理"}, FAKE_USER_ID, CONFIG)
        assert "不是有效的UUID" in result['summary']

    @pytest.mark.asyncio
    async def test_preview_mode(self):
        tool = _load_tool("reject_request")
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            MagicMock(data={"role": "founder"}),
            MagicMock(data={"id": FAKE_REQ_ID, "status": "pending", "type": "travel",
                            "amount": 5000, "description": "出差", "users": {"name": "陈六"}}),
        ])

        with patch("app.tools.approval_tools._get_client", return_value=db):
            result = await tool.run({"request_id": FAKE_REQ_ID, "reason": "超预算", "confirm": False}, FAKE_USER_ID, CONFIG)
        assert "驳回预览" in result['summary']
        assert "超预算" in result['summary']

    @pytest.mark.asyncio
    async def test_already_processed(self):
        tool = _load_tool("reject_request")
        db = _mock_db()
        db.execute = AsyncMock(side_effect=[
            MagicMock(data={"role": "founder"}),
            MagicMock(data={"id": FAKE_REQ_ID, "status": "rejected", "type": "x", "amount": 0, "users": {}}),
        ])

        with patch("app.tools.approval_tools._get_client", return_value=db):
            result = await tool.run({"request_id": FAKE_REQ_ID, "reason": "x", "confirm": True}, FAKE_USER_ID, CONFIG)
        assert "已被处理" in result['summary']


# ═══════════════════════════════════════════════════════════════
#  GetEmployeeApprovalHistoryTool 测试
# ═══════════════════════════════════════════════════════════════


class TestGetEmployeeApprovalHistoryTool:

    @pytest.mark.asyncio
    async def test_invalid_uuid(self):
        tool = _load_tool("get_employee_approval_history")
        result = await tool.run({"employee_id": "not-uuid"}, FAKE_USER_ID, CONFIG)
        assert "不是有效的UUID" in result['summary']

    @pytest.mark.asyncio
    async def test_empty_history(self):
        tool = _load_tool("get_employee_approval_history")
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=[]))

        with patch("app.tools.approval_tools._get_client", return_value=db):
            result = await tool.run({"employee_id": FAKE_USER_ID}, FAKE_USER_ID, CONFIG)
        assert "暂无审批记录" in result['summary']

    @pytest.mark.asyncio
    async def test_returns_history(self):
        tool = _load_tool("get_employee_approval_history")
        records = [
            {"status": "approved", "type": "expense", "amount": 800,
             "description": "打车报销", "submitted_via": "ai_assistant"},
            {"status": "pending", "type": "travel", "amount": 3000,
             "description": "上海出差"},
        ]
        db = _mock_db()
        db.execute = AsyncMock(return_value=MagicMock(data=records))

        with patch("app.tools.approval_tools._get_client", return_value=db):
            result = await tool.run({"employee_id": FAKE_USER_ID, "limit": 2}, FAKE_USER_ID, CONFIG)
        assert "条审批记录" in result['summary']
        # submitted_via="ai_assistant" 详情在 data 中
        assert any(r.get("submitted_via") == "ai_assistant" for r in result['data'])

class TestUrgeApprovalTool:
    @pytest.mark.asyncio
    async def test_urge_approval(self):
        tool = _load_tool("urge_approval")
        with patch("app.tools.approval_tools.ApprovalService", create=True) as mock_service:
            with patch("app.services.approval_service.ApprovalService.urge_approval", new_callable=AsyncMock) as mock_method:
                mock_method.return_value = {"message": "催办成功"}
                result = await tool.run({"request_id": FAKE_REQ_ID, "reason": "urgency"}, FAKE_USER_ID, CONFIG)
                assert "成功" in result or "催办" in result or "message" in result

    @pytest.mark.asyncio
    async def test_invalid_uuid(self):
        tool = _load_tool("urge_approval")
        result = await tool.run({"request_id": "not-uuid", "reason": "x"}, FAKE_USER_ID, CONFIG)
        assert "ID" in result or "UUID" in result

