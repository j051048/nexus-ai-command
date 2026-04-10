"""
GDPR compliance endpoints.

P1 Task: Implement data deletion and export.
"""

import logging

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gdpr", tags=["GDPR"])


@router.post("/delete-my-data")
async def delete_user_data(
    user_id: str = Depends(get_current_user_id),
):
    """
    Delete all user data (Right to Erasure).

    GDPR Article 17: Right to erasure ('right to be forgotten')
    """
    from app.core.database import supabase

    try:
        await supabase.rpc("delete_user_data", {"user_id_param": user_id}).execute()

        logger.info(f"[GDPR] Deleted all data for user {user_id}")
        return api_success(data={"user_id": user_id}, message="所有数据已删除")
    except Exception as e:
        logger.error(f"[GDPR] Delete failed for {user_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据删除失败")


@router.get("/export-my-data")
async def export_user_data(
    user_id: str = Depends(get_current_user_id),
):
    """
    Export all user data (Right to Data Portability).

    GDPR Article 20: Right to data portability
    """
    from app.core.database import supabase

    try:
        data = {}

        profile = (
            await supabase.table("users")
            .select("id, email, full_name, avatar_url, created_at, updated_at")
            .eq("id", user_id)
            .single()
            .execute()
        )
        data["profile"] = profile.data

        conversations = (
            await supabase.table("chat_sessions")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        data["conversations"] = conversations.data

        memories = (
            await supabase.table("conversation_memories")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        data["memories"] = memories.data

        logger.info(f"[GDPR] Exported data for user {user_id}")
        return api_success(data=data, message="数据导出成功")
    except Exception as e:
        logger.error(f"[GDPR] Export failed for {user_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "数据导出失败")
