"""用户管理 API 路由"""

import logging
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["Users"])


class UserUpdate(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None
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
        result = await db.table("users").select("*").eq("id", user_id).single().execute()
        return api_success(data={"user": result.data})
    except Exception as e:
        logger.error(f"Failed to get profile: {e}")
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
        data = body.model_dump(exclude_none=True)
        result = await db.table("users").update(data).eq("id", user_id).execute()
        return api_success(data={"user": result.data[0] if result.data else None}, message="资料已更新")
    except Exception as e:
        logger.error(f"Failed to update profile: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "更新资料失败")
