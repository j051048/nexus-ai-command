"""
Item 13: AI Conversation Memory API

Endpoints for managing user long-term AI conversation memories.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends

from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error, ErrorCode
from app.services.conversation_memory_service import conversation_memory_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memories", tags=["Conversation Memories"])


@router.get("")
async def get_memories(
    request: Request,
    category: Optional[str] = None,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
):
    """获取当前用户的记忆列表"""
    try:
        db = getattr(request.state, "db", None)

        memories = await conversation_memory_service.get_memories(
            user_id=user_id,
            category=category,
            limit=min(limit, 100),
            db=db,
        )

        return api_success(data=memories, message="记忆列表获取成功")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting memories: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("")
async def clear_memories(
    request: Request,
    category: Optional[str] = None,
    user_id: str = Depends(get_current_user_id),
):
    """清除当前用户记忆（可按分类）"""
    try:
        db = getattr(request.state, "db", None)

        count = await conversation_memory_service.clear_memories(
            user_id=user_id,
            category=category,
            db=db,
        )

        return api_success(
            data={"deleted_count": count},
            message=f"已清除 {count} 条记忆",
        )
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error clearing memories: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/{memory_id}")
async def delete_memory(
    request: Request,
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """删除单条记忆"""
    try:
        db = getattr(request.state, "db", None)

        deleted = await conversation_memory_service.delete_memory(
            user_id=user_id,
            memory_id=memory_id,
            db=db,
        )

        if not deleted:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "记忆条目不存在")

        return api_success(
            data={"deleted": memory_id},
            message="记忆已删除",
        )
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error deleting memory {memory_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
