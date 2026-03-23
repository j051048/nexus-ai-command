"""
系统配置工具集
提供租户级别的可配置化能力
"""

import logging
from typing import Any

from app.services.system_config_service import system_config_service

from .base_tool import BaseTool
from ._shared import _get_client
from app.tools._shared import safe_tool_error

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ============================================================================
# 系统配置工具
# ============================================================================


class ListSystemConfigsTool(BaseTool):
    """查询系统配置列表"""

    name = "list_system_configs"
    description = (
        "查询租户的系统配置列表，支持按配置类型筛选"
    )
    domain = "admin"
    examples = [
        {"input": {}, "output_summary": "返回当前租户的所有配置项，按类型分组展示"},
        {"input": {"config_type": "asset_status"}, "output_summary": "仅返回资产状态相关的配置项"},
    ]
    gotchas = "需要用户已登录且有组织信息。返回结果按配置类型分组。"
    related_tools = ["update_system_config"]

    parameters = {
        "type": "object",
        "properties": {
            "config_type": {
                "type": "string",
                "description": "配置类型: asset_status/work_order_type/priority等",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        config_type = args.get("config_type")

        try:
            configs = await system_config_service.list_configs(
                org_id=org_id,
                config_type=config_type,
                db=client,
            )

            if not configs:
                return "当前暂无配置项。"

            # 按 config_type 分组
            grouped = {}
            for cfg in configs:
                ct = cfg.get("config_type", "unknown")
                if ct not in grouped:
                    grouped[ct] = []
                grouped[ct].append(cfg)

            lines = [f"📋 共找到 {len(configs)} 个配置项:\n"]
            for ct, items in grouped.items():
                lines.append(f"\n**{ct}** ({len(items)}项):")
                for item in items:
                    value = item.get("config_value", {})
                    label = value.get("label", item.get("config_key"))
                    color = value.get("color", "")
                    icon = value.get("icon", "")
                    lines.append(f"  - {label} (key: {item.get('config_key')}) {icon} {color}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询配置列表失败: {e}")
            return safe_tool_error(e, "查询配置列表")


class UpdateSystemConfigTool(BaseTool):
    """更新系统配置"""

    name = "update_system_config"
    description = "创建或更新租户的系统配置项"
    domain = "admin"
    examples = [
        {"input": {"config_type": "asset_status", "config_key": "maintenance", "label": "维护中", "color": "#FFA500"}, "output_summary": "创建或更新一个资产状态配置项"},
        {"input": {"config_type": "priority", "config_key": "urgent", "label": "紧急", "icon": "alert"}, "output_summary": "创建一个带图标的优先级配置项"},
    ]
    gotchas = "此操作不可逆，仅管理员可用。配置类型、配置键和显示标签为必填项。变更会影响全局行为。"
    related_tools = ["list_system_configs"]
    required_role = "admin"
    is_irreversible = True  # HITL: 系统配置变更影响全局行为

    parameters = {
        "type": "object",
        "properties": {
            "config_type": {
                "type": "string",
                "description": "配置类型: asset_status/work_order_type/priority等",
            },
            "config_key": {
                "type": "string",
                "description": "配置键（英文标识）",
            },
            "label": {
                "type": "string",
                "description": "显示标签（中文名称）",
            },
            "color": {
                "type": "string",
                "description": "颜色代码（可选）",
            },
            "icon": {
                "type": "string",
                "description": "图标名称（可选）",
            },
            "sort_order": {
                "type": "integer",
                "description": "排序（可选）",
                "default": 0,
            },
        },
        "required": ["config_type", "config_key", "label"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        config_type = args.get("config_type")
        config_key = args.get("config_key")
        label = args.get("label")
        color = args.get("color")
        icon = args.get("icon")
        sort_order = args.get("sort_order", 0)

        config_value = {"label": label}
        if color:
            config_value["color"] = color
        if icon:
            config_value["icon"] = icon

        try:
            await system_config_service.upsert_config(
                org_id=org_id,
                config_type=config_type,
                config_key=config_key,
                config_value=config_value,
                sort_order=sort_order,
                db=client,
            )

            return (
                f"✅ 配置已保存！\n\n"
                f"- 类型: {config_type}\n"
                f"- 键: {config_key}\n"
                f"- 标签: {label}\n"
                f"- 颜色: {color or '未设置'}\n"
                f"- 图标: {icon or '未设置'}"
            )

        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return safe_tool_error(e, "保存配置")
