"""
库存管理服务
提供库存查询、出入库、低库存预警等功能
"""

import logging

logger = logging.getLogger(__name__)


class InventoryService:
    """库存管理服务"""

    async def list_inventory(
        self,
        org_id: str,
        filters: dict | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询库存列表

        Args:
            org_id: 组织ID
            filters: 筛选条件 {category, location, search, low_stock_only}
            db: 数据库客户端

        Returns:
            库存列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = (
                db.table("inventory")
                .select("*")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
            )

            if filters:
                if filters.get("category"):
                    query = query.eq("category", filters["category"])
                if filters.get("location"):
                    query = query.eq("location", filters["location"])
                if filters.get("search"):
                    search = filters["search"]
                    query = query.or_(
                        f"name.ilike.%{search}%,item_code.ilike.%{search}%"
                    )
                if filters.get("low_stock_only"):
                    # 需要在应用层过滤，因为 PostgREST 不支持跨列比较
                    pass

            result = await query.execute()
            items = result.data or []

            # 应用层过滤低库存
            if filters and filters.get("low_stock_only"):
                items = [
                    item
                    for item in items
                    if item.get("min_stock") is not None
                    and item.get("quantity", 0) < item["min_stock"]
                ]

            return items

        except Exception as e:
            logger.error(f"查询库存列表失败: {e}")
            raise

    async def inventory_in(
        self,
        org_id: str,
        item_id: str,
        quantity: int,
        operator_id: str,
        reason: str | None = None,
        metadata: dict | None = None,
        idempotency_key: str | None = None,
        db=None,
    ) -> dict:
        """
        入库操作

        Args:
            org_id: 组织ID
            item_id: 物品ID
            quantity: 入库数量
            operator_id: 操作人ID
            reason: 入库原因
            metadata: 附加信息
            db: 数据库客户端

        Returns:
            入库记录
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        try:
            result = await db.rpc(
                "adjust_inventory_atomic",
                {
                    "p_org_id": org_id,
                    "p_item_id": item_id,
                    "p_delta": quantity,
                    "p_operator_id": operator_id,
                    "p_receiver_id": None,
                    "p_reason": reason,
                    "p_metadata": metadata or {},
                    "p_idempotency_key": idempotency_key,
                },
            ).execute()
            payload = result.data or {}
            logger.info(
                "Inventory receipt committed atomically: item=%s quantity=%s new_total=%s",
                item_id,
                quantity,
                payload.get("new_quantity"),
            )
            return payload

        except Exception as e:
            logger.error(f"入库失败: {e}")
            raise

    async def inventory_out(
        self,
        org_id: str,
        item_id: str,
        quantity: int,
        operator_id: str,
        receiver_id: str | None = None,
        reason: str | None = None,
        idempotency_key: str | None = None,
        db=None,
    ) -> dict:
        """
        出库操作

        Args:
            org_id: 组织ID
            item_id: 物品ID
            quantity: 出库数量
            operator_id: 操作人ID
            receiver_id: 领用人ID
            reason: 出库原因
            db: 数据库客户端

        Returns:
            出库记录
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        try:
            result = await db.rpc(
                "adjust_inventory_atomic",
                {
                    "p_org_id": org_id,
                    "p_item_id": item_id,
                    "p_delta": -quantity,
                    "p_operator_id": operator_id,
                    "p_receiver_id": receiver_id,
                    "p_reason": reason,
                    "p_metadata": {},
                    "p_idempotency_key": idempotency_key,
                },
            ).execute()
            payload = result.data or {}
            logger.info(
                "Inventory issue committed atomically: item=%s quantity=%s new_total=%s",
                item_id,
                quantity,
                payload.get("new_quantity"),
            )
            return payload

        except Exception as e:
            logger.error(f"出库失败: {e}")
            raise

    async def get_low_stock_items(
        self,
        org_id: str,
        db=None,
    ) -> list[dict]:
        """
        获取低库存预警物品

        Args:
            org_id: 组织ID
            db: 数据库客户端

        Returns:
            低库存物品列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await (
                db.table("inventory")
                .select("*")
                .eq("organization_id", org_id)
                .not_.is_("min_stock", "null")
                .execute()
            )

            items = result.data or []

            # 应用层过滤: quantity < min_stock
            low_stock_items = [
                item
                for item in items
                if item.get("quantity", 0) < item.get("min_stock", 0)
            ]

            return low_stock_items

        except Exception as e:
            logger.error(f"获取低库存预警失败: {e}")
            raise

    async def get_inventory_statistics(
        self,
        org_id: str,
        category: str | None = None,
        db=None,
    ) -> dict:
        """
        获取库存统计数据

        Args:
            org_id: 组织ID
            category: 物品分类（可选）
            db: 数据库客户端

        Returns:
            统计数据
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = db.table("inventory").select("*").eq("organization_id", org_id)

            if category:
                query = query.eq("category", category)

            result = await query.execute()
            items = result.data or []

            total_items = len(items)
            total_value = sum(
                float(item.get("unit_price") or 0) * int(item.get("quantity") or 0)
                for item in items
            )
            low_stock_count = sum(
                1
                for item in items
                if item.get("min_stock") is not None
                and item.get("quantity", 0) < item["min_stock"]
            )

            return {
                "total_items": total_items,
                "total_value": round(total_value, 2),
                "low_stock_count": low_stock_count,
            }

        except Exception as e:
            logger.error(f"获取库存统计失败: {e}")
            raise


inventory_service = InventoryService()
