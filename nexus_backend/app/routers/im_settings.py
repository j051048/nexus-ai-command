"""
IM 平台管理设置 API

提供 IM 平台配置的 CRUD 和操作端点：
- 获取组织的 IM 配置列表
- 创建/更新 IM 配置
- 删除 IM 配置
- 测试 IM 连接
- 手动触发通讯录同步
- 手动触发考勤同步
"""

import logging
from fastapi import APIRouter, Request, Depends

from app.core.auth import get_current_user_id
from app.core.database import supabase
from app.core.errors import api_success, api_error, ErrorCode
from app.services.im_platform.contact_sync_service import (
    ContactSyncService,
    contact_sync_service,
)
from app.services.im_platform.attendance_sync_service import (
    attendance_sync_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/im-settings", tags=["IM Settings"])

SUPPORTED_PLATFORMS = ("wecom", "dingtalk", "feishu")


@router.get("")
async def get_im_configs(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    获取当前组织的 IM 平台配置列表。

    Returns:
        配置列表（敏感字段脱敏）
    """
    db = getattr(request.state, "db", None) or supabase
    org_id = getattr(request.state, "org_id", None)

    if not db:
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Database not available")

    try:
        query = db.table("im_platform_config").select(
            "id, organization_id, platform, is_active, created_at, updated_at"
        )
        if org_id:
            query = query.eq("organization_id", org_id)

        result = await query.execute()
        configs = result.data or []

        return api_success(data={"configs": configs})

    except Exception as e:
        logger.error(f"[im_settings] Failed to get configs: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("")
async def upsert_im_config(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    创建或更新 IM 平台配置。

    Request Body:
    {
        "platform": "wecom",
        "config": {
            "corp_id": "xxx",
            "corp_secret": "xxx",
            "agent_id": "xxx"
        },
        "is_active": true
    }
    """
    db = getattr(request.state, "db", None) or supabase
    org_id = getattr(request.state, "org_id", None)

    if not db:
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Database not available")

    try:
        body = await request.json()
        platform = body.get("platform", "")
        config = body.get("config", {})
        is_active = body.get("is_active", True)

        if platform not in SUPPORTED_PLATFORMS:
            return api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                f"Unsupported platform: {platform}. "
                f"Supported: {', '.join(SUPPORTED_PLATFORMS)}",
            )

        if not config:
            return api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                "config is required",
            )

        # 验证必需的配置字段
        required_fields = _get_required_fields(platform)
        missing = [f for f in required_fields if not config.get(f)]
        if missing:
            return api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                f"Missing required config fields: {', '.join(missing)}",
            )

        if not org_id:
            return api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                "Organization context required",
            )

        # Upsert
        data = {
            "organization_id": org_id,
            "platform": platform,
            "config": config,
            "is_active": is_active,
        }

        result = await db.table("im_platform_config").upsert(
            data,
            on_conflict="organization_id,platform",
        ).execute()

        logger.info(
            f"[im_settings] Config upserted for org={org_id}, "
            f"platform={platform}"
        )

        return api_success(
            data={
                "message": f"{platform} configuration saved",
                "platform": platform,
                "is_active": is_active,
            }
        )

    except Exception as e:
        logger.error(f"[im_settings] Failed to upsert config: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/{platform}")
async def delete_im_config(
    platform: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    删除指定平台的 IM 配置。

    Args:
        platform: 平台标识
    """
    db = getattr(request.state, "db", None) or supabase
    org_id = getattr(request.state, "org_id", None)

    if not db:
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Database not available")

    if platform not in SUPPORTED_PLATFORMS:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            f"Unsupported platform: {platform}",
        )

    try:
        await (
            db.table("im_platform_config")
            .delete()
            .eq("organization_id", org_id)
            .eq("platform", platform)
            .execute()
        )

        logger.info(
            f"[im_settings] Config deleted for org={org_id}, "
            f"platform={platform}"
        )

        return api_success(
            data={"message": f"{platform} configuration deleted"}
        )

    except Exception as e:
        logger.error(f"[im_settings] Failed to delete config: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/{platform}/test")
async def test_im_connection(
    platform: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    测试 IM 平台连接（验证 token 能否正常获取）。

    Args:
        platform: 平台标识
    """
    db = getattr(request.state, "db", None) or supabase
    org_id = getattr(request.state, "org_id", None)

    if platform not in SUPPORTED_PLATFORMS:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            f"Unsupported platform: {platform}",
        )

    client = None
    try:
        sync_service = ContactSyncService()
        client = await sync_service._get_client(org_id, platform, db)

        if not client:
            return api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                f"No active {platform} configuration found for this organization",
            )

        # 尝试获取 token 以验证连接
        token = await client.get_access_token()

        # 尝试获取部门列表（轻量验证 API 权限）
        departments = await client.get_departments()

        return api_success(
            data={
                "status": "connected",
                "platform": platform,
                "token_obtained": bool(token),
                "departments_found": len(departments),
                "message": f"Successfully connected to {platform}",
            }
        )

    except Exception as e:
        logger.error(
            f"[im_settings] Connection test failed for {platform}: {e}"
        )
        return api_success(
            data={
                "status": "failed",
                "platform": platform,
                "error": str(e)[:200],
                "message": f"Failed to connect to {platform}",
            }
        )
    finally:
        if client:
            await client.close()


@router.post("/{platform}/sync-contacts")
async def trigger_contact_sync(
    platform: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    手动触发通讯录同步。

    Args:
        platform: 平台标识
    """
    org_id = getattr(request.state, "org_id", None)
    db = getattr(request.state, "db", None) or supabase

    if platform not in SUPPORTED_PLATFORMS:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            f"Unsupported platform: {platform}",
        )

    if not org_id:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            "Organization context required",
        )

    try:
        stats = await contact_sync_service.sync_contacts(
            org_id=org_id,
            platform=platform,
            db=db,
        )

        return api_success(data={"sync_result": stats})

    except Exception as e:
        logger.error(f"[im_settings] Contact sync failed: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/{platform}/sync-attendance")
async def trigger_attendance_sync(
    platform: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    手动触发考勤同步。

    Query Params:
        date: 可选，同步日期 YYYY-MM-DD（默认今天）

    Args:
        platform: 平台标识
    """
    org_id = getattr(request.state, "org_id", None)
    db = getattr(request.state, "db", None) or supabase
    sync_date = request.query_params.get("date", None)

    if platform not in SUPPORTED_PLATFORMS:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            f"Unsupported platform: {platform}",
        )

    if not org_id:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            "Organization context required",
        )

    try:
        stats = await attendance_sync_service.sync_attendance(
            org_id=org_id,
            platform=platform,
            sync_date=sync_date,
            db=db,
        )

        return api_success(data={"sync_result": stats})

    except Exception as e:
        logger.error(f"[im_settings] Attendance sync failed: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


def _get_required_fields(platform: str) -> list:
    """获取平台必需的配置字段列表"""
    if platform == "wecom":
        return ["corp_id", "corp_secret"]
    elif platform == "dingtalk":
        return ["app_key", "app_secret"]
    elif platform == "feishu":
        return ["app_id", "app_secret"]
    return []
