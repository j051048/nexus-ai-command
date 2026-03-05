"""
库存管理工具集
提供库存查询、出入库、统计等功能
"""

import logging
import uuid as _uuid
from typing import Any

from app.core.database import supabase
from app.services.inventory_service import inventory_service

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


def _validate_uuid(value: str, field_name: str = "ID") -> str | None:
    """验证UUID格式"""
    try:
        _uuid.UUID(value)
        return None
    except (ValueError, TypeError, AttributeError):
        return f"{field_name} '{value}' 不是有效的UUID格式。"


# ============================================================================
# 库存管理工具
# ============================================================================


class ListInventoryTool(BaseTool):
    """查询库存列表"""

    name = "list_inventory"
    description = "查询库存列表。当用户说'查看库存'、'物资列表'、'库存查询'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "物品分类（可选）",
            },
            "location": {
                "type": "string",
                "description": "存放位置（可选）",
            },
            "search": {
                "type": "string",
                "description": "搜索关键词，按名称或编码搜索（可选）",
                "maxLength": 100,
            },
            "low_stock_only": {
                "type": "boolean",
                "description": "是否只显示低库存物品（可选）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        filters = {}
        if args.get("category"):
            filters["category"] = args["category"]
        if args.get("location"):
            filters["location"] = args["location"]
        if args.get("search"):
            filters["search"] = args["search"]
        if args.get("low_stock_only"):
            filters["low_stock_only"] = args["low_stock_only"]

        try:
            items = await inventory_service.list_inventory(
                org_id=org_id,
                filters=filters or None,
                db=client,
            )

            if not items:
                return "📦 当前暂无库存记录。"

            lines = [f"📦 共找到 {len(items)} 种物品:\n"]
            for item in items:
                stock_warning = ""
                if item.get("min_stock") is not None and item.get("quantity", 0) < item["min_stock"]:
                    stock_warning = " ⚠️低库存"

                lines.append(
                    f"- **{item.get('name', '未知')}** | 编码: {item.get('item_code', '')} | "
                    f"数量: {item.get('quantity', 0)} | "
                    f"位置: {item.get('location', '未知')}{stock_warning}"
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询库存失败: {e}")
            return f"❌ 查询库存失败: {str(e)}"


class InventoryInTool(BaseTool):
    """入库操作"""

    name = "inventory_in"
    description = "入库操作，接收物品入库。当用户说'入库'、'物资入库'、'收货'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "item_id": {
                "type": "string",
                "description": "物品ID",
            },
            "quantity": {
                "type": "integer",
                "description": "入库数量",
                "minimum": 1,
            },
            "reason": {
                "type": "string",
                "description": "入库原因（可选）",
                "maxLength": 500,
            },
        },
        "required": ["item_id", "quantity"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        item_id = args.get("item_id", "").strip()
        quantity = args.get("quantity")
        reason = args.get("reason")

        if not item_id:
            return "❌ 物品ID不能为空"
        if err := _validate_uuid(item_id, "item_id"):
            return f"❌ {err}"
        if not quantity or quantity <= 0:
            return "❌ 入库数量必须大于0"

        try:
            record = await inventory_service.inventory_in(
                org_id=org_id,
                item_id=item_id,
                quantity=quantity,
                operator_id=user_id,
                reason=reason,
                db=client,
            )

            return (
                f"✅ 入库成功！\n\n- 物品ID: {item_id[:8]}...\n- 入库数量: {quantity}\n- 记录ID: {record.get('id', '')}"
            )

        except Exception as e:
            logger.error(f"入库失败: {e}")
            return f"❌ 入库失败: {str(e)}"


class InventoryOutTool(BaseTool):
    """出库操作"""

    name = "inventory_out"
    description = "出库操作，领用物品出库。当用户说'出库'、'领用物资'、'物品出库'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "item_id": {
                "type": "string",
                "description": "物品ID",
            },
            "quantity": {
                "type": "integer",
                "description": "出库数量",
                "minimum": 1,
            },
            "receiver_id": {
                "type": "string",
                "description": "领用人ID（可选）",
            },
            "reason": {
                "type": "string",
                "description": "出库原因（可选）",
                "maxLength": 500,
            },
        },
        "required": ["item_id", "quantity"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        item_id = args.get("item_id", "").strip()
        quantity = args.get("quantity")
        receiver_id = args.get("receiver_id")
        reason = args.get("reason")

        if not item_id:
            return "❌ 物品ID不能为空"
        if err := _validate_uuid(item_id, "item_id"):
            return f"❌ {err}"
        if not quantity or quantity <= 0:
            return "❌ 出库数量必须大于0"

        if receiver_id:
            receiver_id = receiver_id.strip()
            if err := _validate_uuid(receiver_id, "receiver_id"):
                return f"❌ {err}"

        try:
            record = await inventory_service.inventory_out(
                org_id=org_id,
                item_id=item_id,
                quantity=quantity,
                operator_id=user_id,
                receiver_id=receiver_id,
                reason=reason,
                db=client,
            )

            return (
                f"✅ 出库成功！\n\n- 物品ID: {item_id[:8]}...\n- 出库数量: {quantity}\n- 记录ID: {record.get('id', '')}"
            )

        except Exception as e:
            logger.error(f"出库失败: {e}")
            return f"❌ 出库失败: {str(e)}"


class InventoryStatisticsTool(BaseTool):
    """库存统计"""

    name = "inventory_statistics"
    description = "获取库存统计数据。当用户说'库存统计'、'库存概况'、'物资统计'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "物品分类（可选，不填统计全部）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        category = args.get("category")

        try:
            stats = await inventory_service.get_inventory_statistics(
                org_id=org_id,
                category=category,
                db=client,
            )

            category_label = category if category else "全部"

            return (
                f"📊 库存统计 ({category_label}):\n\n"
                f"- 物品总数: {stats.get('total_items', 0)}\n"
                f"- 库存总价值: ¥{stats.get('total_value', 0):,.2f}\n"
                f"- 低库存预警: {stats.get('low_stock_count', 0)} 项"
            )

        except Exception as e:
            logger.error(f"获取库存统计失败: {e}")
            return f"❌ 获取库存统计失败: {str(e)}"
