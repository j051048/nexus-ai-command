"""
Item 13: AI Conversation Memory API

Endpoints for managing user long-term AI conversation memories
and organization behavior policies.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.conversation_memory_service import conversation_memory_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memories", tags=["Conversation Memories"])

MemoryState = Literal[
    "proposed",
    "confirmed",
    "active",
    "pending_review",
    "expired",
    "rejected",
    "archived",
]
MemoryVisibility = Literal["private", "team", "organization"]


class MemoryCreateBody(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=8000)
    category: str = Field(default="explicit_memory", max_length=80)
    importance: float = Field(default=0.7, ge=0, le=1)
    visibility: MemoryVisibility = "private"
    confidence: float = Field(default=1.0, ge=0, le=1)
    expires_at: str | None = None
    evidence_ref: str | None = Field(default=None, max_length=1000)
    metadata: dict = Field(default_factory=dict)


class MemoryUpdateBody(BaseModel):
    value: str | None = Field(default=None, min_length=1, max_length=8000)
    visibility: MemoryVisibility | None = None
    lifecycle_state: MemoryState | None = None
    expires_at: str | None = None


@router.get("")
async def get_memories(
    request: Request,
    category: str | None = None,
    state: str | None = None,
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
):
    """获取当前用户的记忆列表"""
    try:
        db = getattr(request.state, "db", None)

        allowed_states = [
            "proposed",
            "confirmed",
            "active",
            "pending_review",
            "expired",
            "rejected",
            "archived",
        ]
        lifecycle_states = (
            allowed_states if state == "all" else ([state] if state else None)
        )
        if lifecycle_states and any(
            item not in allowed_states for item in lifecycle_states
        ):
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无效的记忆状态")

        memories = await conversation_memory_service.get_memories(
            user_id=user_id,
            category=category,
            limit=min(limit, 100),
            db=db,
            lifecycle_states=lifecycle_states,
        )

        return api_success(data=memories, message="记忆列表获取成功")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting memories: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆操作失败")


@router.post("")
async def create_memory(
    request: Request,
    body: MemoryCreateBody,
    user_id: str = Depends(get_current_user_id),
):
    """Create an explicit, user-confirmed memory."""
    try:
        org_id = getattr(request.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "缺少组织上下文")
        saved = await conversation_memory_service.save_memory(
            user_id=user_id,
            key=body.key,
            value=body.value,
            category=body.category,
            metadata=body.metadata,
            importance=body.importance,
            org_id=org_id,
            db=getattr(request.state, "db", None),
            confidence=body.confidence,
            visibility=body.visibility,
            expires_at=body.expires_at,
            evidence_ref=body.evidence_ref,
            source="user_explicit",
            extraction_method="user_explicit",
        )
        return api_success(data=saved, message="记忆已保存")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error("Error creating memory: %s", e)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆保存失败")


@router.patch("/{memory_id}")
async def update_memory(
    request: Request,
    memory_id: str,
    body: MemoryUpdateBody,
    user_id: str = Depends(get_current_user_id),
):
    """Edit, confirm, reject, archive or restore an owned memory."""
    try:
        updated = await conversation_memory_service.update_memory(
            user_id=user_id,
            memory_id=memory_id,
            value=body.value,
            visibility=body.visibility,
            lifecycle_state=body.lifecycle_state,
            expires_at=body.expires_at,
            db=getattr(request.state, "db", None),
        )
        if not updated:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "记忆不存在")
        return api_success(data=updated, message="记忆已更新")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error("Error updating memory %s: %s", memory_id, e)
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆更新失败")


@router.get("/{memory_id}/audit")
async def get_memory_audit(
    request: Request,
    memory_id: str,
    user_id: str = Depends(get_current_user_id),
):
    from app.services.conversation_memory.audit import get_memory_audit_trail

    rows = await get_memory_audit_trail(
        memory_id=memory_id,
        user_id=user_id,
        db=getattr(request.state, "db", None),
    )
    return api_success(data=rows)


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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆操作失败")


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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆操作失败")


# ─── Organization Behavior Policies ──────────────────────────


class PolicyItem(BaseModel):
    key: str
    value: str


class PolicyBatchBody(BaseModel):
    policies: list[PolicyItem]


async def _get_org_id_and_role(
    request: Request, user_id: str
) -> tuple[str | None, str | None]:
    """Extract org_id and user role from request state."""
    org_id = getattr(request.state, "org_id", None)
    role = getattr(request.state, "role", None)

    # Fallback: query role from DB if middleware didn't set it
    if not role:
        from app.core.database import supabase

        if supabase:
            res = (
                await supabase.table("users")
                .select("role")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆操作失败")


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
            raise api_error(
                ErrorCode.AUTH_PERMISSION_DENIED, "未关联组织，无法设置行为准则"
            )

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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆操作失败")


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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆操作失败")


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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆操作失败")


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
            raise api_error(
                ErrorCode.AUTH_PERMISSION_DENIED, "未关联组织，无法设置业务规则"
            )

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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆操作失败")


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
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "记忆操作失败")


# ─── Entity Profile (Mem0+ simplified) ────────────────────────


@router.get("/entity-profile")
async def get_entity_profile(
    request: Request,
    entity: str,
    limit: int = 30,
    user_id: str = Depends(get_current_user_id),
):
    """获取实体画像 — 聚合 knowledge_graph_triples 中该实体的所有关系。

    返回以该实体为 source 或 destination 的三元组列表，
    帮助用户了解 AI 对某人/公司/概念的已知信息。
    """
    try:
        org_id = getattr(request.state, "org_id", None)
        if not org_id:
            return api_success(
                data={"entity": entity, "triples": []}, message="未关联组织"
            )

        from app.core.database import supabase as db

        entity_clean = entity.strip()[:200]
        safe_limit = min(max(limit, 1), 100)

        # Query triples where entity appears as source OR destination
        as_source = (
            await db.table("knowledge_graph_triples")
            .select(
                "id, source_entity, source_type, relationship, destination_entity, destination_type, strength, occurrences, updated_at"
            )
            .eq("organization_id", org_id)
            .ilike("source_entity", entity_clean)
            .order("strength", desc=True)
            .limit(safe_limit)
            .execute()
        )
        as_dest = (
            await db.table("knowledge_graph_triples")
            .select(
                "id, source_entity, source_type, relationship, destination_entity, destination_type, strength, occurrences, updated_at"
            )
            .eq("organization_id", org_id)
            .ilike("destination_entity", entity_clean)
            .order("strength", desc=True)
            .limit(safe_limit)
            .execute()
        )

        triples = (as_source.data or []) + (as_dest.data or [])
        # Dedupe by id
        seen = set()
        unique = []
        for t in triples:
            if t["id"] not in seen:
                seen.add(t["id"])
                unique.append(t)

        # Also fetch aliases from entity_aliases
        aliases = []
        try:
            alias_resp = (
                await db.table("entity_aliases")
                .select("alias, canonical_name")
                .eq("organization_id", org_id)
                .or_(f"alias.ilike.{entity_clean},canonical_name.ilike.{entity_clean}")
                .limit(20)
                .execute()
            )
            aliases = alias_resp.data or []
        except Exception:
            pass  # entity_aliases table may not exist

        return api_success(
            data={
                "entity": entity_clean,
                "triple_count": len(unique),
                "triples": unique[:safe_limit],
                "aliases": aliases,
            },
            message=f"实体画像: {entity_clean}",
        )
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting entity profile for '{entity}': {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "实体画像查询失败")
