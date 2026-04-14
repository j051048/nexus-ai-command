"""Agent工具分层配置 (DEPRECATED)

已废弃：工具路由已迁移到 node_helpers._DOMAIN_TOOL_MAP（16 域精细映射）
+ tool_embedding_index.py（语义检索精简）。

此文件保留仅为向后兼容，请勿新增引用。
"""

import warnings

# 空字典，保留接口兼容
TOOL_GROUPS: dict[str, list[str]] = {}


def get_tools_for_scene(scene: str) -> list[str]:
    """已废弃：请使用 node_helpers._get_tool_schemas() 代替。"""
    warnings.warn(
        "get_tools_for_scene() is deprecated. Use node_helpers._get_tool_schemas() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return []
