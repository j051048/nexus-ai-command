"""
Item 7: Permissions Router
ABAC 权限管理 API 端点。
"""

import logging
from fastapi import APIRouter, Request, Depends
from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error, ErrorCode
from app.services.permission_service import permission_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/permissions", tags=["Permissions"])


@router.get("/me")
async def get_my_permissions(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    获取当前用户的完整权限列表。

    返回所有权限规则，标注当前用户是否拥有每项权限。
    对于含条件约束的权限，granted 仅反映角色匹配结果，
    实际访问时可能还需满足条件约束。
    """
    try:
        db = getattr(request.state, "db", None)

        permissions = await permission_service.get_user_permissions(
            user_id=user_id, db=db
        )

        # 统计
        granted_count = sum(1 for p in permissions if p["granted"])

        return api_success(
            data={
                "user_id": user_id,
                "permissions": permissions,
                "summary": {
                    "total": len(permissions),
                    "granted": granted_count,
                    "denied": len(permissions) - granted_count,
                },
            }
        )

    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error fetching permissions for {user_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/check/{permission:path}")
async def check_single_permission(
    request: Request,
    permission: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    检查当前用户是否拥有指定权限。

    路径参数中的 permission 支持点号分隔，如 approval.create。
    返回详细的权限评估结果，包括角色检查和条件评估过程。
    """
    try:
        db = getattr(request.state, "db", None)

        result = await permission_service.check_permission_detailed(
            user_id=user_id,
            permission=permission,
            db=db,
        )

        return api_success(
            data={
                "permission": result.permission,
                "granted": result.granted,
                "reason": result.reason,
                "evaluated_conditions": result.evaluated_conditions,
            }
        )

    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error checking permission {permission}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/roles/{role}")
async def get_role_permissions(
    role: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    获取指定角色拥有的权限列表。

    仅 founder 和 boss 可以查看其他角色的权限。
    """
    try:
        valid_roles = ["employee", "manager", "boss", "founder", "guest"]
        if role not in valid_roles:
            raise api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                f"无效角色: {role}，有效值: {', '.join(valid_roles)}",
            )

        permissions = permission_service.get_role_permissions(role)

        return api_success(
            data={
                "role": role,
                "permissions": permissions,
                "count": len(permissions),
            }
        )

    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error fetching role permissions for {role}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/all")
async def get_all_permission_rules(
    user_id: str = Depends(get_current_user_id),
):
    """
    获取所有权限规则定义。

    返回系统中定义的所有权限及其角色要求和条件约束。
    用于前端权限管理界面展示。
    """
    try:
        rules = permission_service.get_all_permissions()

        return api_success(
            data={
                "rules": rules,
                "total": len(rules),
                "role_hierarchy": permission_service.ROLE_HIERARCHY,
            }
        )

    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error fetching all permission rules: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
