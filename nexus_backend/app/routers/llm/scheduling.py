"""LLM 调度规则子路由"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import api_success

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
                "load_balance_strategy,priority,is_active"
            )
            .eq("tenant_id", str(org_id))
            .eq("is_active", True)
            .order("priority", desc=True)
            .execute()
        )
        return api_success(data=result.data or [])
    except Exception as e:
        logger.error(f"Failed to list schedule rules: {e}")
        return api_success(data=[])
