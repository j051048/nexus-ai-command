"""用户快捷指令 CRUD API"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success

router = APIRouter(prefix="/api/ai/saved-prompts", tags=["Saved Prompts"])


class SavedPromptCreate(BaseModel):
    title: str = Field(..., max_length=100)
    prompt: str = Field(..., max_length=2000)
    icon: str = Field(default="zap", max_length=30)
    sort_order: int = Field(default=0)


@router.get("")
async def list_saved_prompts(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """列出当前用户的所有快捷指令"""
    client = get_request_db(req)
    result = (
        await client.table("user_saved_prompts")
        .select("*")
        .eq("user_id", user_id)
        .order("sort_order")
        .order("created_at", desc=True)
        .execute()
    )
    return api_success(data=result.data or [])


@router.post("")
async def create_saved_prompt(
    body: SavedPromptCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建快捷指令"""
    client = get_request_db(req)
    result = (
        await client.table("user_saved_prompts")
        .insert(
            {
                "user_id": user_id,
                "title": body.title,
                "prompt": body.prompt,
                "icon": body.icon,
                "sort_order": body.sort_order,
            }
        )
        .execute()
    )
    return api_success(
        data=result.data[0] if result.data else None, message="快捷指令已保存"
    )


@router.delete("/{prompt_id}")
async def delete_saved_prompt(
    prompt_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """删除快捷指令（校验归属）"""
    client = get_request_db(req)
    # Verify ownership
    existing = (
        await client.table("user_saved_prompts")
        .select("id")
        .eq("id", prompt_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    if not existing.data:
        raise api_error(ErrorCode.NOT_FOUND, "快捷指令不存在或无权限")

    await client.table("user_saved_prompts").delete().eq("id", prompt_id).execute()
    return api_success(data={"id": prompt_id}, message="快捷指令已删除")
