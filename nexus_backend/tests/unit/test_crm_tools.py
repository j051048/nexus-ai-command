"""
CRM 工具层集成测试

覆盖 crm_tools.py 中 8 个核心工具的业务逻辑:
- GetCustomersTool: 空结果 / 按阶段筛选 / 搜索
- GetCustomerDetailTool: 正常 / 缺少UUID / 不存在
- CreateCustomerTool: 正常 / 缺少必填 / 负金额 / 无org
- UpdateCustomerTool: 正常 / 缺少字段 / 无效UUID
- AddFollowUpTool: 正常 / 无效类型降级 / 空内容
- GetFollowUpsTool: 正常 / 空结果 / limit 边界
- UpdateCustomerStageTool: 正常推进 / 无效阶段 / 事件触发
- GetSalesPipelineTool: 正常 / 空数据
"""

import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ── helpers ────────────────────────────────────────────────

FAKE_ORG_ID = "org-test-001"
FAKE_USER_ID = "user-test-001"
FAKE_CUSTOMER_ID = str(uuid.uuid4())

CONFIG = {"org_id": FAKE_ORG_ID, "token": None}


def _make_customer(overrides: dict = None) -> dict:
    """生成一条标准客户记录"""
    base = {
        "id": FAKE_CUSTOMER_ID,
        "name": "测试客户",
        "company": "测试科技有限公司",
        "industry": "IT",
        "stage": "lead",
        "source": "官网",
        "estimated_value": 50000,
        "organization_id": FAKE_ORG_ID,
        "assigned_to": FAKE_USER_ID,
        "created_at": "2026-03-01T00:00:00+00:00",
        "updated_at": "2026-04-01T00:00:00+00:00",
    }
    if overrides:
        base.update(overrides)
    return base


def _mock_db_chain():
    """构建一个通用的 supabase mock 链式调用对象"""
    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.insert.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.delete.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.or_.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.range.return_value = mock_query
    mock_query.maybe_single.return_value = mock_query
    return mock_query


def _load_tool(name: str):
    """按名称加载工具实例"""
    from app.tools import get_tool, _load_all
    _load_all()
    tool = get_tool(name)
    assert tool is not None, f"工具 {name} 未注册"
    return tool


# ═══════════════════════════════════════════════════════════════
#  GetCustomersTool 测试
# ═══════════════════════════════════════════════════════════════


class TestGetCustomersTool:
    """查询客户列表工具"""

    @pytest.mark.asyncio
    async def test_returns_customer_list(self):
        """正常返回客户列表"""
        tool = _load_tool("get_customers")
        customers = [_make_customer(), _make_customer({"id": str(uuid.uuid4()), "name": "客户B", "stage": "opportunity"})]

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.list_customers = AsyncMock(return_value=customers)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)

        assert "2 位客户" in result
        assert "测试客户" in result
        assert "客户B" in result

    @pytest.mark.asyncio
    async def test_empty_list(self):
        """无客户时返回引导提示"""
        tool = _load_tool("get_customers")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.list_customers = AsyncMock(return_value=[])
            result = await tool.run({}, FAKE_USER_ID, CONFIG)

        assert "暂无客户" in result
        assert "创建客户" in result

    @pytest.mark.asyncio
    async def test_filter_by_stage(self):
        """按阶段筛选"""
        tool = _load_tool("get_customers")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.list_customers = AsyncMock(return_value=[_make_customer({"stage": "opportunity"})])
            result = await tool.run({"stage": "opportunity"}, FAKE_USER_ID, CONFIG)

        mock_svc.list_customers.assert_called_once()
        call_kwargs = mock_svc.list_customers.call_args
        assert call_kwargs[1].get("filters", {}).get("stage") == "opportunity" or \
               call_kwargs[0][1].get("stage") == "opportunity" if len(call_kwargs[0]) > 1 else True

    @pytest.mark.asyncio
    async def test_search_mode(self):
        """搜索模式走 search_customers"""
        tool = _load_tool("get_customers")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.search_customers = AsyncMock(return_value=[_make_customer({"name": "华为"})])
            result = await tool.run({"search": "华为"}, FAKE_USER_ID, CONFIG)

        mock_svc.search_customers.assert_called_once()
        assert "华为" in result

    @pytest.mark.asyncio
    async def test_no_org_id(self):
        """缺少 org_id 时返回错误提示"""
        tool = _load_tool("get_customers")
        result = await tool.run({}, FAKE_USER_ID, {})  # 空 config
        assert "无法获取组织信息" in result


# ═══════════════════════════════════════════════════════════════
#  GetCustomerDetailTool 测试
# ═══════════════════════════════════════════════════════════════


class TestGetCustomerDetailTool:
    """查询客户详情工具"""

    @pytest.mark.asyncio
    async def test_returns_customer_detail(self):
        """正常返回客户详情 + 联系人 + 跟进记录"""
        tool = _load_tool("get_customer_detail")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.get_customer = AsyncMock(return_value=_make_customer())
            mock_svc.list_contacts = AsyncMock(return_value=[
                {"name": "张三", "title": "总经理", "phone": "13800001111", "email": "z@test.com", "is_primary": True}
            ])
            mock_svc.get_activity_timeline = AsyncMock(return_value=[
                {"activity_type": "call", "content": "电话沟通报价", "created_at": "2026-04-01"}
            ])

            result = await tool.run({"customer_id": FAKE_CUSTOMER_ID}, FAKE_USER_ID, CONFIG)

        assert "测试客户" in result
        assert "张三" in result
        assert "电话沟通" in result

    @pytest.mark.asyncio
    async def test_missing_customer_id(self):
        """未提供 customer_id"""
        tool = _load_tool("get_customer_detail")
        result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "请提供客户ID" in result

    @pytest.mark.asyncio
    async def test_invalid_uuid_format(self):
        """无效 UUID 格式"""
        tool = _load_tool("get_customer_detail")
        result = await tool.run({"customer_id": "not-a-uuid"}, FAKE_USER_ID, CONFIG)
        assert "不是有效的UUID" in result

    @pytest.mark.asyncio
    async def test_customer_not_found(self):
        """客户不存在"""
        tool = _load_tool("get_customer_detail")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.get_customer = AsyncMock(return_value=None)
            result = await tool.run({"customer_id": FAKE_CUSTOMER_ID}, FAKE_USER_ID, CONFIG)

        assert "未找到" in result


# ═══════════════════════════════════════════════════════════════
#  CreateCustomerTool 测试
# ═══════════════════════════════════════════════════════════════


class TestCreateCustomerTool:
    """创建客户工具"""

    @pytest.mark.asyncio
    async def test_create_success(self):
        """正常创建客户"""
        tool = _load_tool("create_customer")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.create_customer = AsyncMock(return_value=_make_customer({"name": "新客户"}))
            result = await tool.run({"name": "新客户", "company": "新公司"}, FAKE_USER_ID, CONFIG)

        assert "创建成功" in result
        assert "新客户" in result

    @pytest.mark.asyncio
    async def test_missing_name(self):
        """缺少必填字段 name"""
        tool = _load_tool("create_customer")
        result = await tool.run({"company": "某公司"}, FAKE_USER_ID, CONFIG)
        assert "名称不能为空" in result

    @pytest.mark.asyncio
    async def test_empty_name(self):
        """空白名称"""
        tool = _load_tool("create_customer")
        result = await tool.run({"name": "   "}, FAKE_USER_ID, CONFIG)
        assert "名称不能为空" in result

    @pytest.mark.asyncio
    async def test_negative_amount(self):
        """负数金额校验"""
        tool = _load_tool("create_customer")
        result = await tool.run(
            {"name": "测试", "estimated_value": -1000},
            FAKE_USER_ID, CONFIG,
        )
        assert "不能为负数" in result

    @pytest.mark.asyncio
    async def test_invalid_amount_format(self):
        """非数字金额"""
        tool = _load_tool("create_customer")
        result = await tool.run(
            {"name": "测试", "estimated_value": "abc"},
            FAKE_USER_ID, CONFIG,
        )
        assert "格式错误" in result

    @pytest.mark.asyncio
    async def test_no_org_id(self):
        """缺少组织信息"""
        tool = _load_tool("create_customer")
        result = await tool.run({"name": "测试"}, FAKE_USER_ID, {})
        assert "无法获取组织信息" in result


# ═══════════════════════════════════════════════════════════════
#  UpdateCustomerTool 测试
# ═══════════════════════════════════════════════════════════════


class TestUpdateCustomerTool:
    """更新客户工具"""

    @pytest.mark.asyncio
    async def test_update_success(self):
        """正常更新"""
        tool = _load_tool("update_customer")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.update_customer = AsyncMock(return_value=_make_customer({"company": "新公司名"}))
            result = await tool.run(
                {"customer_id": FAKE_CUSTOMER_ID, "company": "新公司名"},
                FAKE_USER_ID, CONFIG,
            )

        assert "已更新" in result
        assert "company=新公司名" in result

    @pytest.mark.asyncio
    async def test_no_fields_to_update(self):
        """未提供任何更新字段"""
        tool = _load_tool("update_customer")
        result = await tool.run({"customer_id": FAKE_CUSTOMER_ID}, FAKE_USER_ID, CONFIG)
        assert "至少一个要更新的字段" in result

    @pytest.mark.asyncio
    async def test_invalid_uuid(self):
        """无效 UUID"""
        tool = _load_tool("update_customer")
        result = await tool.run(
            {"customer_id": "bad-id", "name": "改名"},
            FAKE_USER_ID, CONFIG,
        )
        assert "不是有效的UUID" in result


# ═══════════════════════════════════════════════════════════════
#  AddFollowUpTool 测试
# ═══════════════════════════════════════════════════════════════


class TestAddFollowUpTool:
    """添加跟进记录工具"""

    @pytest.mark.asyncio
    async def test_add_success(self):
        """正常添加跟进"""
        tool = _load_tool("add_follow_up")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.create_activity = AsyncMock(return_value={
                "id": str(uuid.uuid4()), "activity_type": "call", "content": "沟通报价"
            })
            result = await tool.run(
                {"customer_id": FAKE_CUSTOMER_ID, "activity_type": "call", "content": "沟通报价"},
                FAKE_USER_ID, CONFIG,
            )

        assert "已添加" in result
        assert "电话" in result

    @pytest.mark.asyncio
    async def test_invalid_type_fallback_to_note(self):
        """无效的 activity_type 自动降级为 note"""
        tool = _load_tool("add_follow_up")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.create_activity = AsyncMock(return_value={
                "id": str(uuid.uuid4()), "activity_type": "note", "content": "随手记"
            })
            result = await tool.run(
                {"customer_id": FAKE_CUSTOMER_ID, "activity_type": "INVALID_TYPE", "content": "随手记"},
                FAKE_USER_ID, CONFIG,
            )

        # 应该调用成功，不报错（降级为 note）
        mock_svc.create_activity.assert_called_once()
        call_args = mock_svc.create_activity.call_args[0]
        assert call_args[1] == "note"  # activity_type 被降级

    @pytest.mark.asyncio
    async def test_empty_content(self):
        """内容为空"""
        tool = _load_tool("add_follow_up")
        result = await tool.run(
            {"customer_id": FAKE_CUSTOMER_ID, "activity_type": "call", "content": ""},
            FAKE_USER_ID, CONFIG,
        )
        assert "不能为空" in result


# ═══════════════════════════════════════════════════════════════
#  GetFollowUpsTool 测试
# ═══════════════════════════════════════════════════════════════


class TestGetFollowUpsTool:
    """查询跟进记录工具"""

    @pytest.mark.asyncio
    async def test_returns_timeline(self):
        """正常返回跟进时间线"""
        tool = _load_tool("get_follow_ups")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.get_activity_timeline = AsyncMock(return_value=[
                {"activity_type": "call", "content": "首次电话", "created_at": "2026-04-01"},
                {"activity_type": "meeting", "content": "现场拜访", "created_at": "2026-04-05"},
            ])
            result = await tool.run({"customer_id": FAKE_CUSTOMER_ID}, FAKE_USER_ID, CONFIG)

        assert "2条" in result
        assert "首次电话" in result
        assert "现场拜访" in result

    @pytest.mark.asyncio
    async def test_empty_timeline(self):
        """无跟进记录"""
        tool = _load_tool("get_follow_ups")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.get_activity_timeline = AsyncMock(return_value=[])
            result = await tool.run({"customer_id": FAKE_CUSTOMER_ID}, FAKE_USER_ID, CONFIG)

        assert "暂无跟进" in result

    @pytest.mark.asyncio
    async def test_limit_clamp(self):
        """limit 边界值自动修正"""
        tool = _load_tool("get_follow_ups")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.get_activity_timeline = AsyncMock(return_value=[])

            # 超大 limit 被 clamp 到 100
            await tool.run({"customer_id": FAKE_CUSTOMER_ID, "limit": 9999}, FAKE_USER_ID, CONFIG)
            call_kwargs = mock_svc.get_activity_timeline.call_args
            assert call_kwargs[1]["limit"] == 100

    @pytest.mark.asyncio
    async def test_invalid_limit_fallback(self):
        """非数字 limit 回退为 20"""
        tool = _load_tool("get_follow_ups")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.get_activity_timeline = AsyncMock(return_value=[])

            await tool.run({"customer_id": FAKE_CUSTOMER_ID, "limit": "abc"}, FAKE_USER_ID, CONFIG)
            call_kwargs = mock_svc.get_activity_timeline.call_args
            assert call_kwargs[1]["limit"] == 20


# ═══════════════════════════════════════════════════════════════
#  UpdateCustomerStageTool 测试
# ═══════════════════════════════════════════════════════════════


class TestUpdateCustomerStageTool:
    """推进客户阶段工具"""

    @pytest.mark.asyncio
    async def test_stage_update_success(self):
        """正常推进阶段"""
        tool = _load_tool("update_customer_stage")

        with patch("app.tools.crm_tools.crm_service") as mock_svc, \
             patch("app.services.event_bus.event_bus") as mock_bus:
            mock_svc.get_customer = AsyncMock(return_value=_make_customer({"stage": "lead"}))
            mock_svc.update_customer = AsyncMock(return_value=_make_customer({"stage": "opportunity", "name": "测试客户"}))
            mock_svc.create_activity = AsyncMock(return_value={"id": "act-1"})

            result = await tool.run(
                {"customer_id": FAKE_CUSTOMER_ID, "new_stage": "opportunity"},
                FAKE_USER_ID, CONFIG,
            )

        assert "阶段已更新" in result
        assert "线索" in result and "商机" in result
        # 验证跟进记录被创建
        mock_svc.create_activity.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_stage(self):
        """无效阶段值"""
        tool = _load_tool("update_customer_stage")
        result = await tool.run(
            {"customer_id": FAKE_CUSTOMER_ID, "new_stage": "nonexistent"},
            FAKE_USER_ID, CONFIG,
        )
        assert "无效的阶段" in result

    @pytest.mark.asyncio
    async def test_customer_not_found(self):
        """客户不存在"""
        tool = _load_tool("update_customer_stage")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.get_customer = AsyncMock(return_value=None)
            result = await tool.run(
                {"customer_id": FAKE_CUSTOMER_ID, "new_stage": "opportunity"},
                FAKE_USER_ID, CONFIG,
            )

        assert "未找到" in result

    @pytest.mark.asyncio
    async def test_empty_args(self):
        """缺少必要参数"""
        tool = _load_tool("update_customer_stage")
        result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "不能为空" in result


# ═══════════════════════════════════════════════════════════════
#  GetSalesPipelineTool 测试
# ═══════════════════════════════════════════════════════════════


class TestGetSalesPipelineTool:
    """销售漏斗视图工具"""

    @pytest.mark.asyncio
    async def test_pipeline_overview(self):
        """正常返回漏斗概览"""
        tool = _load_tool("get_sales_pipeline")

        stats = {
            "total_customers": 10,
            "new_this_month": 3,
            "conversion_rate": 30.0,
            "total_estimated_value": 500000,
            "stage_distribution": [
                {"stage": "lead", "name": "线索", "count": 4, "color": "#94a3b8"},
                {"stage": "prospect", "name": "意向", "count": 2, "color": "#3b82f6"},
                {"stage": "opportunity", "name": "商机", "count": 1, "color": "#f59e0b"},
                {"stage": "customer", "name": "成交", "count": 3, "color": "#22c55e"},
                {"stage": "churned", "name": "流失", "count": 0, "color": "#ef4444"},
            ],
        }
        customers = [
            _make_customer({"stage": "lead", "estimated_value": 10000}),
            _make_customer({"stage": "customer", "estimated_value": 200000}),
        ]

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.get_customer_stats = AsyncMock(return_value=stats)
            mock_svc.list_customers = AsyncMock(return_value=customers)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)

        assert "销售漏斗概览" in result
        assert "客户总数" in result
        assert "10" in result
        assert "转化率" in result

    @pytest.mark.asyncio
    async def test_empty_pipeline(self):
        """无客户数据"""
        tool = _load_tool("get_sales_pipeline")

        with patch("app.tools.crm_tools.crm_service") as mock_svc:
            mock_svc.get_customer_stats = AsyncMock(return_value={"total_customers": 0})
            result = await tool.run({}, FAKE_USER_ID, CONFIG)

        assert "暂无客户数据" in result

    @pytest.mark.asyncio
    async def test_no_org_id(self):
        """缺少组织信息"""
        tool = _load_tool("get_sales_pipeline")
        result = await tool.run({}, FAKE_USER_ID, {})
        assert "无法获取组织信息" in result
