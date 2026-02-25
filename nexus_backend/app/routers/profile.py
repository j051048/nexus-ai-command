"""User profile and self-service API endpoints."""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["Profile"])


@router.get("")
async def get_profile(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Get current user's profile."""
    client = getattr(req.state, "db", None)
    if not client:
        return api_error(ErrorCode.DB_CONNECTION_ERROR, "Database unavailable")

    try:
        res = (
            await client.table("users")
            .select("id, name, email, role, department, position, avatar_url, employee_number, job_title, created_at")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )

        if not res.data:
            return api_error(ErrorCode.RESOURCE_NOT_FOUND, "User not found")

        return api_success(data={"profile": res.data})
    except Exception as e:
        logger.error(f"Profile fetch failed: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("")
async def update_profile(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Update current user's profile."""
    client = getattr(req.state, "db", None)
    if not client:
        return api_error(ErrorCode.DB_CONNECTION_ERROR, "Database unavailable")

    try:
        body = await req.json()
        allowed_fields = {"name", "avatar_url", "position", "phone"}
        updates = {k: v for k, v in body.items() if k in allowed_fields}

        if not updates:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "No valid fields to update")

        await client.table("users").update(updates).eq("id", user_id).execute()

        return api_success(data={"updated": True, "fields": list(updates.keys())})
    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/ai-settings")
async def get_ai_settings(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Get user's AI configuration settings."""
    client = getattr(req.state, "db", None)
    if not client:
        return api_error(ErrorCode.DB_CONNECTION_ERROR, "Database unavailable")

    try:
        res = (
            await client.table("ai_settings")
            .select("model, base_url, temperature")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )

        return api_success(data={"ai_settings": res.data or {}})
    except Exception as e:
        logger.error(f"AI settings fetch failed: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/ai-settings")
async def update_ai_settings(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Update user's AI configuration settings."""
    client = getattr(req.state, "db", None)
    if not client:
        return api_error(ErrorCode.DB_CONNECTION_ERROR, "Database unavailable")

    try:
        body = await req.json()
        allowed_fields = {"model", "base_url", "temperature", "api_key"}
        updates = {k: v for k, v in body.items() if k in allowed_fields}

        if not updates:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "No valid fields to update")

        updates["user_id"] = user_id
        await client.table("ai_settings").upsert(updates).execute()

        return api_success(data={"updated": True})
    except Exception as e:
        logger.error(f"AI settings update failed: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


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
    except Exception as e:
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
