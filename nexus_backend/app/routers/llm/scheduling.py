"""LLM 调度规则子路由"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

from ._shared import CreateScheduleRuleRequest, UpdateScheduleRuleRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["LLM Scheduling"])


def _get_admin_db():
    """获取 admin client (绕过 RLS, 因为 llm_schedule_rule 的 RLS 依赖 app.current_org_id)"""
    from app.core.database import supabase

    return supabase


@router.get("/schedule-rules")
async def list_schedule_rules(
    req: Request, user_id: str = Depends(get_current_user_id)
):
    """获取当前租户的模型调度规则列表"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_success(data=[])

        result = (
            await db.table("llm_schedule_rule")
            .select(
                "id,rule_name,scene_code,agent_code,"
                "primary_model_id,backup_model_id,"
                "load_balance_strategy,priority,is_active,complexity_tier"
            )
            .eq("tenant_id", str(org_id))
            .order("priority", desc=True)
            .execute()
        )
        return api_success(data=result.data or [])
    except Exception as e:
        logger.error(f"Failed to list schedule rules: {e}")
        return api_success(data=[])


@router.post("/schedule-rules")
async def create_schedule_rule(
    body: CreateScheduleRuleRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建调度规则"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_error(ErrorCode.BAD_REQUEST, "缺少组织信息")

        insert_data = body.model_dump(exclude_none=True)
        insert_data["tenant_id"] = str(org_id)

        result = (
            await db.table("llm_schedule_rule")
            .insert(insert_data)
            .execute()
        )
        return api_success(data=result.data[0] if result.data else {})
    except Exception as e:
        logger.error(f"Failed to create schedule rule: {e}")
        return api_error(ErrorCode.INTERNAL_ERROR, f"创建调度规则失败: {e}")


@router.put("/schedule-rules/{rule_id}")
async def update_schedule_rule(
    rule_id: int,
    body: UpdateScheduleRuleRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新调度规则"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_error(ErrorCode.BAD_REQUEST, "缺少组织信息")

        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            return api_error(ErrorCode.BAD_REQUEST, "没有需要更新的字段")

        update_data["update_time"] = datetime.now(timezone.utc).isoformat()

        result = (
            await db.table("llm_schedule_rule")
            .update(update_data)
            .eq("id", rule_id)
            .eq("tenant_id", str(org_id))
            .execute()
        )

        if not result.data:
            return api_error(ErrorCode.NOT_FOUND, "调度规则不存在")

        return api_success(data=result.data[0])
    except Exception as e:
        logger.error(f"Failed to update schedule rule {rule_id}: {e}")
        return api_error(ErrorCode.INTERNAL_ERROR, f"更新调度规则失败: {e}")


@router.delete("/schedule-rules/{rule_id}")
async def delete_schedule_rule(
    rule_id: int,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """删除调度规则"""
    try:
        db = _get_admin_db()
        org_id = getattr(req.state, "org_id", None)

        if not db or not org_id:
            return api_error(ErrorCode.BAD_REQUEST, "缺少组织信息")

        result = (
            await db.table("llm_schedule_rule")
            .delete()
            .eq("id", rule_id)
            .eq("tenant_id", str(org_id))
            .execute()
        )

        if not result.data:
            return api_error(ErrorCode.NOT_FOUND, "调度规则不存在")

        return api_success(data={"deleted": True})
    except Exception as e:
        logger.error(f"Failed to delete schedule rule {rule_id}: {e}")
        return api_error(ErrorCode.INTERNAL_ERROR, f"删除调度规则失败: {e}")
