"""
API Key 管理路由

提供 API Key 的创建、列表、撤销和使用统计端点。
"""

import logging
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Request, Depends, Query

from app.core.auth import get_current_user_id
from app.core.dependencies import require_role
from app.core.errors import api_success, api_error, ErrorCode
from app.services.api_key_service import api_key_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/api-keys", tags=["API Keys"])

# API Key 管理需要管理员权限
require_key_admin = require_role(["admin", "founder", "boss"])


# ============== Request Models ==============


class CreateKeyRequest(BaseModel):
    name: str
    scopes: List[str] = ["read"]
    expires_days: int = 365


# ============== Endpoints ==============


@router.post("")
async def create_api_key(
    request: Request,
    body: CreateKeyRequest,
    user_id: str = Depends(require_key_admin),
):
    """创建 API Key（返回完整 key 仅此一次）"""
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        result = await api_key_service.create_api_key(
            org_id=org_id,
            name=body.name,
            scopes=body.scopes,
            expires_days=body.expires_days,
            created_by=user_id,
            db=client,
        )
        return api_success(data=result, message="API Key 创建成功")
    except Exception as e:
        logger.error(f"创建 API Key 失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("")
async def list_api_keys(
    request: Request,
    user_id: str = Depends(require_key_admin),
):
    """列出组织的 API Keys"""
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        keys = await api_key_service.list_api_keys(org_id=org_id, db=client)
        return api_success(data=keys)
    except Exception as e:
        logger.error(f"列出 API Keys 失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    request: Request,
    user_id: str = Depends(require_key_admin),
):
    """撤销 API Key"""
    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        success = await api_key_service.revoke_api_key(key_id=key_id, db=client)
        if success:
            return api_success(data={"key_id": key_id}, message="API Key 已撤销")
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "API Key 不存在")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"撤销 API Key 失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/{key_id}/usage")
async def get_api_key_usage(
    key_id: str,
    request: Request,
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    user_id: str = Depends(require_key_admin),
):
    """获取 API Key 使用统计"""
    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    date_range = None
    if date_from or date_to:
        date_range = {}
        if date_from:
            date_range["from"] = date_from
        if date_to:
            date_range["to"] = date_to

    try:
        usage = await api_key_service.get_api_usage(
            key_id=key_id, date_range=date_range, db=client
        )
        if usage.get("error"):
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, usage["error"])
        return api_success(data=usage)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"获取 API 使用统计失败: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
