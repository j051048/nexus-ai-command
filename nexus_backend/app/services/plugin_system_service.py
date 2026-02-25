"""
Plugin/extension system with registry and lifecycle management.

Provides extension points for third-party code to hook into the
agent pipeline, data export, and custom tool registration.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """Plugin lifecycle states."""

    REGISTERED = "registered"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class ExtensionPoint(Enum):
    """Points where plugins can hook into the system."""

    PRE_CHAT = "pre_chat"  # Before LLM call
    POST_CHAT = "post_chat"  # After LLM response
    PRE_TOOL = "pre_tool"  # Before tool execution
    POST_TOOL = "post_tool"  # After tool execution
    CUSTOM_TOOL = "custom_tool"  # Register new tools
    DATA_EXPORT = "data_export"  # Export pipeline hook
    ON_ERROR = "on_error"  # Error handling hook


@dataclass
class PluginMetadata:
    """Metadata describing a plugin."""

    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    extension_points: list[ExtensionPoint]
    status: PluginStatus = PluginStatus.REGISTERED
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "extension_points": [ep.value for ep in self.extension_points],
            "status": self.status.value,
        }


class BasePlugin(ABC):
    """Abstract base class for plugins."""

    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        ...

    @abstractmethod
    async def initialize(self, config: dict) -> bool:
        """Initialize the plugin with configuration."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up plugin resources."""
        ...


# Type alias for hook handlers
HookHandler = Callable[[dict], Awaitable[dict]]


class PluginSystemService:
    """Plugin registry, lifecycle management, and hook execution."""

    def __init__(self):
        self._plugins: dict[str, BasePlugin] = {}
        self._metadata: dict[str, PluginMetadata] = {}
        self._hooks: dict[ExtensionPoint, list[HookHandler]] = {ep: [] for ep in ExtensionPoint}

    def register(self, plugin: BasePlugin) -> bool:
        """Register a plugin (does not activate it)."""
        metadata = plugin.get_metadata()
        if metadata.plugin_id in self._plugins:
            logger.warning(f"Plugin {metadata.plugin_id} already registered")
            return False

        self._plugins[metadata.plugin_id] = plugin
        self._metadata[metadata.plugin_id] = metadata
        metadata.status = PluginStatus.REGISTERED
        logger.info(f"Plugin registered: {metadata.name} v{metadata.version}")
        return True

    async def activate(self, plugin_id: str, config: dict = None) -> bool:
        """Activate a registered plugin."""
        plugin = self._plugins.get(plugin_id)
        metadata = self._metadata.get(plugin_id)
        if not plugin or not metadata:
            return False

        try:
            success = await plugin.initialize(config or metadata.config)
            if success:
                metadata.status = PluginStatus.ACTIVE
                logger.info(f"Plugin activated: {metadata.name}")
                return True
            else:
                metadata.status = PluginStatus.ERROR
                return False
        except Exception as e:
            metadata.status = PluginStatus.ERROR
            logger.error(f"Plugin {plugin_id} activation failed: {e}")
            return False

    async def deactivate(self, plugin_id: str) -> None:
        """Deactivate an active plugin."""
        plugin = self._plugins.get(plugin_id)
        metadata = self._metadata.get(plugin_id)
        if not plugin or not metadata:
            return

        try:
            await plugin.shutdown()
        except Exception as e:
            logger.warning(f"Plugin {plugin_id} shutdown error: {e}")

        metadata.status = PluginStatus.DISABLED

        # Remove its hooks
        for ep_hooks in self._hooks.values():
            ep_hooks[:] = [h for h in ep_hooks if getattr(h, "_plugin_id", None) != plugin_id]

    def add_hook(self, point: ExtensionPoint, handler: HookHandler, plugin_id: str = None):
        """Register a hook handler at an extension point."""
        if plugin_id:
            handler._plugin_id = plugin_id  # type: ignore
        self._hooks[point].append(handler)

    async def run_hooks(self, point: ExtensionPoint, context: dict) -> dict:
        """Execute all hooks at an extension point, passing context through."""
        for handler in self._hooks[point]:
            try:
                result = await handler(context)
                if isinstance(result, dict):
                    context.update(result)
            except Exception as e:
                logger.warning(f"Hook error at {point.value}: {e}")
        return context

    def list_plugins(self) -> list[dict]:
        """List all registered plugins with their status."""
        return [m.to_dict() for m in self._metadata.values()]

    def get_plugin_status(self, plugin_id: str) -> dict | None:
        """Get status of a specific plugin."""
        metadata = self._metadata.get(plugin_id)
        return metadata.to_dict() if metadata else None

    async def load_installed_plugins(self, org_id: str, db=None) -> int:
        """
        P1 Bridge: Load installed marketplace plugins into the hook system.

        Reads installed plugins from the DB (via PluginMarketplaceService) and
        registers lightweight hook handlers based on their category/type.

        Returns the number of plugins loaded.
        """
        try:
            from app.services.plugin_marketplace_service import plugin_marketplace_service

            installed = await plugin_marketplace_service.get_installed_plugins(org_id, db=db)
        except Exception as e:
            logger.warning(f"Failed to load installed plugins for org {org_id}: {e}")
            return 0

        loaded = 0
        for plugin_info in installed:
            plugin_id = plugin_info["id"]
            if plugin_id in self._plugins:
                continue  # Already registered

            category = plugin_info.get("category", "")
            config = plugin_info.get("config", {})

            # Create a marketplace bridge plugin
            bridge = _MarketplaceBridgePlugin(plugin_id, plugin_info["name"], category, config)
            if self.register(bridge):
                # Register category-specific hooks
                if category == "notification":
                    self.add_hook(ExtensionPoint.POST_CHAT, bridge.post_chat_notify, plugin_id)
                elif category == "erp":
                    self.add_hook(ExtensionPoint.POST_TOOL, bridge.post_tool_sync, plugin_id)
                elif category == "productivity":
                    self.add_hook(ExtensionPoint.DATA_EXPORT, bridge.data_export_hook, plugin_id)
                elif category == "security":
                    self.add_hook(ExtensionPoint.PRE_CHAT, bridge.pre_chat_compliance, plugin_id)

                loaded += 1
                logger.info(f"[PluginBridge] Loaded marketplace plugin: {plugin_id} ({category})")

        return loaded


class _MarketplaceBridgePlugin(BasePlugin):
    """Bridge adapter: wraps a marketplace plugin config into the hook system."""

    def __init__(self, plugin_id: str, name: str, category: str, config: dict):
        self._plugin_id = plugin_id
        self._name = name
        self._category = category
        self._config = config

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            plugin_id=self._plugin_id,
            name=self._name,
            version="1.0.0",
            description=f"Marketplace bridge: {self._category}",
            author="Nexus Marketplace",
            extension_points=[],
            config=self._config,
        )

    async def initialize(self, config: dict) -> bool:
        self._config = config
        return True

    async def shutdown(self) -> None:
        pass

    # ── Category-specific hook handlers ──

    async def post_chat_notify(self, context: dict) -> dict:
        """Notification plugins: forward AI responses to configured webhook."""
        webhook_url = self._config.get("webhook_url")
        if not webhook_url:
            return context
        try:
            import httpx

            ai_msg = context.get("ai_message")
            content = getattr(ai_msg, "content", "")[:500] if ai_msg else ""
            if content:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        webhook_url,
                        json={"msgtype": "text", "text": {"content": f"[Nexus AI] {content}"}},
                    )
        except Exception as e:
            logger.warning(f"[PluginBridge] Notification hook failed for {self._plugin_id}: {e}")
        return context

    async def post_tool_sync(self, context: dict) -> dict:
        """ERP plugins: log tool execution for audit/sync purposes."""
        logger.debug(f"[PluginBridge] ERP sync hook ({self._plugin_id}): {len(context.get('completed_tools', []))} tools")
        return context

    async def data_export_hook(self, context: dict) -> dict:
        """Productivity plugins: intercept data export for report generation."""
        logger.debug(f"[PluginBridge] Data export hook ({self._plugin_id})")
        return context

    async def pre_chat_compliance(self, context: dict) -> dict:
        """Security plugins: pre-chat compliance check (pass-through for now)."""
        logger.debug(f"[PluginBridge] Compliance check hook ({self._plugin_id})")
        return context


# Global instance
plugin_system_service = PluginSystemService()
