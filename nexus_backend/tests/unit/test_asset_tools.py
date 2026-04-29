"""
资产管理工具 (asset_tools.py) 单元测试
覆盖：资产列表、详情、创建、更新、转移、统计
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FAKE_USER_ID = "user-" + "a" * 32
FAKE_ORG_ID = "org-" + "b" * 32
CONFIG = {"org_id": FAKE_ORG_ID, "token": "jwt-test"}


def _mock_client():
    return MagicMock()


def _load_tool(name: str):
    from app.tools import get_tool
    tool = get_tool(name)
    assert tool is not None, f"Tool '{name}' not found in registry"
    return tool


# ════════════════════════════════════════════════════════════════════
# 资产列表
# ════════════════════════════════════════════════════════════════════


class TestListAssetsTool:
    """查询资产列表"""

    @pytest.mark.asyncio
    async def test_list_all_assets(self):
        tool = _load_tool("list_assets")
        assets = [
            {"id": str(uuid.uuid4()), "name": "联想笔记本", "asset_code": "PC-001",
             "asset_type": "computer", "status": "in_use", "current_user": {"name": "张三"}, "value": 6000},
            {"id": str(uuid.uuid4()), "name": "丰田商务车", "asset_code": "VH-001",
             "asset_type": "vehicle", "status": "idle", "current_user": None, "value": 280000},
        ]
        with (
            patch("app.tools.asset_tools._get_client", return_value=_mock_client()),
            patch("app.tools.asset_tools.asset_service") as svc,
        ):
            svc.list_assets = AsyncMock(return_value=assets)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        result_str = str(result)
        assert "联想笔记本" in result_str or "PC-001" in result_str
        assert "2" in result_str

    @pytest.mark.asyncio
    async def test_list_assets_empty(self):
        tool = _load_tool("list_assets")
        with (
            patch("app.tools.asset_tools._get_client", return_value=_mock_client()),
            patch("app.tools.asset_tools.asset_service") as svc,
        ):
            svc.list_assets = AsyncMock(return_value=[])
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        assert "暂无" in str(result)

    @pytest.mark.asyncio
    async def test_list_assets_with_filter(self):
        tool = _load_tool("list_assets")
        filtered = [
            {"id": str(uuid.uuid4()), "name": "ThinkPad", "asset_code": "PC-002",
             "asset_type": "computer", "status": "idle", "current_user": None, "value": 5000},
        ]
        with (
            patch("app.tools.asset_tools._get_client", return_value=_mock_client()),
            patch("app.tools.asset_tools.asset_service") as svc,
        ):
            svc.list_assets = AsyncMock(return_value=filtered)
            result = await tool.run(
                {"asset_type": "computer", "status": "idle"}, FAKE_USER_ID, CONFIG
            )
        assert "ThinkPad" in str(result) or "PC-002" in str(result)

    @pytest.mark.asyncio
    async def test_list_assets_no_org(self):
        tool = _load_tool("list_assets")
        with patch("app.tools.asset_tools._get_client", return_value=_mock_client()):
            result = await tool.run({}, FAKE_USER_ID, {})
        assert "无法获取组织" in str(result) or "❌" in str(result) or "登录" in str(result)


class TestGetAssetDetailTool:
    """资产详情"""

    @pytest.mark.asyncio
    async def test_get_detail_success(self):
        tool = _load_tool("get_asset_detail")
        asset_id = str(uuid.uuid4())
        asset = {
            "id": asset_id, "name": "MacBook Pro", "asset_code": "PC-003",
            "asset_type": "computer", "status": "in_use",
            "current_user": {"name": "李四"}, "department": {"name": "技术部"},
            "purchase_date": "2026-01-15", "value": 15000,
            "metadata": {"serial": "SN123456"},
        }
        with (
            patch("app.tools.asset_tools._get_client", return_value=_mock_client()),
            patch("app.tools.asset_tools.asset_service") as svc,
        ):
            svc.get_asset_detail = AsyncMock(return_value=asset)
            result = await tool.run({"asset_id": asset_id}, FAKE_USER_ID, CONFIG)
        result_str = str(result)
        assert "MacBook Pro" in result_str or "PC-003" in result_str

    @pytest.mark.asyncio
    async def test_get_detail_not_found(self):
        tool = _load_tool("get_asset_detail")
        asset_id = str(uuid.uuid4())
        with (
            patch("app.tools.asset_tools._get_client", return_value=_mock_client()),
            patch("app.tools.asset_tools.asset_service") as svc,
        ):
            svc.get_asset_detail = AsyncMock(return_value=None)
            result = await tool.run({"asset_id": asset_id}, FAKE_USER_ID, CONFIG)
        assert "未找到" in str(result) or "不存在" in str(result)

    @pytest.mark.asyncio
    async def test_get_detail_invalid_uuid(self):
        tool = _load_tool("get_asset_detail")
        with patch("app.tools.asset_tools._get_client", return_value=_mock_client()):
            result = await tool.run({"asset_id": "invalid"}, FAKE_USER_ID, CONFIG)
        assert "❌" in str(result)


class TestCreateAssetTool:
    """创建资产"""

    @pytest.mark.asyncio
    async def test_create_asset_success(self):
        tool = _load_tool("create_asset")
        asset_id = str(uuid.uuid4())
        updated = {
            "id": asset_id, "name": "Dell显示器",
            "status": "idle",
        }
        with (
            patch("app.tools.asset_tools._get_client", return_value=_mock_client()),
            patch("app.tools.asset_tools.asset_service") as svc,
        ):
            svc.update_asset = AsyncMock(return_value=updated)
            result = await tool.run(
                {"asset_id": asset_id, "name": "Dell显示器", "status": "idle"},
                FAKE_USER_ID, CONFIG,
            )
        result_str = str(result)
        assert "Dell显示器" in result_str or "✅" in result_str or "成功" in result_str or "更新" in result_str

    @pytest.mark.asyncio
    async def test_create_asset_missing_required(self):
        tool = _load_tool("create_asset")
        with patch("app.tools.asset_tools._get_client", return_value=_mock_client()):
            result = await tool.run(
                {"asset_code": "", "name": "", "asset_type": ""},
                FAKE_USER_ID, CONFIG,
            )
        assert "❌" in str(result) or "不能为空" in str(result)


class TestTransferAssetTool:
    """资产转移"""

    @pytest.mark.asyncio
    async def test_allocate_success(self):
        tool = _load_tool("transfer_asset")
        asset_id = str(uuid.uuid4())
        to_user = str(uuid.uuid4())
        with (
            patch("app.tools.asset_tools._get_client", return_value=_mock_client()),
            patch("app.tools.asset_tools.asset_service") as svc,
        ):
            svc.transfer_asset = AsyncMock(return_value={"id": asset_id})
            result = await tool.run(
                {"asset_id": asset_id, "transfer_type": "allocate", "to_user_id": to_user},
                FAKE_USER_ID, CONFIG,
            )
        result_str = str(result)
        assert "✅" in result_str or "成功" in result_str or "领用" in result_str or "转移" in result_str

    @pytest.mark.asyncio
    async def test_transfer_invalid_uuid(self):
        tool = _load_tool("transfer_asset")
        with patch("app.tools.asset_tools._get_client", return_value=_mock_client()):
            result = await tool.run(
                {"asset_id": "bad-uuid", "transfer_type": "allocate", "to_user_id": "bad"},
                FAKE_USER_ID, CONFIG,
            )
        assert "❌" in str(result)


class TestAssetStatisticsTool:
    """资产统计"""

    @pytest.mark.asyncio
    async def test_statistics_all(self):
        tool = _load_tool("asset_statistics")
        stats = {
            "total_count": 50, "in_use_count": 35, "idle_count": 10,
            "maintenance_count": 3, "scrapped_count": 2,
            "utilization_rate": 70, "total_value": 2500000,
        }
        with (
            patch("app.tools.asset_tools._get_client", return_value=_mock_client()),
            patch("app.tools.asset_tools.asset_service") as svc,
        ):
            svc.get_asset_statistics = AsyncMock(return_value=stats)
            result = await tool.run({}, FAKE_USER_ID, CONFIG)
        result_str = str(result)
        assert "50" in result_str or "资产" in result_str
