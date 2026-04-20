"""
Intent Rules CRUD — 行业术语 / 意图分类关键词管理

管理员可以通过此 API 动态添加、修改、删除意图识别关键词，
无需修改代码即可扩展 AI 的意图分类能力。
"""

import logging
import re

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intent-rules", tags=["intent-rules"])


class IntentRuleCreate(BaseModel):
    keyword: str
    complexity: str  # critical / complex / moderate
    description: str | None = None
    is_active: bool = True

    @field_validator("keyword")
    @classmethod
    def keyword_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("关键词不能为空")
        return v

    @field_validator("complexity")
    @classmethod
    def valid_complexity(cls, v: str) -> str:
        allowed = {"critical", "complex", "moderate"}
        if v not in allowed:
            raise ValueError(f"complexity 必须是 {allowed} 之一")
        return v


class IntentRuleUpdate(BaseModel):
    keyword: str | None = None
    complexity: str | None = None
    description: str | None = None
    is_active: bool | None = None

    @field_validator("complexity")
    @classmethod
    def valid_complexity(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"critical", "complex", "moderate"}
        if v not in allowed:
            raise ValueError(f"complexity 必须是 {allowed} 之一")
        return v


class RegexValidateRequest(BaseModel):
    pattern: str


@router.get("")
async def list_intent_rules(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取所有意图规则"""
    try:
        from app.core.database import supabase

        db = getattr(request.state, "db", None) or supabase
        result = (
            await db.table("intent_rules")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return api_success(data=result.data or [], message="意图规则列表")
    except Exception as e:
        logger.error(f"List intent rules error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("")
async def create_intent_rule(
    body: IntentRuleCreate,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建意图规则"""
    try:
        from app.core.database import supabase

        db = getattr(request.state, "db", None) or supabase

        # 检查是否重复
        existing = (
            await db.table("intent_rules")
            .select("id")
            .eq("keyword", body.keyword)
            .maybe_single()
            .execute()
        )
        if existing.data:
            return api_error(ErrorCode.RESOURCE_CONFLICT, f"关键词「{body.keyword}」已存在")

        result = (
            await db.table("intent_rules")
            .insert(
                {
                    "keyword": body.keyword,
                    "complexity": body.complexity,
                    "description": body.description,
                    "is_active": body.is_active,
                }
            )
            .execute()
        )

        # 热重载规则
        await _trigger_reload()

        return api_success(data=result.data[0] if result.data else None, message="规则创建成功")
    except Exception as e:
        logger.error(f"Create intent rule error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/{rule_id}")
async def update_intent_rule(
    rule_id: str,
    body: IntentRuleUpdate,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新意图规则"""
    try:
        from app.core.database import supabase

        db = getattr(request.state, "db", None) or supabase

        update_data = {k: v for k, v in body.model_dump().items() if v is not None}
        if not update_data:
            return api_error(ErrorCode.VALIDATION_ERROR, "没有需要更新的字段")

        result = (
            await db.table("intent_rules")
            .update(update_data)
            .eq("id", rule_id)
            .execute()
        )

        if not result.data:
            return api_error(ErrorCode.NOT_FOUND, "规则不存在")

        await _trigger_reload()
        return api_success(data=result.data[0], message="规则更新成功")
    except Exception as e:
        logger.error(f"Update intent rule error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/{rule_id}")
async def delete_intent_rule(
    rule_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """删除意图规则"""
    try:
        from app.core.database import supabase

        db = getattr(request.state, "db", None) or supabase

        result = (
            await db.table("intent_rules")
            .delete()
            .eq("id", rule_id)
            .execute()
        )

        await _trigger_reload()
        return api_success(data=None, message="规则已删除")
    except Exception as e:
        logger.error(f"Delete intent rule error: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/validate-regex")
async def validate_regex(
    body: RegexValidateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """验证正则表达式是否合法"""
    try:
        re.compile(body.pattern)
        return api_success(data={"valid": True}, message="正则表达式合法")
    except re.error as e:
        return api_success(
            data={"valid": False, "error": str(e)}, message="正则表达式不合法"
        )


async def _trigger_reload():
    """触发意图规则热重载"""
    try:
        from app.agent.router import reload_db_intent_rules

        count = await reload_db_intent_rules()
        logger.info(f"[IntentRules] Reloaded, total keywords: {count}")
    except Exception as e:
        logger.warning(f"[IntentRules] Reload failed: {e}")
