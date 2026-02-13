"""
Plugin/extension system with registry and lifecycle management.

Provides extension points for third-party code to hook into the
agent pipeline, data export, and custom tool registration.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class PluginStatus(Enum):
    """Plugin lifecycle states."""
    REGISTERED = "registered"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


class ExtensionPoint(Enum):
    """Points where plugins can hook into the system."""
    PRE_CHAT = "pre_chat"           # Before LLM call
    POST_CHAT = "post_chat"         # After LLM response
    PRE_TOOL = "pre_tool"           # Before tool execution
    POST_TOOL = "post_tool"         # After tool execution
    CUSTOM_TOOL = "custom_tool"     # Register new tools
    DATA_EXPORT = "data_export"     # Export pipeline hook
    ON_ERROR = "on_error"           # Error handling hook


@dataclass
class PluginMetadata:
    """Metadata describing a plugin."""
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    extension_points: List[ExtensionPoint]
    status: PluginStatus = PluginStatus.REGISTERED
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
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
    async def initialize(self, config: Dict) -> bool:
        """Initialize the plugin with configuration."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up plugin resources."""
        ...


# Type alias for hook handlers
HookHandler = Callable[[Dict], Awaitable[Dict]]


class PluginSystemService:
    """Plugin registry, lifecycle management, and hook execution."""

    def __init__(self):
        self._plugins: Dict[str, BasePlugin] = {}
        self._metadata: Dict[str, PluginMetadata] = {}
        self._hooks: Dict[ExtensionPoint, List[HookHandler]] = {
            ep: [] for ep in ExtensionPoint
        }

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

    async def activate(self, plugin_id: str, config: Dict = None) -> bool:
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

    def add_hook(
        self, point: ExtensionPoint, handler: HookHandler, plugin_id: str = None
    ):
        """Register a hook handler at an extension point."""
        if plugin_id:
            handler._plugin_id = plugin_id  # type: ignore
        self._hooks[point].append(handler)

    async def run_hooks(
        self, point: ExtensionPoint, context: Dict
    ) -> Dict:
        """Execute all hooks at an extension point, passing context through."""
        for handler in self._hooks[point]:
            try:
                result = await handler(context)
                if isinstance(result, dict):
                    context.update(result)
            except Exception as e:
                logger.warning(f"Hook error at {point.value}: {e}")
        return context

    def list_plugins(self) -> List[Dict]:
        """List all registered plugins with their status."""
        return [m.to_dict() for m in self._metadata.values()]

    def get_plugin_status(self, plugin_id: str) -> Optional[Dict]:
        """Get status of a specific plugin."""
        metadata = self._metadata.get(plugin_id)
        return metadata.to_dict() if metadata else None


# Global instance
plugin_system_service = PluginSystemService()
