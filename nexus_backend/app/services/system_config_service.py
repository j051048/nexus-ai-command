"""
系统配置服务
提供租户级别的可配置化能力，支持自定义业务枚举
"""

import logging

logger = logging.getLogger(__name__)


class SystemConfigService:
    """系统配置管理服务"""

    async def list_configs(
        self,
        org_id: str,
        config_type: str | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询配置列表

        Args:
            org_id: 组织ID
            config_type: 配置类型（可选）
            db: 数据库客户端

        Returns:
            配置列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = (
                db.table("system_configs")
                .select("*")
                .eq("organization_id", org_id)
                .eq("is_active", True)
                .order("config_type", desc=False)
                .order("sort_order", desc=False)
            )

            if config_type:
                query = query.eq("config_type", config_type)

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"查询配置列表失败: {e}")
            raise

    async def get_config(
        self,
        org_id: str,
        config_type: str,
        config_key: str,
        db=None,
    ) -> dict | None:
        """
        获取单个配置

        Args:
            org_id: 组织ID
            config_type: 配置类型
            config_key: 配置键
            db: 数据库客户端

        Returns:
            配置对象或None
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await (
                db.table("system_configs")
                .select("*")
                .eq("organization_id", org_id)
                .eq("config_type", config_type)
                .eq("config_key", config_key)
                .eq("is_active", True)
                .maybe_single()
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"获取配置失败: {e}")
            raise

    async def upsert_config(
        self,
        org_id: str,
        config_type: str,
        config_key: str,
        config_value: dict,
        sort_order: int = 0,
        db=None,
    ) -> dict:
        """
        创建或更新配置

        Args:
            org_id: 组织ID
            config_type: 配置类型
            config_key: 配置键
            config_value: 配置值（JSONB）
            sort_order: 排序
            db: 数据库客户端

        Returns:
            配置对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            data = {
                "organization_id": org_id,
                "config_type": config_type,
                "config_key": config_key,
                "config_value": config_value,
                "sort_order": sort_order,
                "is_active": True,
            }

            result = await (
                db.table("system_configs").upsert(data, on_conflict="organization_id,config_type,config_key").execute()
            )

            if result.data and len(result.data) > 0:
                logger.info(f"配置已保存: org={org_id}, type={config_type}, key={config_key}")
                return result.data[0]

            raise RuntimeError("配置保存失败")

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            raise

    async def delete_config(
        self,
        org_id: str,
        config_type: str,
        config_key: str,
        db=None,
    ) -> bool:
        """
        删除配置（软删除）

        Args:
            org_id: 组织ID
            config_type: 配置类型
            config_key: 配置键
            db: 数据库客户端

        Returns:
            是否成功
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await (
                db.table("system_configs")
                .update({"is_active": False})
                .eq("organization_id", org_id)
                .eq("config_type", config_type)
                .eq("config_key", config_key)
                .execute()
            )

            if result.data:
                logger.info(f"配置已删除: org={org_id}, type={config_type}, key={config_key}")
                return True
            return False

        except Exception as e:
            logger.error(f"删除配置失败: {e}")
            raise

    async def init_default_configs(self, org_id: str, db=None) -> None:
        """
        初始化租户默认配置

        Args:
            org_id: 组织ID
            db: 数据库客户端
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        # 默认资产状态
        asset_statuses = [
            ("idle", {"label": "闲置", "color": "#9CA3AF", "icon": "inbox"}),
            ("in_use", {"label": "使用中", "color": "#10B981", "icon": "check-circle"}),
            ("maintenance", {"label": "维修中", "color": "#F59E0B", "icon": "wrench"}),
            ("scrapped", {"label": "已报废", "color": "#EF4444", "icon": "trash"}),
        ]

        # 默认工单类型
        work_order_types = [
            ("repair", {"label": "设备报修", "color": "#F59E0B", "icon": "wrench"}),
            ("complaint", {"label": "客户投诉", "color": "#EF4444", "icon": "alert-circle"}),
            ("request", {"label": "物资申请", "color": "#3B82F6", "icon": "package"}),
            ("consultation", {"label": "咨询", "color": "#8B5CF6", "icon": "help-circle"}),
        ]

        # 默认优先级
        priorities = [
            ("low", {"label": "低", "color": "#9CA3AF"}),
            ("medium", {"label": "中", "color": "#3B82F6"}),
            ("high", {"label": "高", "color": "#F59E0B"}),
            ("urgent", {"label": "紧急", "color": "#EF4444"}),
        ]

        try:
            configs = []

            for i, (key, value) in enumerate(asset_statuses):
                configs.append(
                    {
                        "organization_id": org_id,
                        "config_type": "asset_status",
                        "config_key": key,
                        "config_value": value,
                        "sort_order": i,
                    }
                )

            for i, (key, value) in enumerate(work_order_types):
                configs.append(
                    {
                        "organization_id": org_id,
                        "config_type": "work_order_type",
                        "config_key": key,
                        "config_value": value,
                        "sort_order": i,
                    }
                )

            for i, (key, value) in enumerate(priorities):
                configs.append(
                    {
                        "organization_id": org_id,
                        "config_type": "priority",
                        "config_key": key,
                        "config_value": value,
                        "sort_order": i,
                    }
                )

            await db.table("system_configs").insert(configs).execute()
            logger.info(f"租户默认配置已初始化: org={org_id}")

        except Exception as e:
            logger.warning(f"初始化默认配置失败（可能已存在）: {e}")


system_config_service = SystemConfigService()
