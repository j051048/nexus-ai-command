"""
资产管理服务
提供通用资产管理功能
"""

import logging

logger = logging.getLogger(__name__)


class AssetService:
    """资产管理服务"""

    async def list_assets(
        self,
        org_id: str,
        filters: dict | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询资产列表

        Args:
            org_id: 组织ID
            filters: 筛选条件 {asset_type, status, department_id, current_user_id, search}
            db: 数据库客户端

        Returns:
            资产列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = (
                db.table("assets")
                .select("*, current_user:employees!current_user_id(id, name)")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
            )

            if filters:
                if filters.get("asset_type"):
                    query = query.eq("asset_type", filters["asset_type"])
                if filters.get("status"):
                    query = query.eq("status", filters["status"])
                if filters.get("department_id"):
                    query = query.eq("department_id", filters["department_id"])
                if filters.get("current_user_id"):
                    query = query.eq("current_user_id", filters["current_user_id"])
                if filters.get("search"):
                    search = filters["search"]
                    query = query.or_(f"asset_code.ilike.%{search}%,name.ilike.%{search}%")

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"查询资产列表失败: {e}")
            raise

    async def get_asset_detail(
        self,
        asset_id: str,
        db=None,
    ) -> dict | None:
        """
        获取资产详情

        Args:
            asset_id: 资产ID
            db: 数据库客户端

        Returns:
            资产详情
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await (
                db.table("assets")
                .select("*, current_user:employees!current_user_id(id, name)")
                .eq("id", asset_id)
                .maybe_single()
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"获取资产详情失败: {e}")
            raise

    async def create_asset(
        self,
        org_id: str,
        data: dict,
        db=None,
    ) -> dict:
        """
        创建资产

        Args:
            org_id: 组织ID
            data: 资产数据
            db: 数据库客户端

        Returns:
            资产对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            data["organization_id"] = org_id
            data.setdefault("status", "idle")

            result = await db.table("assets").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"资产已创建: org={org_id}, code={data.get('asset_code')}")
                return result.data[0]

            raise RuntimeError("资产创建失败")

        except Exception as e:
            logger.error(f"创建资产失败: {e}")
            raise

    async def update_asset(
        self,
        asset_id: str,
        updates: dict,
        db=None,
    ) -> dict:
        """
        更新资产信息

        Args:
            asset_id: 资产ID
            updates: 更新字段
            db: 数据库客户端

        Returns:
            更新后的资产对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await db.table("assets").update(updates).eq("id", asset_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"资产已更新: id={asset_id}")
                return result.data[0]

            raise RuntimeError("资产更新失败")

        except Exception as e:
            logger.error(f"更新资产失败: {e}")
            raise

    async def transfer_asset(
        self,
        org_id: str,
        asset_id: str,
        transfer_type: str,
        operator_id: str,
        from_user_id: str | None = None,
        to_user_id: str | None = None,
        from_department_id: str | None = None,
        to_department_id: str | None = None,
        reason: str | None = None,
        db=None,
    ) -> dict:
        """
        资产转移/领用/归还

        Args:
            org_id: 组织ID
            asset_id: 资产ID
            transfer_type: 转移类型 (allocate/return/transfer/scrap)
            operator_id: 操作人ID
            from_user_id: 原使用人ID
            to_user_id: 新使用人ID
            from_department_id: 原部门ID
            to_department_id: 新部门ID
            reason: 原因
            db: 数据库客户端

        Returns:
            转移记录
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            # 创建转移记录
            transfer_data = {
                "organization_id": org_id,
                "asset_id": asset_id,
                "transfer_type": transfer_type,
                "from_user_id": from_user_id,
                "to_user_id": to_user_id,
                "from_department_id": from_department_id,
                "to_department_id": to_department_id,
                "reason": reason,
                "operator_id": operator_id,
            }

            transfer_result = await db.table("asset_transfers").insert(transfer_data).execute()

            # 更新资产状态
            asset_updates = {}
            if to_user_id:
                asset_updates["current_user_id"] = to_user_id
                asset_updates["status"] = "in_use"
            elif transfer_type == "return":
                asset_updates["current_user_id"] = None
                asset_updates["status"] = "idle"
            elif transfer_type == "scrap":
                asset_updates["status"] = "scrapped"

            if to_department_id:
                asset_updates["department_id"] = to_department_id

            if asset_updates:
                await db.table("assets").update(asset_updates).eq("id", asset_id).execute()

            logger.info(f"资产转移成功: asset={asset_id}, type={transfer_type}")
            return transfer_result.data[0] if transfer_result.data else {}

        except Exception as e:
            logger.error(f"资产转移失败: {e}")
            raise

    async def get_asset_statistics(
        self,
        org_id: str,
        asset_type: str | None = None,
        db=None,
    ) -> dict:
        """
        获取资产统计数据

        Args:
            org_id: 组织ID
            asset_type: 资产类型（可选）
            db: 数据库客户端

        Returns:
            统计数据
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = db.table("assets").select("*").eq("organization_id", org_id)

            if asset_type:
                query = query.eq("asset_type", asset_type)

            result = await query.execute()
            assets = result.data or []

            total_count = len(assets)
            idle_count = sum(1 for a in assets if a.get("status") == "idle")
            in_use_count = sum(1 for a in assets if a.get("status") == "in_use")
            maintenance_count = sum(1 for a in assets if a.get("status") == "maintenance")
            scrapped_count = sum(1 for a in assets if a.get("status") == "scrapped")

            total_value = sum(float(a.get("value") or 0) for a in assets)

            return {
                "total_count": total_count,
                "idle_count": idle_count,
                "in_use_count": in_use_count,
                "maintenance_count": maintenance_count,
                "scrapped_count": scrapped_count,
                "utilization_rate": round(in_use_count / total_count * 100, 2) if total_count > 0 else 0,
                "total_value": round(total_value, 2),
            }

        except Exception as e:
            logger.error(f"获取资产统计失败: {e}")
            raise

    async def list_asset_types(
        self,
        org_id: str,
        db=None,
    ) -> list[dict]:
        """
        查询资产类型列表

        Args:
            org_id: 组织ID
            db: 数据库客户端

        Returns:
            资产类型列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await db.table("asset_types").select("*").eq("organization_id", org_id).execute()

            return result.data or []

        except Exception as e:
            logger.error(f"查询资产类型列表失败: {e}")
            raise

    async def create_asset_type(
        self,
        org_id: str,
        name: str,
        icon: str | None = None,
        fields_config: dict | None = None,
        db=None,
    ) -> dict:
        """
        创建资产类型

        Args:
            org_id: 组织ID
            name: 类型名称
            icon: 图标
            fields_config: 字段配置
            db: 数据库客户端

        Returns:
            资产类型对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            data = {
                "organization_id": org_id,
                "name": name,
                "icon": icon,
                "fields_config": fields_config or {},
            }

            result = await db.table("asset_types").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"资产类型已创建: org={org_id}, name={name}")
                return result.data[0]

            raise RuntimeError("资产类型创建失败")

        except Exception as e:
            logger.error(f"创建资产类型失败: {e}")
            raise


asset_service = AssetService()
