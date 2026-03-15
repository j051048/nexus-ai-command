"""Quota management endpoints."""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success

from ._shared import (
    CreateQuotaConfigRequest,
    UpdateQuotaConfigRequest,
    _get_admin_client,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/quota-configs")
async def list_quota_configs(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取配额配置列表"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = _get_admin_client()

        res = (
            await client.table("llm_quota_config")
            .select("*")
            .eq("tenant_id", org_id)
            .order("create_time", desc=True)
            .execute()
        )
        return api_success(data={"configs": res.data or []})
    except Exception as e:
        logger.error(f"List quota configs error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/quota-configs")
async def create_quota_config(
    body: CreateQuotaConfigRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建配额配置"""
    try:
        org_id = getattr(req.state, "org_id", None) or "default"
        client = _get_admin_client()

        record = {
            "tenant_id": org_id,
            "quota_type": body.quota_type,
            "target_id": body.target_id,
            "daily_token_limit": body.daily_token_limit,
            "daily_request_limit": body.daily_request_limit,
            "daily_cost_limit": body.daily_cost_limit,
            "monthly_token_limit": body.monthly_token_limit,
            "monthly_cost_limit": body.monthly_cost_limit,
        }

        res = await client.table("llm_quota_config").insert(record).execute()
        config = res.data[0] if res.data else record
        return api_success(data={"config": config}, message="配额配置创建成功")
    except Exception as e:
        err_code = getattr(e, "code", "")
        if str(err_code) == "23505":
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "该配额配置已存在，请勿重复添加")
        logger.error(f"Create quota config error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/quota-configs/{config_id}")
async def update_quota_config(
    config_id: str,
    body: UpdateQuotaConfigRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新配额配置"""
    try:
        client = _get_admin_client()

        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无更新内容")

        res = await client.table("llm_quota_config").update(update_data).eq("id", config_id).execute()
        if not res.data:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "配额配置不存在")

        return api_success(data={"config": res.data[0]}, message="配额配置已更新")
    except Exception as e:
        logger.error(f"Update quota config error: id={config_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
