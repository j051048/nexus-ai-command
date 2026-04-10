"""
库存管理工具集
提供库存查询、出入库、统计等功能
"""

import logging
from typing import Any

from app.services.inventory_service import inventory_service
from app.tools._shared import safe_tool_error

from ._shared import _get_client, _validate_uuid
from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ============================================================================
# 库存管理工具
# ============================================================================


class ListInventoryTool(BaseTool):
    """查询库存列表"""

    name = "list_inventory"
    domain = "inventory"
    description = "查询库存列表，支持按分类、位置、关键词筛选。当用户说'查看库存'、'物资列表'、'库存查询'时调用。"
    examples = [
        {"input": {}, "output_summary": "返回全部库存物品列表"},
        {
            "input": {"category": "办公用品", "low_stock_only": True},
            "output_summary": "返回办公用品分类下的低库存物品",
        },
        {
            "input": {"search": "打印纸"},
            "output_summary": "按名称或编码搜索包含'打印纸'的物品",
        },
    ]
    related_tools = ["inventory_in", "inventory_out", "inventory_statistics"]
    gotchas = (
        "low_stock_only=True时只返回库存低于最低库存阈值的物品。搜索按名称和编码匹配。"
    )

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

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
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
                if (
                    item.get("min_stock") is not None
                    and item.get("quantity", 0) < item["min_stock"]
                ):
                    stock_warning = " ⚠️低库存"

                lines.append(
                    f"- **{item.get('name', '未知')}** | 编码: {item.get('item_code', '')} | "
                    f"数量: {item.get('quantity', 0)} | "
                    f"位置: {item.get('location', '未知')}{stock_warning}"
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询库存失败: {e}")
            return safe_tool_error(e, "查询库存")


class InventoryInTool(BaseTool):
    """入库操作"""

    name = "inventory_in"
    domain = "inventory"
    description = "执行物品入库操作，增加指定物品的库存数量。当用户说'入库'、'物资入库'、'收货'时调用。"
    examples = [
        {
            "input": {"item_id": "uuid-xxx", "quantity": 100},
            "output_summary": "将指定物品入库100个",
        },
        {
            "input": {"item_id": "uuid-xxx", "quantity": 50, "reason": "采购到货"},
            "output_summary": "入库50个并记录原因为采购到货",
        },
    ]
    related_tools = ["list_inventory", "inventory_out", "inventory_statistics"]
    gotchas = "item_id必须是有效的UUID格式。入库数量必须大于0。入库前建议先用list_inventory确认物品存在。"

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

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
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

            return f"✅ 入库成功！\n\n- 物品ID: {item_id[:8]}...\n- 入库数量: {quantity}\n- 记录ID: {record.get('id', '')}"

        except Exception as e:
            logger.error(f"入库失败: {e}")
            return safe_tool_error(e, "入库")


class InventoryOutTool(BaseTool):
    """出库操作"""

    name = "inventory_out"
    domain = "inventory"
    description = "执行物品出库操作，减少指定物品的库存数量。当用户说'出库'、'领用物资'、'物品出库'时调用。"
    examples = [
        {
            "input": {"item_id": "uuid-xxx", "quantity": 10},
            "output_summary": "将指定物品出库10个",
        },
        {
            "input": {
                "item_id": "uuid-xxx",
                "quantity": 5,
                "receiver_id": "user-uuid",
                "reason": "项目领用",
            },
            "output_summary": "出库5个并记录领用人和原因",
        },
    ]
    related_tools = ["list_inventory", "inventory_in", "inventory_statistics"]
    gotchas = "出库数量不能超过当前库存。item_id和receiver_id都必须是有效的UUID格式。"

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

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
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

            return f"✅ 出库成功！\n\n- 物品ID: {item_id[:8]}...\n- 出库数量: {quantity}\n- 记录ID: {record.get('id', '')}"

        except Exception as e:
            logger.error(f"出库失败: {e}")
            return safe_tool_error(e, "出库")


class InventoryStatisticsTool(BaseTool):
    """库存统计"""

    name = "inventory_statistics"
    domain = "inventory"
    description = "获取库存统计数据，包括物品总数、总价值和低库存预警数。当用户说'库存统计'、'库存概况'、'物资统计'时调用。"
    examples = [
        {"input": {}, "output_summary": "返回全部库存的统计概况"},
        {
            "input": {"category": "电子设备"},
            "output_summary": "返回电子设备分类的库存统计",
        },
    ]
    related_tools = ["list_inventory", "inventory_in", "inventory_out"]
    gotchas = "不传category则统计全部分类。返回的总价值基于物品单价乘以数量。"

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

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
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
            return safe_tool_error(e, "获取库存统计")
