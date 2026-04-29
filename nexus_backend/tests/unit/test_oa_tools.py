"""
OA 办公自动化工具集测试

覆盖 oa_tools.py 中 4 个核心工具类的业务逻辑:
- LeaveRequestTool: 创建请假 / 日期校验 / 年假余额 / 重复检测 / 审批链
- LeaveQueryTool: 查询请假记录 / 假期余额
- MeetingBookingTool: 预约会议 / 冲突检测 / 参会人查找
- TaskAssignmentTool: 分配任务 / 负责人查找 / 通知发送
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── helpers ────────────────────────────────────────────────

FAKE_ORG_ID = "org-oa-test-001"
FAKE_USER_ID = "user-oa-test-001"
FAKE_LEAVE_ID = str(uuid.uuid4())

CONFIG = {"org_id": FAKE_ORG_ID, "token": None}


def _tomorrow():
    """返回明天的日期字符串"""
    return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


def _day_after_tomorrow():
    """返回后天的日期字符串"""
    return (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")


def _load_tool(name: str):
    from app.tools import _load_all, get_tool
    _load_all()
    tool = get_tool(name)
    assert tool is not None, f"工具 {name} 未注册"
    return tool


def _mock_db_chain():
    """构建通用的 supabase mock 链式调用"""
    mock = MagicMock()
    mock.table.return_value = mock
    mock.select.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.delete.return_value = mock
    mock.eq.return_value = mock
    mock.in_.return_value = mock
    mock.lte.return_value = mock
    mock.gte.return_value = mock
    mock.ilike.return_value = mock
    mock.or_.return_value = mock
    mock.order.return_value = mock
    mock.limit.return_value = mock
    mock.maybe_single.return_value = mock
    mock.rpc.return_value = mock
    return mock


# ═══════════════════════════════════════════════════════════════
#  LeaveRequestTool 测试
# ═══════════════════════════════════════════════════════════════


class TestLeaveRequestTool:
    """创建请假申请工具"""

    @pytest.mark.asyncio
    async def test_invalid_date_past_year(self):
        """过去年份的日期应被拒绝"""
        tool = _load_tool("create_leave_request")
        mock = _mock_db_chain()

        with patch("app.tools.oa_tools._get_client", return_value=mock):
            result = await tool.run(
                {
                    "leave_type": "annual",
                    "start_date": "2020-01-01",
                    "end_date": "2020-01-03",
                },
                FAKE_USER_ID,
                CONFIG,
            )

        assert "日期异常" in result

    @pytest.mark.asyncio
    async def test_end_before_start(self):
        """结束日期早于开始日期应被拒绝"""
        tool = _load_tool("create_leave_request")
        mock = _mock_db_chain()

        with patch("app.tools.oa_tools._get_client", return_value=mock):
            result = await tool.run(
                {
                    "leave_type": "personal",
                    "start_date": _day_after_tomorrow(),
                    "end_date": _tomorrow(),
                },
                FAKE_USER_ID,
                CONFIG,
            )

        assert "不能早于" in result

    @pytest.mark.asyncio
    async def test_invalid_date_format(self):
        """非法日期格式应返回错误提示"""
        tool = _load_tool("create_leave_request")
        mock = _mock_db_chain()

        with patch("app.tools.oa_tools._get_client", return_value=mock):
            result = await tool.run(
                {
                    "leave_type": "annual",
                    "start_date": "not-a-date",
                    "end_date": "2026-13-45",
                },
                FAKE_USER_ID,
                CONFIG,
            )

        assert "日期格式错误" in result or "YYYY-MM-DD" in result

    @pytest.mark.asyncio
    async def test_annual_leave_balance_exceeded(self):
        """年假余额不足时应被拒绝"""
        tool = _load_tool("create_leave_request")

        start = _tomorrow()
        # 申请20天年假（超过默认10天额度）
        end = (datetime.now() + timedelta(days=20)).strftime("%Y-%m-%d")

        with patch("app.tools.oa_tools._get_client") as mock_gc:
            client = MagicMock()
            mock_gc.return_value = client

            table_mock = MagicMock()
            client.table.return_value = table_mock
            table_mock.select.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.in_.return_value = table_mock
            table_mock.lte.return_value = table_mock
            table_mock.gte.return_value = table_mock
            table_mock.order.return_value = table_mock
            table_mock.limit.return_value = table_mock
            table_mock.maybe_single.return_value = table_mock

            # 按实际代码调用顺序设置 side_effect:
            # 1. 用户信息查询 (maybe_single)
            # 2. 重复请假检查
            # 3. 年假已用天数查询 → 返回列表，每项是 dict
            table_mock.execute = AsyncMock(
                side_effect=[
                    MagicMock(data={"name": "测试用户", "department": "技术部", "role": "employee"}),
                    MagicMock(data=[]),  # 无重复
                    MagicMock(data=[{"days": 5}, {"days": 3}]),  # 已用8天
                ]
            )

            result = await tool.run(
                {
                    "leave_type": "annual",
                    "start_date": start,
                    "end_date": end,
                },
                FAKE_USER_ID,
                CONFIG,
            )

        assert "余额不足" in result or "剩余" in result

    @pytest.mark.asyncio
    async def test_successful_leave_creates_record(self):
        """成功创建请假应返回确认信息"""
        tool = _load_tool("create_leave_request")
        start = _tomorrow()
        end = _day_after_tomorrow()

        with patch("app.tools.oa_tools._get_client") as mock_gc:
            client = MagicMock()
            mock_gc.return_value = client

            table_mock = MagicMock()
            client.table.return_value = table_mock
            table_mock.select.return_value = table_mock
            table_mock.insert.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.in_.return_value = table_mock
            table_mock.lte.return_value = table_mock
            table_mock.gte.return_value = table_mock
            table_mock.ilike.return_value = table_mock
            table_mock.order.return_value = table_mock
            table_mock.limit.return_value = table_mock
            table_mock.maybe_single.return_value = table_mock

            table_mock.execute = AsyncMock(
                side_effect=[
                    # 1. 用户信息
                    MagicMock(data={"name": "张三", "department": "技术部", "role": "employee"}),
                    # 2. 重复检查 - 无重复
                    MagicMock(data=[]),
                    # 3. 获取 org_id
                    MagicMock(data={"organization_id": FAKE_ORG_ID}),
                    # 4. 插入请假记录
                    MagicMock(data=[{"id": FAKE_LEAVE_ID}]),
                    # 5. 插入审批记录
                    MagicMock(data=[{"id": str(uuid.uuid4())}]),
                    # 6. 日历同步
                    MagicMock(data=[{"id": str(uuid.uuid4())}]),
                ]
            )

            with patch(
                "app.services.approval_chain.approval_chain_service.match_and_bind_chain",
                new_callable=AsyncMock,
                return_value={
                    "auto_approve": True,
                    "chain_id": None,
                    "starting_step": 0,
                    "approval_level": "auto",
                    "timeout_at": None,
                    "chain_name": "自动批准",
                },
            ):
                result = await tool.run(
                    {
                        "leave_type": "sick",
                        "start_date": start,
                        "end_date": end,
                        "reason": "身体不适",
                    },
                    FAKE_USER_ID,
                    CONFIG,
                )

        assert "申请已提交" in result or "✅" in result


# ═══════════════════════════════════════════════════════════════
#  LeaveQueryTool 测试
# ═══════════════════════════════════════════════════════════════


class TestLeaveQueryTool:
    """查询请假状态工具"""

    @pytest.mark.asyncio
    async def test_query_my_requests(self):
        """正常查询请假记录"""
        tool = _load_tool("query_leave_status")

        with patch("app.tools.oa_tools._get_client") as mock_gc:
            client = MagicMock()
            mock_gc.return_value = client

            table_mock = MagicMock()
            client.table.return_value = table_mock
            table_mock.select.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.order.return_value = table_mock
            table_mock.limit.return_value = table_mock

            table_mock.execute = AsyncMock(
                return_value=MagicMock(
                    data=[
                        {
                            "type": "annual",
                            "days": 3,
                            "start_date": "2026-04-01",
                            "end_date": "2026-04-03",
                            "status": "approved",
                        },
                        {
                            "type": "sick",
                            "days": 1,
                            "start_date": "2026-04-10",
                            "end_date": "2026-04-10",
                            "status": "pending",
                        },
                    ]
                )
            )

            result = await tool.run(
                {"query_type": "my_requests"}, FAKE_USER_ID, CONFIG
            )

        assert "请假记录" in result
        assert "年假" in result
        assert "病假" in result

    @pytest.mark.asyncio
    async def test_query_empty_records(self):
        """无请假记录时返回提示"""
        tool = _load_tool("query_leave_status")

        with patch("app.tools.oa_tools._get_client") as mock_gc:
            client = MagicMock()
            mock_gc.return_value = client

            table_mock = MagicMock()
            client.table.return_value = table_mock
            table_mock.select.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.order.return_value = table_mock
            table_mock.limit.return_value = table_mock

            table_mock.execute = AsyncMock(return_value=MagicMock(data=[]))

            result = await tool.run(
                {"query_type": "my_requests"}, FAKE_USER_ID, CONFIG
            )

        res_str = str(result)
        assert "没有请假记录" in res_str or "暂无" in res_str

    @pytest.mark.asyncio
    async def test_query_balance(self):
        """查询假期余额"""
        tool = _load_tool("query_leave_status")

        with patch("app.tools.oa_tools._get_client") as mock_gc:
            client = MagicMock()
            mock_gc.return_value = client

            table_mock = MagicMock()
            client.table.return_value = table_mock
            table_mock.select.return_value = table_mock
            table_mock.eq.return_value = table_mock

            # 已使用3天年假
            table_mock.execute = AsyncMock(
                return_value=MagicMock(data=[{"days": 2}, {"days": 1}])
            )

            result = await tool.run(
                {"query_type": "balance"}, FAKE_USER_ID, CONFIG
            )

        assert "假期余额" in result or "年假" in result
        assert "7" in result  # 10 - 3 = 7


# ═══════════════════════════════════════════════════════════════
#  MeetingBookingTool 测试
# ═══════════════════════════════════════════════════════════════


class TestMeetingBookingTool:
    """会议预约工具"""

    @pytest.mark.asyncio
    async def test_book_meeting_success(self):
        """成功预约会议"""
        tool = _load_tool("book_meeting")

        with patch("app.tools.oa_tools._get_client") as mock_gc:
            client = MagicMock()
            mock_gc.return_value = client

            table_mock = MagicMock()
            client.table.return_value = table_mock
            table_mock.select.return_value = table_mock
            table_mock.insert.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.ilike.return_value = table_mock
            table_mock.limit.return_value = table_mock

            # RPC 冲突检测 - 无冲突
            rpc_mock = MagicMock()
            client.rpc.return_value = rpc_mock
            rpc_mock.execute = AsyncMock(return_value=MagicMock(data=[]))

            # 查找参会人 + 插入
            table_mock.execute = AsyncMock(
                side_effect=[
                    # 1. 查找参会人"张三"
                    MagicMock(data=[{"id": "user-zs", "name": "张三"}]),
                    # 2. 插入会议记录
                    MagicMock(data=[{"id": str(uuid.uuid4())}]),
                    # 3. 日历同步
                    MagicMock(data=[{"id": str(uuid.uuid4())}]),
                ]
            )

            with patch("app.tools.oa_tools.notification_service") as mock_notif:
                mock_notif.send = AsyncMock()

                result = await tool.run(
                    {
                        "title": "产品评审会",
                        "datetime": (datetime.now() + timedelta(days=1))
                        .replace(hour=15, minute=0)
                        .isoformat(),
                        "attendees": ["张三"],
                        "room_preference": "medium",
                    },
                    FAKE_USER_ID,
                    CONFIG,
                )

        assert "预约成功" in result or "✅" in result
        assert "产品评审会" in result

    @pytest.mark.asyncio
    async def test_meeting_time_fallback(self):
        """无效时间格式自动降级为明天下午"""
        tool = _load_tool("book_meeting")

        with patch("app.tools.oa_tools._get_client") as mock_gc:
            client = MagicMock()
            mock_gc.return_value = client

            table_mock = MagicMock()
            client.table.return_value = table_mock
            table_mock.select.return_value = table_mock
            table_mock.insert.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.ilike.return_value = table_mock
            table_mock.limit.return_value = table_mock

            rpc_mock = MagicMock()
            client.rpc.return_value = rpc_mock
            rpc_mock.execute = AsyncMock(return_value=MagicMock(data=[]))

            table_mock.execute = AsyncMock(
                side_effect=[
                    MagicMock(data=[]),  # 无参会人
                    MagicMock(data=[{"id": str(uuid.uuid4())}]),  # 插入
                    MagicMock(data=[{"id": str(uuid.uuid4())}]),  # 日历同步
                ]
            )

            with patch("app.tools.oa_tools.notification_service"):
                result = await tool.run(
                    {
                        "title": "临时会议",
                        "datetime": "invalid-date-format",
                        "attendees": [],
                    },
                    FAKE_USER_ID,
                    CONFIG,
                )

        # 应该成功（降级为默认时间），不应报错
        assert "✅" in result or "预约" in result


# ═══════════════════════════════════════════════════════════════
#  TaskAssignmentTool 测试
# ═══════════════════════════════════════════════════════════════


class TestTaskAssignmentTool:
    """任务分配工具"""

    @pytest.mark.asyncio
    async def test_assign_task_success(self):
        """成功分配任务"""
        tool = _load_tool("assign_task")

        with patch("app.tools.oa_tools._get_client") as mock_gc:
            client = MagicMock()
            mock_gc.return_value = client

            table_mock = MagicMock()
            client.table.return_value = table_mock
            table_mock.select.return_value = table_mock
            table_mock.insert.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.ilike.return_value = table_mock
            table_mock.limit.return_value = table_mock
            table_mock.maybe_single.return_value = table_mock

            table_mock.execute = AsyncMock(
                side_effect=[
                    # 1. 查找负责人
                    MagicMock(data=[{"id": "user-ls", "name": "李四"}]),
                    # 2. 获取创建者信息
                    MagicMock(data={"name": "张三", "organization_id": FAKE_ORG_ID}),
                    # 3. 插入任务
                    MagicMock(data=[{"id": str(uuid.uuid4())}]),
                ]
            )

            with patch("app.tools.oa_tools.notification_service") as mock_notif:
                mock_notif.send = AsyncMock()

                result = await tool.run(
                    {
                        "title": "准备Q2报告",
                        "assignee": "李四",
                        "priority": "high",
                    },
                    FAKE_USER_ID,
                    CONFIG,
                )

        assert "准备Q2报告" in result
        assert "李四" in result

    @pytest.mark.asyncio
    async def test_assignee_not_found(self):
        """找不到负责人时返回错误"""
        tool = _load_tool("assign_task")

        with patch("app.tools.oa_tools._get_client") as mock_gc:
            client = MagicMock()
            mock_gc.return_value = client

            table_mock = MagicMock()
            client.table.return_value = table_mock
            table_mock.select.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.ilike.return_value = table_mock
            table_mock.limit.return_value = table_mock

            # 查不到负责人
            table_mock.execute = AsyncMock(return_value=MagicMock(data=[]))

            result = await tool.run(
                {"title": "某任务", "assignee": "不存在的人"},
                FAKE_USER_ID,
                CONFIG,
            )

        assert "找不到" in result or "❌" in result

    @pytest.mark.asyncio
    async def test_default_due_date(self):
        """未指定截止日期时默认3天后"""
        tool = _load_tool("assign_task")

        inserted_data = {}

        with patch("app.tools.oa_tools._get_client") as mock_gc:
            client = MagicMock()
            mock_gc.return_value = client

            table_mock = MagicMock()
            client.table.return_value = table_mock
            table_mock.select.return_value = table_mock
            table_mock.eq.return_value = table_mock
            table_mock.ilike.return_value = table_mock
            table_mock.limit.return_value = table_mock
            table_mock.maybe_single.return_value = table_mock

            # 使 insert 可被 await
            insert_mock = MagicMock()
            insert_mock.execute = AsyncMock(
                return_value=MagicMock(data=[{"id": str(uuid.uuid4())}])
            )

            def capture_insert(data):
                inserted_data.update(data)
                return insert_mock

            table_mock.insert = capture_insert

            table_mock.execute = AsyncMock(
                side_effect=[
                    MagicMock(data=[{"id": "user-ls", "name": "李四"}]),
                    MagicMock(data={"name": "张三", "organization_id": FAKE_ORG_ID}),
                ]
            )

            with patch("app.tools.oa_tools.notification_service") as mock_notif:
                mock_notif.send = AsyncMock()

                await tool.run(
                    {"title": "某任务", "assignee": "李四"},
                    FAKE_USER_ID,
                    CONFIG,
                )

        # 验证默认截止日期是3天后
        expected_due = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        assert inserted_data.get("due_date") == expected_due
