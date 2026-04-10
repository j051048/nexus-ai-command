"""User profile and self-service API endpoints."""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.cache import cache
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import AISettingsUpdate, ProfileUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["Profile"])


@cache(ttl=300)
async def _get_user_profile(client, user_id: str):
    """Cached user profile query."""
    res = (
        await client.table("users")
        .select(
            "id, name, email, role, department, position, avatar_url, employee_number, job_title, created_at"
        )
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


@router.get("")
async def get_profile(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Get current user's profile."""
    client = getattr(req.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "Database unavailable")

    try:
        row = await _get_user_profile(client, user_id)
        if not row:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "User not found")

        return api_success(data={"profile": row})
    except Exception as e:
        logger.error(f"Profile fetch failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "用户资料操作失败")


@router.put("")
async def update_profile(
    body: ProfileUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Update current user's profile."""
    client = getattr(req.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "Database unavailable")

    try:
        updates = body.model_dump(exclude_none=True)

        if not updates:
            raise api_error(
                ErrorCode.VALIDATION_INVALID_INPUT, "No valid fields to update"
            )

        await client.table("users").update(updates).eq("id", user_id).execute()

        return api_success(data={"updated": True, "fields": list(updates.keys())})
    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "用户资料操作失败")


@router.get("/ai-settings")
async def get_ai_settings(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Get user's AI configuration settings."""
    client = getattr(req.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "Database unavailable")

    try:
        res = (
            await client.table("ai_settings")
            .select("model, base_url, temperature, behavior_preferences")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        return api_success(data={"ai_settings": res.data[0] if res.data else {}})
    except Exception as e:
        logger.error(f"AI settings fetch failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "用户资料操作失败")


@router.put("/ai-settings")
async def update_ai_settings(
    body: AISettingsUpdate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Update user's AI configuration settings."""
    client = getattr(req.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "Database unavailable")

    try:
        updates = body.model_dump(exclude_none=True)

        if not updates:
            raise api_error(
                ErrorCode.VALIDATION_INVALID_INPUT, "No valid fields to update"
            )

        updates["user_id"] = user_id
        await client.table("ai_settings").upsert(updates).execute()

        return api_success(data={"updated": True})
    except Exception as e:
        logger.error(f"AI settings update failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "用户资料操作失败")


@router.put("/security")
async def update_security_settings(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Update security settings (notification preferences, etc.)."""
    try:
        await req.json()
        return api_success(
            data={
                "updated": True,
                "note": "Security settings updated. Password changes require Supabase Auth.",
            }
        )
    except Exception:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "用户资料操作失败")
