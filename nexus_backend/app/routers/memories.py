"""
Item 13: AI Conversation Memory API

Endpoints for managing user long-term AI conversation memories
and organization behavior policies.
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.conversation_memory_service import conversation_memory_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memories", tags=["Conversation Memories"])


@router.get("")
async def get_memories(
    request: Request,
    category: str | None = None,
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
    category: str | None = None,
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


# ─── Organization Behavior Policies ──────────────────────────


class PolicyItem(BaseModel):
    key: str
    value: str


class PolicyBatchBody(BaseModel):
    policies: list[PolicyItem]


async def _get_org_id_and_role(request: Request, user_id: str) -> tuple[str | None, str | None]:
    """Extract org_id and user role from request state."""
    org_id = getattr(request.state, "org_id", None)
    role = getattr(request.state, "role", None)

    # Fallback: query role from DB if middleware didn't set it
    if not role:
        from app.core.database import supabase

        if supabase:
            res = await supabase.table("users").select("role").eq("id", user_id).maybe_single().execute()
            role = res.data.get("role") if res and res.data else None

    return org_id, role


def _require_admin(role: str | None):
    """Only boss/founder/super_admin can manage org policies."""
    if role not in ("boss", "founder", "super_admin"):
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "仅管理员可管理组织行为准则")


@router.get("/org-policies")
async def get_org_policies(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取组织行为准则列表"""
    try:
        org_id, _role = await _get_org_id_and_role(request, user_id)
        if not org_id:
            return api_success(data=[], message="未关联组织")

        db = getattr(request.state, "db", None)
        policies = await conversation_memory_service.get_org_memories(
            org_id=org_id,
            category="policy",
            limit=50,
            db=db,
        )
        return api_success(data=policies, message="组织行为准则获取成功")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting org policies: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/org-policies")
async def save_org_policies(
    request: Request,
    body: PolicyBatchBody,
    user_id: str = Depends(get_current_user_id),
):
    """批量保存组织行为准则（仅管理员）"""
    try:
        org_id, role = await _get_org_id_and_role(request, user_id)
        _require_admin(role)

        if not org_id:
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "未关联组织，无法设置行为准则")

        db = getattr(request.state, "db", None)
        saved = []
        for item in body.policies:
            if not item.key.strip() or not item.value.strip():
                continue
            result = await conversation_memory_service.save_org_memory(
                org_id=org_id,
                category="policy",
                key=item.key.strip(),
                value=item.value.strip(),
                user_id=user_id,
                metadata={"source": "admin_manual"},
                db=db,
            )
            if result:
                saved.append(result)

        return api_success(
            data={"saved_count": len(saved)},
            message=f"已保存 {len(saved)} 条行为准则",
        )
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error saving org policies: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/org-policies/{memory_id}")
async def delete_org_policy(
    request: Request,
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """删除单条组织行为准则（仅管理员）"""
    try:
        org_id, role = await _get_org_id_and_role(request, user_id)
        _require_admin(role)

        if not org_id:
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "未关联组织")

        db = getattr(request.state, "db", None)
        deleted = await conversation_memory_service.delete_org_memory(
            org_id=org_id,
            memory_id=memory_id,
            db=db,
        )

        if not deleted:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "准则条目不存在")

        return api_success(data={"deleted": memory_id}, message="准则已删除")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error deleting org policy {memory_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


# ─── Business Rules (Agent auto-injection) ──────────────────────────


@router.get("/business-rules")
async def get_business_rules(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取组织业务规则列表（Agent 执行时自动注入）"""
    try:
        org_id, _role = await _get_org_id_and_role(request, user_id)
        if not org_id:
            return api_success(data=[], message="未关联组织")

        db = getattr(request.state, "db", None)
        rules = await conversation_memory_service.get_org_memories(
            org_id=org_id,
            category="business_rule",
            limit=50,
            db=db,
        )
        return api_success(data=rules, message="业务规则获取成功")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting business rules: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/business-rules")
async def save_business_rules(
    request: Request,
    body: PolicyBatchBody,
    user_id: str = Depends(get_current_user_id),
):
    """批量保存业务规则（仅管理员）"""
    try:
        org_id, role = await _get_org_id_and_role(request, user_id)
        _require_admin(role)

        if not org_id:
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "未关联组织，无法设置业务规则")

        db = getattr(request.state, "db", None)
        saved = []
        for item in body.policies:
            if not item.key.strip() or not item.value.strip():
                continue
            result = await conversation_memory_service.save_org_memory(
                org_id=org_id,
                category="business_rule",
                key=item.key.strip(),
                value=item.value.strip(),
                user_id=user_id,
                metadata={"source": "admin_manual"},
                db=db,
            )
            if result:
                saved.append(result)

        return api_success(
            data={"saved_count": len(saved)},
            message=f"已保存 {len(saved)} 条业务规则",
        )
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error saving business rules: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/business-rules/{memory_id}")
async def delete_business_rule(
    request: Request,
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """删除单条业务规则（仅管理员）"""
    try:
        org_id, role = await _get_org_id_and_role(request, user_id)
        _require_admin(role)

        if not org_id:
            raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "未关联组织")

        db = getattr(request.state, "db", None)
        deleted = await conversation_memory_service.delete_org_memory(
            org_id=org_id,
            memory_id=memory_id,
            db=db,
        )

        if not deleted:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "业务规则不存在")

        return api_success(data={"deleted": memory_id}, message="业务规则已删除")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error deleting business rule {memory_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
