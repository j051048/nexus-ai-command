"""
插件/扩展市场服务

提供:
- 内置插件注册表管理
- 插件安装/卸载
- 插件配置管理
- 已安装插件查询
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class PluginMarketplaceService:
    """插件市场服务"""

    # 内置插件注册表
    BUILTIN_PLUGINS: List[Dict[str, Any]] = [
        {
            "id": "plugin_kingdee",
            "name": "金蝶 ERP 集成",
            "description": "连接金蝶 ERP 系统，同步进销存和财务数据",
            "category": "erp",
            "version": "1.0.0",
            "icon": "database",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 1280,
            "rating": 4.5,
            "config_schema": {
                "api_url": {
                    "type": "text",
                    "label": "API 地址",
                    "required": True,
                    "placeholder": "https://your-kingdee-instance.com/api",
                },
                "api_key": {
                    "type": "password",
                    "label": "API 密钥",
                    "required": True,
                    "placeholder": "输入 API 密钥",
                },
            },
        },
        {
            "id": "plugin_wecom_bot",
            "name": "企业微信机器人",
            "description": "通过企微群机器人推送通知和报告",
            "category": "notification",
            "version": "1.0.0",
            "icon": "message-circle",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 3560,
            "rating": 4.8,
            "config_schema": {
                "webhook_url": {
                    "type": "text",
                    "label": "Webhook 地址",
                    "required": True,
                    "placeholder": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
                },
            },
        },
        {
            "id": "plugin_email_digest",
            "name": "邮件日报摘要",
            "description": "每日自动发送工作摘要邮件",
            "category": "productivity",
            "version": "1.0.0",
            "icon": "mail",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 2100,
            "rating": 4.3,
            "config_schema": {
                "recipients": {
                    "type": "text",
                    "label": "收件人",
                    "required": True,
                    "placeholder": "多个邮箱以逗号分隔",
                },
                "send_time": {
                    "type": "text",
                    "label": "发送时间",
                    "required": False,
                    "placeholder": "18:00 (默认)",
                },
            },
        },
        {
            "id": "plugin_data_backup",
            "name": "数据自动备份",
            "description": "定期自动备份组织数据到指定存储",
            "category": "security",
            "version": "1.0.0",
            "icon": "shield",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 980,
            "rating": 4.6,
            "config_schema": {},
        },
        {
            "id": "plugin_dingtalk",
            "name": "钉钉集成",
            "description": "连接钉钉工作台，同步审批和通知",
            "category": "notification",
            "version": "1.0.0",
            "icon": "bell",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 2800,
            "rating": 4.4,
            "config_schema": {
                "app_key": {
                    "type": "text",
                    "label": "AppKey",
                    "required": True,
                    "placeholder": "钉钉应用 AppKey",
                },
                "app_secret": {
                    "type": "password",
                    "label": "AppSecret",
                    "required": True,
                    "placeholder": "钉钉应用 AppSecret",
                },
            },
        },
        {
            "id": "plugin_ai_report",
            "name": "AI 智能报表",
            "description": "自动生成周报、月报和数据分析报告",
            "category": "productivity",
            "version": "1.0.0",
            "icon": "bar-chart-3",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 1750,
            "rating": 4.7,
            "config_schema": {
                "report_type": {
                    "type": "text",
                    "label": "报表类型",
                    "required": False,
                    "placeholder": "weekly/monthly",
                },
            },
        },
        {
            "id": "plugin_yonyou",
            "name": "用友 U8 集成",
            "description": "对接用友 U8 财务与供应链管理系统",
            "category": "erp",
            "version": "1.0.0",
            "icon": "server",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 890,
            "rating": 4.2,
            "config_schema": {
                "server_url": {
                    "type": "text",
                    "label": "服务器地址",
                    "required": True,
                    "placeholder": "https://u8-server.example.com",
                },
                "token": {
                    "type": "password",
                    "label": "访问令牌",
                    "required": True,
                    "placeholder": "输入访问令牌",
                },
            },
        },
        {
            "id": "plugin_compliance_check",
            "name": "合规审查助手",
            "description": "自动检查文档和流程的合规性",
            "category": "security",
            "version": "1.0.0",
            "icon": "shield-check",
            "is_builtin": True,
            "author": "Nexus 官方",
            "downloads": 670,
            "rating": 4.1,
            "config_schema": {},
        },
    ]

    # 插件ID到插件的映射 (缓存)
    _plugin_map: Dict[str, Dict] = {}

    def __init__(self):
        self._plugin_map = {p["id"]: p for p in self.BUILTIN_PLUGINS}

    async def list_plugins(
        self,
        org_id: Optional[str] = None,
        category: Optional[str] = None,
        db: Any = None,
    ) -> List[Dict]:
        """列出所有可用插件，附带安装状态"""
        plugins = list(self.BUILTIN_PLUGINS)

        # 按分类筛选
        if category and category != "all":
            plugins = [p for p in plugins if p.get("category") == category]

        # 如果有 org_id，标记已安装状态
        installed_ids: set = set()
        if org_id and db:
            try:
                result = db.table("installed_plugins").select("plugin_id, is_active, config").eq(
                    "organization_id", org_id
                ).execute()
                if result.data:
                    for row in result.data:
                        installed_ids.add(row["plugin_id"])
            except Exception as e:
                logger.warning(f"Failed to fetch installed plugins: {e}")

        # 附加安装状态
        for plugin in plugins:
            plugin["installed"] = plugin["id"] in installed_ids

        return plugins

    async def get_plugin(self, plugin_id: str) -> Optional[Dict]:
        """获取单个插件详情"""
        return self._plugin_map.get(plugin_id)

    async def install_plugin(
        self,
        org_id: str,
        plugin_id: str,
        config: Optional[Dict] = None,
        db: Any = None,
    ) -> Dict:
        """安装插件到组织"""
        plugin = self._plugin_map.get(plugin_id)
        if not plugin:
            raise ValueError(f"插件不存在: {plugin_id}")

        # 验证必填配置
        schema = plugin.get("config_schema", {})
        config = config or {}
        for key, field_def in schema.items():
            if field_def.get("required") and not config.get(key):
                raise ValueError(f"缺少必填配置: {field_def.get('label', key)}")

        if db:
            try:
                result = db.table("installed_plugins").upsert(
                    {
                        "organization_id": org_id,
                        "plugin_id": plugin_id,
                        "config": config,
                        "is_active": True,
                        "updated_at": datetime.utcnow().isoformat(),
                    },
                    on_conflict="organization_id,plugin_id",
                ).execute()
                logger.info(f"Plugin {plugin_id} installed for org {org_id}")
            except Exception as e:
                logger.error(f"Failed to install plugin: {e}")
                raise

        return {
            **plugin,
            "installed": True,
            "config": config,
            "is_active": True,
            "installed_at": datetime.utcnow().isoformat(),
        }

    async def uninstall_plugin(
        self, org_id: str, plugin_id: str, db: Any = None
    ) -> bool:
        """从组织卸载插件"""
        if db:
            try:
                db.table("installed_plugins").delete().eq(
                    "organization_id", org_id
                ).eq("plugin_id", plugin_id).execute()
                logger.info(f"Plugin {plugin_id} uninstalled for org {org_id}")
            except Exception as e:
                logger.error(f"Failed to uninstall plugin: {e}")
                raise
        return True

    async def update_plugin_config(
        self, org_id: str, plugin_id: str, config: Dict, db: Any = None
    ) -> Dict:
        """更新插件配置"""
        plugin = self._plugin_map.get(plugin_id)
        if not plugin:
            raise ValueError(f"插件不存在: {plugin_id}")

        if db:
            try:
                db.table("installed_plugins").update(
                    {
                        "config": config,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                ).eq("organization_id", org_id).eq(
                    "plugin_id", plugin_id
                ).execute()
                logger.info(f"Plugin {plugin_id} config updated for org {org_id}")
            except Exception as e:
                logger.error(f"Failed to update plugin config: {e}")
                raise

        return {**plugin, "config": config, "installed": True}

    async def get_installed_plugins(
        self, org_id: str, db: Any = None
    ) -> List[Dict]:
        """获取组织已安装的插件列表"""
        installed = []

        if db:
            try:
                result = db.table("installed_plugins").select("*").eq(
                    "organization_id", org_id
                ).eq("is_active", True).execute()

                if result.data:
                    for row in result.data:
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
                                }
                            )
            except Exception as e:
                logger.warning(f"Failed to fetch installed plugins: {e}")

        return installed


plugin_marketplace_service = PluginMarketplaceService()
