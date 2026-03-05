"""
Item 7: Permission Middleware
权限检查装饰器和 FastAPI 依赖项。
为路由提供声明式的权限控制。

Usage:
    @router.post("/some-action")
    async def some_action(user_id: str = Depends(require_permission("approval.create"))):
        ...

    # 带资源上下文
    @router.delete("/document/{doc_id}")
    async def delete_doc(
        doc_id: str,
        user_id: str = Depends(require_permission("document.delete")),
        request: Request,
    ):
        # 需要手动进行条件检查（如 is_owner），因为装饰器无法获取 resource
        ...
"""

import logging
from typing import Any

from fastapi import Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error
from app.services.permission_service import permission_service

logger = logging.getLogger(__name__)


def require_permission(permission: str):
    """
    FastAPI 依赖项工厂：检查用户是否拥有指定权限。

    基于用户角色检查权限。如果权限规则包含条件约束（如 is_owner），
    此依赖项仅检查角色是否匹配，条件需要在路由函数内手动验证。

    Args:
        permission: 权限标识（如 'approval.create', 'workflow.manage'）

    Returns:
        FastAPI 依赖项函数，返回 user_id

    Raises:
        HTTPException(403): 权限不足
    """

    async def checker(
        request: Request,
        user_id: str = Depends(get_current_user_id),
    ) -> str:
        db = getattr(request.state, "db", None)

        has_perm = await permission_service.check_permission(
            user_id=user_id,
            permission=permission,
            db=db,
        )

        if not has_perm:
            logger.warning(f"Permission denied: user={user_id}, permission={permission}")
            raise api_error(
                ErrorCode.AUTH_PERMISSION_DENIED,
                f"缺少权限: {permission}",
            )

        return user_id

    return checker


def require_permission_with_resource(permission: str):
    """
    增强版权限依赖项工厂：支持从请求体或路径参数提取资源上下文。

    适用于需要条件评估的权限（如 is_owner, same_department）。
    会尝试从 request.state 中获取 resource_context。

    Args:
        permission: 权限标识

    Returns:
        FastAPI 依赖项函数，返回 user_id
    """

    async def checker(
        request: Request,
        user_id: str = Depends(get_current_user_id),
    ) -> str:
        db = getattr(request.state, "db", None)

        # 尝试从 request.state 获取资源上下文
        resource = getattr(request.state, "resource_context", None)

        has_perm = await permission_service.check_permission(
            user_id=user_id,
            permission=permission,
            resource=resource,
            db=db,
        )

        if not has_perm:
            logger.warning(f"Permission denied: user={user_id}, permission={permission}, resource={resource}")
            raise api_error(
                ErrorCode.AUTH_PERMISSION_DENIED,
                f"缺少权限: {permission}",
            )

        return user_id

    return checker


async def check_permission_in_route(
    user_id: str,
    permission: str,
    resource: dict[str, Any] | None = None,
    db=None,
) -> bool:
    """
    在路由函数内手动检查权限的便捷函数。

    适用于需要在路由逻辑中动态决定资源上下文的场景。

    Args:
        user_id: 用户 ID
        permission: 权限标识
        resource: 资源上下文
        db: 数据库客户端

    Returns:
        True 如果有权限

    Raises:
        HTTPException(403): 权限不足
    """
    has_perm = await permission_service.check_permission(
        user_id=user_id,
        permission=permission,
        resource=resource,
        db=db,
    )

    if not has_perm:
        raise api_error(
            ErrorCode.AUTH_PERMISSION_DENIED,
            f"缺少权限: {permission}",
        )

    return True
