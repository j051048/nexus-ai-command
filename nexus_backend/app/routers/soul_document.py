"""Soul Document API — AI 灵魂文档管理。

仅 boss/founder 可编辑；同租户所有成员可读。
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.database import supabase
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_success
from app.services.soul_document_service import soul_document_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/soul-document", tags=["Soul Document"])


# ── 辅助: 获取当前用户的 org_id ──────────────────────────────────────────
async def _get_org_id(user_id: str) -> str:
    res = await supabase.table("users").select("organization_id").eq("id", user_id).maybe_single().execute()
    org_id = res.data.get("organization_id") if res.data else None
    if not org_id:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "未找到所属组织")
    return org_id


# ── Schema ────────────────────────────────────────────────────────────────
class SoulDocumentBody(BaseModel):
    ai_name: str = Field(default="小助手", max_length=50, description="AI 名字")
    identity: str | None = Field(default=None, max_length=500, description="身份定位")
    personality: str | None = Field(default=None, max_length=500, description="性格特征")
    values: str | None = Field(default=None, max_length=1000, description="价值观/原则")
    language_style: str | None = Field(default=None, max_length=500, description="语言风格")
    taboos: str | None = Field(default=None, max_length=1000, description="禁忌/红线")
    custom_instructions: str | None = Field(default=None, max_length=3000, description="自由指令")
    is_active: bool = Field(default=True, description="是否启用")


# ── GET: 获取灵魂文档 ─────────────────────────────────────────────────────
@router.get("")
async def get_soul_document(user_id: str = Depends(get_current_user_id)):
    """获取当前租户的灵魂文档（任意已登录用户可读）。"""
    org_id = await _get_org_id(user_id)
    doc = await soul_document_service.get_raw(org_id)
    return api_success(data=doc)


# ── PUT: 创建或更新灵魂文档 ───────────────────────────────────────────────
@router.put("")
async def upsert_soul_document(
    body: SoulDocumentBody,
    user_id: str = Depends(require_role(["boss", "founder"])),
):
    """创建或更新灵魂文档（仅 boss/founder）。"""
    org_id = await _get_org_id(user_id)
    result = await soul_document_service.upsert(org_id, user_id, body.model_dump())
    return api_success(data=result, message="灵魂文档已保存")


# ── GET /preview: 预览编译后的提示词 ──────────────────────────────────────
@router.get("/preview")
async def preview_soul_document(
    user_id: str = Depends(require_role(["boss", "founder"])),
):
    """预览灵魂文档编译后的提示词片段。"""
    org_id = await _get_org_id(user_id)
    doc = await soul_document_service.get_raw(org_id)
    if not doc:
        return api_success(data={"compiled": None}, message="尚未配置灵魂文档")

    compiled = soul_document_service.compile_soul_prompt(doc)
    return api_success(data={"compiled": compiled})
