"""Schedule rule CRUD and adapter listing endpoints."""

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_list, api_success

from ._shared import (
    CreateScheduleRuleRequest,
    UpdateScheduleRuleRequest,
    _get_admin_client,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Adapter management endpoints
# ---------------------------------------------------------------------------


@router.get("/adapters")
async def list_adapters(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取可用适配器列表"""
    try:
        client = _get_admin_client()

        res = await client.table("llm_adapter").select("*").order("adapter_code").execute()
        return api_success(data={"adapters": res.data or []})
    except Exception as e:
        logger.error(f"List adapters error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM调度操作失败")


# ---------------------------------------------------------------------------
# Schedule rule management endpoints
# ---------------------------------------------------------------------------


@router.post("/schedule-rules")
async def create_schedule_rule(
    body: CreateScheduleRuleRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建调度规则"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        client = _get_admin_client()

        record = {
            "tenant_id": org_id,
            "rule_name": body.rule_name,
            "scene_code": body.scene_code,
            "agent_code": body.agent_code,
            "primary_model_id": body.primary_model_id,
            "backup_model_id": body.backup_model_id,
            "load_balance_strategy": body.load_balance_strategy,
            "priority": body.priority,
            "complexity_tier": body.complexity_tier,
        }

        res = await client.table("llm_schedule_rule").insert(record).execute()
        rule = res.data[0] if res.data else record
        return api_success(data={"rule": rule}, message="调度规则创建成功")
    except Exception as e:
        err_code = getattr(e, "code", "")
        if str(err_code) == "23505":
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "该调度规则已存在，请勿重复添加")
        logger.error(f"Create schedule rule error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM调度操作失败")


@router.get("/schedule-rules")
async def list_schedule_rules(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取调度规则列表"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        client = _get_admin_client()

        # Count
        count_res = (
            await client.table("llm_schedule_rule").select("id", count="exact").eq("tenant_id", org_id).execute()
        )
        total = count_res.count if count_res.count is not None else len(count_res.data or [])

        # Data
        offset = (page - 1) * page_size
        res = (
            await client.table("llm_schedule_rule")
            .select("*")
            .eq("tenant_id", org_id)
            .order("priority", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )

        return api_list(items=res.data or [], total=total, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"List schedule rules error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM调度操作失败")


@router.put("/schedule-rules/{rule_id}")
async def update_schedule_rule(
    rule_id: str,
    body: UpdateScheduleRuleRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新调度规则"""
    try:
        client = _get_admin_client()

        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无更新内容")

        res = await client.table("llm_schedule_rule").update(update_data).eq("id", rule_id).execute()
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "调度规则不存在")

        return api_success(data={"rule": res.data[0]}, message="调度规则已更新")
    except Exception as e:
        logger.error(f"Update schedule rule error: id={rule_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM调度操作失败")


@router.delete("/schedule-rules/{rule_id}")
async def delete_schedule_rule(
    rule_id: str,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """删除调度规则"""
    try:
        client = _get_admin_client()

        res = await client.table("llm_schedule_rule").delete().eq("id", rule_id).execute()
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "调度规则不存在")

        return api_success(data={"deleted": True}, message="调度规则已删除")
    except Exception as e:
        logger.error(f"Delete schedule rule error: id={rule_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "LLM调度操作失败")
