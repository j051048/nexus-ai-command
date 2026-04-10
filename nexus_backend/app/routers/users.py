"""用户管理 API 路由"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["Users"])


class UserUpdate(BaseModel):
    name: str | None = None
    avatar: str | None = None
    phone: str | None = None
    department: str | None = None


@router.get("/profile")
async def get_profile(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取用户资料"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        result = (
            await db.table("users").select("*").eq("id", user_id).single().execute()
        )
        return api_success(data={"user": result.data})
    except Exception as e:
        logger.error(f"Failed to get profile: {e}")
        if hasattr(e, "status_code"):
            raise
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "获取用户资料失败")


@router.put("/profile")
async def update_profile(
    body: UserUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新用户资料"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        data = body.model_dump(exclude_none=True)
        result = await db.table("users").update(data).eq("id", user_id).execute()
        return api_success(
            data={"user": result.data[0] if result.data else None}, message="资料已更新"
        )
    except Exception as e:
        logger.error(f"Failed to update profile: {e}")
        if hasattr(e, "status_code"):
            raise
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新资料失败")


@router.get("/org-members")
async def get_org_members(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取组织架构成员列表 (OA 中心使用)"""
    try:
        db = getattr(req.state, "db", None)
        if not db:
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据库连接不可用")
        org_id = getattr(req.state, "org_id", None)

        query = db.table("users").select("id, name, avatar, role, department")
        if org_id:
            query = query.eq("organization_id", str(org_id))
        result = await query.execute()
        return api_success(data={"members": result.data if result.data else []})
    except Exception as e:
        logger.error(f"Failed to fetch org members: {e}")
        if hasattr(e, "status_code"):
            raise
        # 降级处理：即使报错也返回空列表，防止前端白屏
        return api_success(data={"members": []})
