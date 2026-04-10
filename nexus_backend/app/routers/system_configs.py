"""系统配置管理 API 路由"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.system_config_service import system_config_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/system-configs", tags=["System Configs"])


class ConfigUpsertRequest(BaseModel):
    config_type: str
    config_key: str
    config_value: dict
    sort_order: int = 0


@router.get("")
async def list_configs(
    req: Request,
    config_type: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """查询配置列表"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        configs = await system_config_service.list_configs(
            org_id=org_id,
            config_type=config_type,
            db=db,
        )
        return api_success(data={"configs": configs})
    except Exception as e:
        logger.error(f"Failed to list configs: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "系统配置操作失败")


@router.put("")
async def upsert_config(
    body: ConfigUpsertRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建或更新配置"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        result = await system_config_service.upsert_config(
            org_id=org_id,
            config_type=body.config_type,
            config_key=body.config_key,
            config_value=body.config_value,
            sort_order=body.sort_order,
            db=db,
        )
        return api_success(data={"config": result})
    except Exception as e:
        logger.error(f"Failed to upsert config: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "系统配置操作失败")


@router.delete("")
async def delete_config(
    req: Request,
    config_type: str = None,
    config_key: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """删除配置（软删除）"""
    if not config_type or not config_key:
        raise api_error(
            ErrorCode.VALIDATION_MISSING_FIELD, "config_type 和 config_key 不能为空"
        )
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        result = await system_config_service.delete_config(
            org_id=org_id,
            config_type=config_type,
            config_key=config_key,
            db=db,
        )
        return api_success(data={"deleted": result})
    except Exception as e:
        logger.error(f"Failed to delete config: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "系统配置操作失败")


@router.post("/init-defaults")
async def init_defaults(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """初始化租户默认配置"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        db = getattr(req.state, "db", None)
        await system_config_service.init_default_configs(org_id=org_id, db=db)
        return api_success(data={"message": "默认配置已初始化"})
    except Exception as e:
        logger.error(f"Failed to init defaults: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "系统配置操作失败")
