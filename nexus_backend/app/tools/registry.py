"""
工具注册中心 — 装饰器自动发现机制

提供 @register_tool 装饰器，允许工具类在定义时自动注册到全局注册表，
消除 __init__.py 中手工维护大字典的需要。

当前阶段：与旧的 _TOOL_MODULES 字典共存，作为新的注册基础设施。
后续渐进式迁移：逐步给各工具类加上装饰器，最终移除硬编码字典。

用法::

    from app.tools.registry import register_tool
    from app.tools.base_tool import BaseTool

    @register_tool(name="my_tool", category="crm", description="示例工具")
    class MyTool(BaseTool):
        ...
"""

import importlib
import logging
import pkgutil
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolInfo:
    """已注册工具的元信息。"""

    name: str
    category: str
    description: str
    tool_class: type
    is_irreversible: bool = False
    required_role: str = "all"
    risk: str = "low"
    owner: str = "platform"
    timeout_s: int | None = None
    idempotent: bool = True
    side_effect: bool = False
    extras: dict[str, Any] = field(default_factory=dict)

    # 缓存的实例（懒加载）
    _instance: Any = field(default=None, repr=False)

    def get_instance(self) -> Any:
        """获取工具实例（懒加载单例）。"""
        if self._instance is None:
            self._instance = self.tool_class()
        return self._instance

    def to_manifest(self) -> dict[str, Any]:
        """Return governance metadata for audits, prompts and admin UIs."""
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "required_role": self.required_role,
            "risk": self.risk,
            "owner": self.owner,
            "timeout_s": self.timeout_s,
            "idempotent": self.idempotent,
            "side_effect": self.side_effect,
            "is_irreversible": self.is_irreversible,
            "extras": self.extras,
        }


# ---------------------------------------------------------------------------
# 全局注册表
# ---------------------------------------------------------------------------
_TOOL_REGISTRY: dict[str, ToolInfo] = {}


def register_tool(
    name: str,
    category: str = "general",
    description: str = "",
    is_irreversible: bool = False,
    required_role: str = "all",
    **extras: Any,
):
    """装饰器：将工具类注册到全局注册表。

    Args:
        name: 工具唯一名称（对应 BaseTool.name）
        category: 工具分类，如 "crm", "hr", "finance", "vmd" 等
        description: 工具简要描述
        is_irreversible: 是否为不可逆操作
        required_role: 需要的用户角色
        **extras: 额外元信息

    Returns:
        装饰后的原始类（不做任何修改）

    Example::

        @register_tool(name="get_customers", category="crm", description="查询客户")
        class GetCustomersTool(BaseTool):
            ...
    """

    def decorator(cls: type) -> type:
        if name in _TOOL_REGISTRY:
            logger.warning(
                "工具 %r 已注册 (class=%s)，将被 %s 覆盖",
                name,
                _TOOL_REGISTRY[name].tool_class.__name__,
                cls.__name__,
            )

        _TOOL_REGISTRY[name] = ToolInfo(
            name=name,
            category=category,
            description=description,
            tool_class=cls,
            is_irreversible=is_irreversible,
            required_role=required_role,
            risk=extras.pop("risk", "high" if is_irreversible else "low"),
            owner=extras.pop("owner", "platform"),
            timeout_s=extras.pop("timeout_s", None),
            idempotent=extras.pop("idempotent", not is_irreversible),
            side_effect=extras.pop("side_effect", is_irreversible),
            extras=extras,
        )
        logger.debug(
            "装饰器注册工具: %s (class=%s, category=%s)", name, cls.__name__, category
        )
        return cls

    return decorator


# ---------------------------------------------------------------------------
# 自动发现
# ---------------------------------------------------------------------------


def auto_discover_tools(package_path: str = "app.tools") -> dict[str, ToolInfo]:
    """扫描指定包下所有模块，import 触发 @register_tool 装饰器注册。

    单个模块 import 失败不影响整体加载——只记录 warning 并跳过。

    Args:
        package_path: 要扫描的包的 dotted path，默认 "app.tools"

    Returns:
        当前注册表的快照（副本）
    """
    try:
        package = importlib.import_module(package_path)
    except ImportError:
        logger.warning("无法导入包 %s，跳过自动发现", package_path)
        return dict(_TOOL_REGISTRY)

    pkg_paths = getattr(package, "__path__", None)
    if pkg_paths is None:
        logger.warning("%s 不是一个包（没有 __path__），跳过自动发现", package_path)
        return dict(_TOOL_REGISTRY)

    for _importer, modname, ispkg in pkgutil.iter_modules(
        pkg_paths, f"{package_path}."
    ):
        # 跳过子包、__init__、base_tool、registry 自身
        if ispkg:
            continue
        short = modname.rsplit(".", 1)[-1]
        if short in ("__init__", "base_tool", "registry"):
            continue

        try:
            importlib.import_module(modname)
        except Exception:
            logger.warning("自动发现: 导入 %s 失败，已跳过", modname, exc_info=True)
            continue

    logger.debug("自动发现完成，共 %d 个装饰器注册的工具", len(_TOOL_REGISTRY))
    return dict(_TOOL_REGISTRY)


def get_all_tool_manifests() -> list[dict[str, Any]]:
    """Return all registered tools as governance manifests."""
    return [info.to_manifest() for info in _TOOL_REGISTRY.values()]


# ---------------------------------------------------------------------------
# 查询接口
# ---------------------------------------------------------------------------


def get_tool_info(name: str) -> ToolInfo | None:
    """按名称获取已注册工具的元信息。"""
    return _TOOL_REGISTRY.get(name)


def get_all_tool_infos() -> dict[str, ToolInfo]:
    """获取所有已注册工具的元信息（返回副本）。"""
    return dict(_TOOL_REGISTRY)


def get_tools_by_category(category: str) -> dict[str, ToolInfo]:
    """按分类筛选已注册工具。"""
    return {k: v for k, v in _TOOL_REGISTRY.items() if v.category == category}


def get_all_categories() -> set[str]:
    """获取所有已注册工具的分类集合。"""
    return {v.category for v in _TOOL_REGISTRY.values()}


def is_registered(name: str) -> bool:
    """检查工具是否已通过装饰器注册。"""
    return name in _TOOL_REGISTRY
