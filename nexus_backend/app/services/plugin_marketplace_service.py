"""Plugin marketplace service for the production launch.

Built-in plugins are real installable integration descriptors. The service
does not claim fabricated popularity metrics and validates required runtime
configuration before persisting an install.
"""

from __future__ import annotations

import inspect
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _field(
    field_type: str,
    label: str,
    *,
    required: bool = False,
    placeholder: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "type": field_type,
        "label": label,
        "required": required,
    }
    if placeholder:
        data["placeholder"] = placeholder
    return data


class PluginMarketplaceService:
    """Built-in plugin catalog and install/config persistence helpers."""

    BUILTIN_PLUGINS: list[dict[str, Any]] = [
        {
            "id": "plugin_kingdee",
            "name": "金蝶 ERP 集成",
            "description": "连接金蝶 ERP HTTP 网关，同步库存、财务和薪资数据。",
            "category": "erp",
            "version": "1.0.0",
            "icon": "database",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 0,
            "rating": None,
            "metadata_source": "builtin",
            "requires_connection_test": True,
            "config_schema": {
                "api_url": _field(
                    "text",
                    "API 地址",
                    required=True,
                    placeholder="https://kingdee.example.com/api",
                ),
                "api_key": _field("password", "API 密钥", required=True),
            },
        },
        {
            "id": "plugin_wecom_bot",
            "name": "企业微信机器人",
            "description": "通过企业微信群机器人发送通知和日报。",
            "category": "notification",
            "version": "1.0.0",
            "icon": "message-circle",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 0,
            "rating": None,
            "metadata_source": "builtin",
            "requires_connection_test": True,
            "config_schema": {
                "webhook_url": _field(
                    "text",
                    "Webhook 地址",
                    required=True,
                    placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
                ),
            },
        },
        {
            "id": "plugin_email_digest",
            "name": "邮件日报摘要",
            "description": "按计划向指定收件人发送工作摘要邮件。",
            "category": "productivity",
            "version": "1.0.0",
            "icon": "mail",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 0,
            "rating": None,
            "metadata_source": "builtin",
            "config_schema": {
                "recipients": _field(
                    "text", "收件人", required=True, placeholder="多个邮箱用逗号分隔"
                ),
                "send_time": _field("text", "发送时间", placeholder="18:00"),
            },
        },
        {
            "id": "plugin_data_backup",
            "name": "数据自动备份",
            "description": "定期导出组织数据到配置的备份存储。",
            "category": "security",
            "version": "1.0.0",
            "icon": "shield",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 0,
            "rating": None,
            "metadata_source": "builtin",
            "config_schema": {},
        },
        {
            "id": "plugin_dingtalk",
            "name": "钉钉集成",
            "description": "连接钉钉工作台，同步审批状态并发送业务通知。",
            "category": "notification",
            "version": "1.0.0",
            "icon": "bell",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 0,
            "rating": None,
            "metadata_source": "builtin",
            "requires_connection_test": True,
            "config_schema": {
                "app_key": _field("text", "AppKey", required=True),
                "app_secret": _field("password", "AppSecret", required=True),
            },
        },
        {
            "id": "plugin_ai_report",
            "name": "AI 智能报表",
            "description": "基于系统内数据生成周报、月报和经营分析报告。",
            "category": "productivity",
            "version": "1.0.0",
            "icon": "bar-chart-3",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 0,
            "rating": None,
            "metadata_source": "builtin",
            "config_schema": {
                "report_type": _field(
                    "text", "默认报表类型", placeholder="weekly/monthly"
                ),
            },
        },
        {
            "id": "plugin_yonyou",
            "name": "用友 U8 集成",
            "description": "对接用友 U8 HTTP 网关，读取财务与供应链数据。",
            "category": "erp",
            "version": "1.0.0",
            "icon": "server",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 0,
            "rating": None,
            "metadata_source": "builtin",
            "requires_connection_test": True,
            "config_schema": {
                "server_url": _field(
                    "text",
                    "服务地址",
                    required=True,
                    placeholder="https://u8.example.com",
                ),
                "token": _field("password", "访问令牌", required=True),
            },
        },
        {
            "id": "plugin_compliance_check",
            "name": "合规审查助手",
            "description": "检查文档、流程和营销内容中的合规风险。",
            "category": "security",
            "version": "1.0.0",
            "icon": "shield-check",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 0,
            "rating": None,
            "metadata_source": "builtin",
            "config_schema": {},
        },
    ]

    def __init__(self) -> None:
        self._plugin_map = {p["id"]: p for p in self.BUILTIN_PLUGINS}

    async def _execute(self, query: Any) -> Any:
        result = query.execute()
        if inspect.isawaitable(result):
            return await result
        return result

    async def list_plugins(
        self,
        org_id: str | None = None,
        category: str | None = None,
        db: Any = None,
    ) -> list[dict[str, Any]]:
        plugins = [dict(plugin) for plugin in self.BUILTIN_PLUGINS]
        if category and category != "all":
            plugins = [p for p in plugins if p.get("category") == category]

        installed: dict[str, dict[str, Any]] = {}
        if org_id and db:
            try:
                result = await self._execute(
                    db.table("installed_plugins")
                    .select("plugin_id, is_active, config, updated_at")
                    .eq("organization_id", org_id)
                )
                installed = {row["plugin_id"]: row for row in result.data or []}
            except Exception as exc:
                logger.warning("Failed to fetch installed plugins: %s", exc)

        for plugin in plugins:
            row = installed.get(plugin["id"])
            plugin["installed"] = bool(row and row.get("is_active", True))
            plugin["connection_status"] = self._connection_status(plugin, row)
            if row:
                plugin["updated_at"] = row.get("updated_at")
        return plugins

    async def get_plugin(self, plugin_id: str) -> dict[str, Any] | None:
        plugin = self._plugin_map.get(plugin_id)
        return dict(plugin) if plugin else None

    async def install_plugin(
        self,
        org_id: str,
        plugin_id: str,
        config: dict[str, Any] | None = None,
        db: Any = None,
    ) -> dict[str, Any]:
        plugin = self._require_plugin(plugin_id)
        cleaned_config = self._validate_config(plugin, config or {})
        now = datetime.now(UTC).isoformat()

        if db:
            await self._execute(
                db.table("installed_plugins").upsert(
                    {
                        "organization_id": org_id,
                        "plugin_id": plugin_id,
                        "config": cleaned_config,
                        "is_active": True,
                        "updated_at": now,
                    },
                    on_conflict="organization_id,plugin_id",
                )
            )
            logger.info("Plugin %s installed for org %s", plugin_id, org_id)

        return {
            **plugin,
            "installed": True,
            "config": cleaned_config,
            "is_active": True,
            "installed_at": now,
            "updated_at": now,
            "connection_status": "configured",
        }

    async def uninstall_plugin(
        self, org_id: str, plugin_id: str, db: Any = None
    ) -> bool:
        self._require_plugin(plugin_id)
        if db:
            await self._execute(
                db.table("installed_plugins")
                .delete()
                .eq("organization_id", org_id)
                .eq("plugin_id", plugin_id)
            )
            logger.info("Plugin %s uninstalled for org %s", plugin_id, org_id)
        return True

    async def update_plugin_config(
        self, org_id: str, plugin_id: str, config: dict[str, Any], db: Any = None
    ) -> dict[str, Any]:
        plugin = self._require_plugin(plugin_id)
        cleaned_config = self._validate_config(plugin, config)
        now = datetime.now(UTC).isoformat()

        if db:
            await self._execute(
                db.table("installed_plugins")
                .update({"config": cleaned_config, "updated_at": now})
                .eq("organization_id", org_id)
                .eq("plugin_id", plugin_id)
            )
            logger.info("Plugin %s config updated for org %s", plugin_id, org_id)

        return {
            **plugin,
            "config": cleaned_config,
            "installed": True,
            "updated_at": now,
            "connection_status": "configured",
        }

    async def get_installed_plugins(
        self, org_id: str, db: Any = None
    ) -> list[dict[str, Any]]:
        installed: list[dict[str, Any]] = []
        if not db:
            return installed

        try:
            result = await self._execute(
                db.table("installed_plugins")
                .select("*")
                .eq("organization_id", org_id)
                .eq("is_active", True)
            )
            for row in result.data or []:
                plugin = self._plugin_map.get(row["plugin_id"])
                if plugin:
                    installed.append(
                        {
                            **plugin,
                            "installed": True,
                            "is_active": row.get("is_active", True),
                            "config": row.get("config", {}),
                            "installed_at": row.get("installed_at"),
                            "updated_at": row.get("updated_at"),
                            "connection_status": self._connection_status(plugin, row),
                        }
                    )
        except Exception as exc:
            logger.warning("Failed to fetch installed plugins: %s", exc)
        return installed

    def _require_plugin(self, plugin_id: str) -> dict[str, Any]:
        plugin = self._plugin_map.get(plugin_id)
        if not plugin:
            raise ValueError(f"插件不存在: {plugin_id}")
        return dict(plugin)

    def _validate_config(
        self, plugin: dict[str, Any], config: dict[str, Any]
    ) -> dict[str, Any]:
        schema = plugin.get("config_schema") or {}
        cleaned: dict[str, Any] = {}
        for key, field_def in schema.items():
            raw_value = config.get(key)
            value = raw_value.strip() if isinstance(raw_value, str) else raw_value
            if field_def.get("required") and not value:
                raise ValueError(f"缺少必填配置: {field_def.get('label', key)}")
            if value:
                if key.endswith("_url") or key in {
                    "api_url",
                    "server_url",
                    "webhook_url",
                }:
                    if not str(value).startswith(("https://", "http://")):
                        raise ValueError(
                            f"{field_def.get('label', key)} 必须是 http(s) 地址"
                        )
                cleaned[key] = value
        return cleaned

    def _connection_status(
        self, plugin: dict[str, Any], install_row: dict[str, Any] | None
    ) -> str:
        if not install_row:
            return "not_installed"
        config = install_row.get("config") or {}
        if plugin.get("requires_connection_test"):
            return "configured" if config else "needs_configuration"
        return "ready"


plugin_marketplace_service = PluginMarketplaceService()
