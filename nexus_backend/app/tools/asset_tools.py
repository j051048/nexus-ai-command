"""
资产管理工具集
提供通用资产管理功能（适用于车辆、电脑、设备等任何类型资产）
"""

import logging
import uuid as _uuid
from typing import Any

from app.core.database import supabase
from app.services.asset_service import asset_service

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
# 资产管理工具
# ============================================================================


class ListAssetsTool(BaseTool):
    """查询资产列表"""

    name = "list_assets"
    description = (
        "查询资产列表，支持按类型、状态、部门筛选。"
        "当用户说'查看资产'、'资产列表'、'有哪些设备'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "asset_type": {
                "type": "string",
                "description": "资产类型（如: vehicle, computer, furniture）",
            },
            "status": {
                "type": "string",
                "description": "资产状态: idle/in_use/maintenance/scrapped",
            },
            "department_id": {
                "type": "string",
                "description": "部门ID（可选）",
            },
            "search": {
                "type": "string",
                "description": "搜索关键词（资产编号/名称）",
                "maxLength": 100,
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
        if args.get("asset_type"):
            filters["asset_type"] = args["asset_type"]
        if args.get("status"):
            filters["status"] = args["status"]
        if args.get("department_id"):
            if err := _validate_uuid(args["department_id"], "department_id"):
                return f"❌ {err}"
            filters["department_id"] = args["department_id"]
        if args.get("search"):
            filters["search"] = args["search"]

        try:
            assets = await asset_service.list_assets(
                org_id=org_id,
                filters=filters or None,
                db=client,
            )

            if not assets:
                return "当前暂无资产记录。您可以说「创建资产」来添加新资产。"

            status_labels = {
                "idle": "闲置",
                "in_use": "使用中",
                "maintenance": "维修中",
                "scrapped": "已报废",
            }

            lines = [f"📋 共找到 {len(assets)} 项资产:\n"]
            for asset in assets:
                status = status_labels.get(asset.get("status", ""), asset.get("status", ""))
                user = asset.get("current_user", {})
                user_name = user.get("name", "无") if user else "无"
                value = asset.get("value") or 0
                value_str = f"¥{float(value):,.0f}" if value else "未填写"

                lines.append(
                    f"- **{asset.get('name')}** [{asset.get('asset_code')}] | "
                    f"类型: {asset.get('asset_type')} | 状态: {status} | "
                    f"使用人: {user_name} | 价值: {value_str} | ID: {asset['id'][:8]}..."
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询资产列表失败: {e}")
            return f"❌ 查询资产列表失败: {str(e)}"


class GetAssetDetailTool(BaseTool):
    """获取资产详情"""

    name = "get_asset_detail"
    description = (
        "获取资产详细信息。"
        "当用户说'查看资产详情'、'资产信息'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "asset_id": {
                "type": "string",
                "description": "资产ID",
            },
        },
        "required": ["asset_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        asset_id = args.get("asset_id")

        if err := _validate_uuid(asset_id, "asset_id"):
            return f"❌ {err}"

        try:
            asset = await asset_service.get_asset_detail(
                asset_id=asset_id,
                db=client,
            )

            if not asset:
                return f"❌ 未找到ID为 {asset_id} 的资产。"

            status_labels = {
                "idle": "闲置",
                "in_use": "使用中",
                "maintenance": "维修中",
                "scrapped": "已报废",
            }
            status = status_labels.get(asset.get("status", ""), asset.get("status", ""))
            user = asset.get("current_user", {})
            user_name = user.get("name", "无") if user else "无"
            dept_id = asset.get("department_id", "未分配")
            value = asset.get("value") or 0
            value_str = f"¥{float(value):,.0f}" if value else "未填写"

            result = (
                f"🏷️ 资产详情:\n\n"
                f"- 名称: {asset.get('name')}\n"
                f"- 编号: {asset.get('asset_code')}\n"
                f"- 类型: {asset.get('asset_type')}\n"
                f"- 状态: {status}\n"
                f"- 部门: {dept_id}\n"
                f"- 使用人: {user_name}\n"
                f"- 购置日期: {asset.get('purchase_date', '未填写')}\n"
                f"- 价值: {value_str}\n"
                f"- ID: {asset['id']}"
            )

            # 附加自定义字段
            metadata = asset.get("metadata", {})
            if metadata:
                result += "\n\n📎 附加信息:"
                for key, val in metadata.items():
                    result += f"\n  - {key}: {val}"

            return result

        except Exception as e:
            logger.error(f"获取资产详情失败: {e}")
            return f"❌ 获取资产详情失败: {str(e)}"


class CreateAssetTool(BaseTool):
    """创建资产"""

    name = "create_asset"
    description = (
        "创建新资产（入库登记）。适用于车辆、电脑、设备、办公家具等任何类型。"
        "当用户说'创建资产'、'新增设备'、'资产入库'时调用。"
    )
    required_role = "admin"
    is_irreversible = True
    confirmation_message = "⚠️ 即将创建新资产记录，确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "asset_code": {
                "type": "string",
                "description": "资产编号（如: PC-2026-001）",
                "maxLength": 50,
            },
            "name": {
                "type": "string",
                "description": "资产名称",
                "maxLength": 100,
            },
            "asset_type": {
                "type": "string",
                "description": "资产类型（如: vehicle, computer, furniture, equipment）",
                "maxLength": 50,
            },
            "department_id": {
                "type": "string",
                "description": "所属部门ID（可选）",
            },
            "value": {
                "type": "number",
                "description": "资产价值（可选）",
                "minimum": 0,
                "maximum": 999999999,
            },
            "purchase_date": {
                "type": "string",
                "description": "购置日期 YYYY-MM-DD（可选）",
            },
            "metadata": {
                "type": "object",
                "description": "附加信息（可选，如车牌号、序列号等）",
            },
        },
        "required": ["asset_code", "name", "asset_type"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        asset_code = args.get("asset_code", "").strip()
        name = args.get("name", "").strip()
        asset_type = args.get("asset_type", "").strip()

        if not asset_code or not name or not asset_type:
            return "❌ 资产编号、名称、类型不能为空"

        if args.get("department_id"):
            if err := _validate_uuid(args["department_id"], "department_id"):
                return f"❌ {err}"

        data = {
            "asset_code": asset_code,
            "name": name,
            "asset_type": asset_type,
        }

        for field in ["department_id", "value", "purchase_date", "metadata"]:
            if args.get(field) is not None:
                data[field] = args[field]

        try:
            asset = await asset_service.create_asset(
                org_id=org_id,
                data=data,
                db=client,
            )

            return (
                f"✅ 资产创建成功！\n\n"
                f"- 名称: {asset.get('name')}\n"
                f"- 编号: {asset.get('asset_code')}\n"
                f"- 类型: {asset.get('asset_type')}\n"
                f"- 状态: 闲置\n"
                f"- ID: {asset['id']}\n\n"
                f"您可以继续更新资产详情或分配给员工。"
            )

        except Exception as e:
            logger.error(f"创建资产失败: {e}")
            return f"❌ 创建资产失败: {str(e)}"


class UpdateAssetTool(BaseTool):
    """更新资产"""

    name = "update_asset"
    description = (
        "更新资产信息或状态。"
        "当用户说'更新资产'、'修改资产状态'、'资产维修'时调用。"
    )
    required_role = "admin"

    parameters = {
        "type": "object",
        "properties": {
            "asset_id": {
                "type": "string",
                "description": "资产ID",
            },
            "status": {
                "type": "string",
                "description": "资产状态: idle/in_use/maintenance/scrapped",
                "enum": ["idle", "in_use", "maintenance", "scrapped"],
            },
            "department_id": {
                "type": "string",
                "description": "所属部门ID（可选）",
            },
            "current_user_id": {
                "type": "string",
                "description": "当前使用人ID（可选）",
            },
            "name": {
                "type": "string",
                "description": "资产名称（可选）",
                "maxLength": 100,
            },
        },
        "required": ["asset_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        asset_id = args.get("asset_id")

        if err := _validate_uuid(asset_id, "asset_id"):
            return f"❌ {err}"

        updates = {}
        if args.get("status"):
            updates["status"] = args["status"]
        if args.get("department_id"):
            if err := _validate_uuid(args["department_id"], "department_id"):
                return f"❌ {err}"
            updates["department_id"] = args["department_id"]
        if args.get("current_user_id"):
            if err := _validate_uuid(args["current_user_id"], "current_user_id"):
                return f"❌ {err}"
            updates["current_user_id"] = args["current_user_id"]
        if args.get("name"):
            updates["name"] = args["name"]

        if not updates:
            return "❌ 请提供至少一个要更新的字段"

        try:
            asset = await asset_service.update_asset(
                asset_id=asset_id,
                updates=updates,
                db=client,
            )

            return f"✅ 资产已更新: {asset.get('name')} [{asset.get('asset_code')}]"

        except Exception as e:
            logger.error(f"更新资产失败: {e}")
            return f"❌ 更新资产失败: {str(e)}"


class TransferAssetTool(BaseTool):
    """资产转移/领用/归还"""

    name = "transfer_asset"
    description = (
        "资产转移、领用或归还。"
        "当用户说'领用资产'、'归还设备'、'资产转移'、'资产报废'时调用。"
    )
    is_irreversible = True
    confirmation_message = "⚠️ 即将进行资产转移操作，确认继续？"

    parameters = {
        "type": "object",
        "properties": {
            "asset_id": {
                "type": "string",
                "description": "资产ID",
            },
            "transfer_type": {
                "type": "string",
                "description": "转移类型",
                "enum": ["allocate", "return", "transfer", "scrap"],
            },
            "to_user_id": {
                "type": "string",
                "description": "目标使用人ID（领用/转移时需要）",
            },
            "to_department_id": {
                "type": "string",
                "description": "目标部门ID（可选）",
            },
            "reason": {
                "type": "string",
                "description": "原因说明",
                "maxLength": 500,
            },
        },
        "required": ["asset_id", "transfer_type"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        asset_id = args.get("asset_id")
        transfer_type = args.get("transfer_type")

        if err := _validate_uuid(asset_id, "asset_id"):
            return f"❌ {err}"

        to_user_id = args.get("to_user_id")
        to_department_id = args.get("to_department_id")

        if transfer_type in ("allocate", "transfer") and not to_user_id:
            return f"❌ {transfer_type} 操作需要指定 to_user_id"

        if to_user_id:
            if err := _validate_uuid(to_user_id, "to_user_id"):
                return f"❌ {err}"
        if to_department_id:
            if err := _validate_uuid(to_department_id, "to_department_id"):
                return f"❌ {err}"

        type_labels = {
            "allocate": "领用",
            "return": "归还",
            "transfer": "转移",
            "scrap": "报废",
        }

        try:
            # 获取当前资产信息以便记录 from
            asset = await asset_service.get_asset_detail(asset_id=asset_id, db=client)
            if not asset:
                return f"❌ 未找到ID为 {asset_id} 的资产。"

            from_user_id = asset.get("current_user_id")
            from_department_id = asset.get("department_id")

            await asset_service.transfer_asset(
                org_id=org_id,
                asset_id=asset_id,
                transfer_type=transfer_type,
                operator_id=user_id,
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                from_department_id=from_department_id,
                to_department_id=to_department_id,
                reason=args.get("reason"),
                db=client,
            )

            return (
                f"✅ 资产{type_labels.get(transfer_type, transfer_type)}成功！\n\n"
                f"- 资产: {asset.get('name')} [{asset.get('asset_code')}]\n"
                f"- 操作: {type_labels.get(transfer_type, transfer_type)}"
            )

        except Exception as e:
            logger.error(f"资产转移失败: {e}")
            return f"❌ 资产转移失败: {str(e)}"


class AssetStatisticsTool(BaseTool):
    """资产统计"""

    name = "asset_statistics"
    description = (
        "获取资产统计数据（总量、在用率、价值等）。"
        "当用户说'资产统计'、'设备利用率'、'有多少资产'时调用。"
    )

    parameters = {
        "type": "object",
        "properties": {
            "asset_type": {
                "type": "string",
                "description": "资产类型（可选，不填则统计全部）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        try:
            stats = await asset_service.get_asset_statistics(
                org_id=org_id,
                asset_type=args.get("asset_type"),
                db=client,
            )

            type_label = args.get("asset_type", "全部")

            return (
                f"📊 资产统计 ({type_label}):\n\n"
                f"- 资产总数: {stats.get('total_count')}\n"
                f"- 使用中: {stats.get('in_use_count')}\n"
                f"- 闲置: {stats.get('idle_count')}\n"
                f"- 维修中: {stats.get('maintenance_count')}\n"
                f"- 已报废: {stats.get('scrapped_count')}\n"
                f"- 利用率: {stats.get('utilization_rate')}%\n"
                f"- 资产总值: ¥{stats.get('total_value'):,.0f}"
            )

        except Exception as e:
            logger.error(f"获取资产统计失败: {e}")
            return f"❌ 获取资产统计失败: {str(e)}"
