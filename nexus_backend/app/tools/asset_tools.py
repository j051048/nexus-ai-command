"""
资产管理工具集
提供通用资产管理功能（适用于车辆、电脑、设备等任何类型资产）
"""

import logging
from typing import Any

from app.services.asset_service import asset_service

from .base_tool import BaseTool
from ._shared import _get_client, _validate_uuid
from app.tools._shared import safe_tool_error

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ============================================================================
# 资产管理工具
# ============================================================================


class ListAssetsTool(BaseTool):
    """查询资产列表"""

    name = "list_assets"
    domain = "asset"
    description = "查询资产列表，支持按类型、状态、部门筛选"
    examples = [
        {"input": {}, "output_summary": "返回全部资产列表"},
        {"input": {"asset_type": "vehicle", "status": "idle"}, "output_summary": "返回闲置状态的车辆资产"},
        {"input": {"search": "笔记本"}, "output_summary": "按关键词搜索包含'笔记本'的资产"},
    ]
    related_tools = ["get_asset_detail", "create_asset", "asset_statistics"]
    gotchas = "状态可选值：idle/in_use/maintenance/scrapped。不传筛选条件则返回全部资产。"

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
            return safe_tool_error(e, "查询资产列表")


class GetAssetDetailTool(BaseTool):
    """获取资产详情"""

    name = "get_asset_detail"
    domain = "asset"
    description = "查询指定资产的详细信息，包括使用人、部门和附加字段"
    examples = [
        {"input": {"asset_id": "uuid-xxxx"}, "output_summary": "返回资产的完整信息，包括名称、编号、状态、使用人等"},
    ]
    related_tools = ["list_assets", "update_asset", "transfer_asset"]
    gotchas = "asset_id必须是有效的UUID格式。返回结果包含metadata附加字段（如车牌号、序列号）。"

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
            return safe_tool_error(e, "获取资产详情")


class CreateAssetTool(BaseTool):
    """创建资产"""

    name = "create_asset"
    domain = "asset"
    description = "创建新资产记录，适用于车辆、电脑、设备、办公家具等任意类型"
    examples = [
        {"input": {"asset_code": "PC-2026-001", "name": "联想笔记本", "asset_type": "computer"}, "output_summary": "创建一台电脑类型的资产"},
        {"input": {"asset_code": "VH-2026-003", "name": "丰田商务车", "asset_type": "vehicle", "value": 280000, "purchase_date": "2026-01-15"}, "output_summary": "创建一辆带价值和购置日期的车辆资产"},
    ]
    related_tools = ["list_assets", "update_asset", "transfer_asset"]
    gotchas = "asset_code、name、asset_type为必填。创建后默认状态为idle（闲置）。metadata可存储自定义扩展字段（如车牌号、序列号）。"
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

        if args.get("department_id") and (err := _validate_uuid(args["department_id"], "department_id")):
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
            return safe_tool_error(e, "创建资产")


class UpdateAssetTool(BaseTool):
    """更新资产"""

    name = "update_asset"
    domain = "asset"
    description = "更新指定资产的信息或状态，支持修改名称、状态、部门和使用人"
    examples = [
        {"input": {"asset_id": "uuid-xxxx", "status": "maintenance"}, "output_summary": "将资产状态更新为维修中"},
        {"input": {"asset_id": "uuid-xxxx", "current_user_id": "uuid-yyyy", "status": "in_use"}, "output_summary": "将资产分配给指定用户并设为使用中"},
    ]
    related_tools = ["get_asset_detail", "transfer_asset", "list_assets"]
    gotchas = "至少需要提供一个要更新的字段。状态可选值：idle/in_use/maintenance/scrapped。简单状态变更用此工具，涉及领用/归还/转移流程请用transfer_asset。"
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
            return safe_tool_error(e, "更新资产")


class TransferAssetTool(BaseTool):
    """资产转移/领用/归还"""

    name = "transfer_asset"
    domain = "asset"
    description = "执行资产领用、归还、转移或报废操作，自动记录流转历史"
    examples = [
        {"input": {"asset_id": "uuid-xxxx", "transfer_type": "allocate", "to_user_id": "uuid-yyyy"}, "output_summary": "将资产领用给指定员工"},
        {"input": {"asset_id": "uuid-xxxx", "transfer_type": "return", "reason": "项目结束"}, "output_summary": "归还资产并记录原因"},
        {"input": {"asset_id": "uuid-xxxx", "transfer_type": "scrap", "reason": "设备老化无法使用"}, "output_summary": "报废指定资产"},
    ]
    related_tools = ["get_asset_detail", "update_asset", "list_assets"]
    gotchas = "领用（allocate）和转移（transfer）操作必须指定to_user_id。归还（return）和报废（scrap）不需要to_user_id。此操作不可逆，需用户确认。"
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

        if to_user_id and (err := _validate_uuid(to_user_id, "to_user_id")):
            return f"❌ {err}"
        if to_department_id and (err := _validate_uuid(to_department_id, "to_department_id")):
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
            return safe_tool_error(e, "资产转移")


class AssetStatisticsTool(BaseTool):
    """资产统计"""

    name = "asset_statistics"
    domain = "asset"
    description = "获取资产统计数据，包括总量、各状态数量、利用率和总价值"
    examples = [
        {"input": {}, "output_summary": "返回全部资产的统计概况"},
        {"input": {"asset_type": "computer"}, "output_summary": "返回电脑类资产的统计数据"},
    ]
    related_tools = ["list_assets", "get_asset_detail"]
    gotchas = "不传asset_type则统计全部类型。返回的utilization_rate为百分比数值。"

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
            return safe_tool_error(e, "获取资产统计")
