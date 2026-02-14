"""
IM 平台 OAuth 回调端点

处理企微/钉钉/飞书的 OAuth SSO 登录：
1. 生成各平台的 OAuth 登录链接
2. 处理 OAuth 回调，用 code 换取用户信息
3. 查找 im_user_mappings 映射到 Nexus 用户
4. 支持通过手机号自动关联未映射的用户
"""

import logging
from fastapi import APIRouter, Request, HTTPException

from app.core.config import settings
from app.core.database import supabase
from app.core.errors import api_success, api_error, ErrorCode
from app.services.im_platform.wecom_client import WecomClient
from app.services.im_platform.dingtalk_client import DingtalkClient
from app.services.im_platform.feishu_client import FeishuClient
from app.services.im_platform.contact_sync_service import ContactSyncService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/im-auth", tags=["IM OAuth"])

# 支持的平台
SUPPORTED_PLATFORMS = ("wecom", "dingtalk", "feishu")


def _get_global_client(platform: str):
    """
    从全局 Settings 获取平台客户端（非 DB 配置场景）。
    用于无组织上下文的 OAuth 流程。
    """
    if platform == "wecom":
        if not settings.WECOM_CORP_ID or not settings.WECOM_CORP_SECRET:
            return None
        return WecomClient(
            corp_id=settings.WECOM_CORP_ID,
            corp_secret=settings.WECOM_CORP_SECRET,
            agent_id=settings.WECOM_AGENT_ID,
        )
    elif platform == "dingtalk":
        if not settings.DINGTALK_APP_KEY or not settings.DINGTALK_APP_SECRET:
            return None
        return DingtalkClient(
            app_key=settings.DINGTALK_APP_KEY,
            app_secret=settings.DINGTALK_APP_SECRET,
            agent_id=settings.DINGTALK_AGENT_ID,
        )
    elif platform == "feishu":
        if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
            return None
        return FeishuClient(
            app_id=settings.FEISHU_APP_ID,
            app_secret=settings.FEISHU_APP_SECRET,
        )
    return None


async def _get_org_client(org_id: str, platform: str, db=None):
    """
    从 DB 配置获取组织级平台客户端。
    """
    contact_sync = ContactSyncService()
    return await contact_sync._get_client(org_id, platform, db)


@router.get("/{platform}/login-url")
async def get_login_url(
    platform: str,
    request: Request,
    redirect_uri: str = "",
    state: str = "",
    org_id: str = "",
):
    """
    生成 IM 平台 OAuth 登录链接。

    Args:
        platform: 平台标识 (wecom/dingtalk/feishu)
        redirect_uri: 授权回调地址（前端提供）
        state: 防 CSRF 状态参数
        org_id: 可选组织 ID（用于从 DB 读取配置）

    Returns:
        {"login_url": "https://..."}
    """
    if platform not in SUPPORTED_PLATFORMS:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            f"Unsupported platform: {platform}. "
            f"Supported: {', '.join(SUPPORTED_PLATFORMS)}",
        )

    if not redirect_uri:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            "redirect_uri is required",
        )

    client = None
    try:
        # 优先从 DB 读取组织配置，否则使用全局配置
        db = getattr(request.state, "db", None) or supabase
        if org_id:
            client = await _get_org_client(org_id, platform, db)

        if not client:
            client = _get_global_client(platform)

        if not client:
            return api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                f"{platform} is not configured. "
                f"Please set the required credentials.",
            )

        login_url = client.get_oauth_url(
            redirect_uri=redirect_uri,
            state=state or "nexus",
        )

        return api_success(data={"login_url": login_url, "platform": platform})

    except Exception as e:
        logger.error(f"[im_oauth] Failed to generate login URL for {platform}: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
    finally:
        if client:
            await client.close()


@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str,
    state: str = "",
    org_id: str = "",
    request: Request = None,
):
    """
    OAuth 回调处理。

    流程：
    1. 用 code 换取平台用户信息
    2. 查 im_user_mappings 找到 Nexus 用户
    3. 如果未映射，尝试通过手机号自动关联
    4. 返回用户信息（前端可据此创建 session）

    Args:
        platform: 平台标识
        code: OAuth 授权码
        state: 状态参数
        org_id: 组织 ID

    Returns:
        {"user": {...}, "is_new_mapping": bool}
    """
    if platform not in SUPPORTED_PLATFORMS:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            f"Unsupported platform: {platform}",
        )

    if not code:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            "Authorization code is required",
        )

    db = getattr(request.state, "db", None) or supabase if request else supabase
    client = None

    try:
        # 获取客户端
        if org_id:
            client = await _get_org_client(org_id, platform, db)
        if not client:
            client = _get_global_client(platform)

        if not client:
            return api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                f"{platform} is not configured",
            )

        # 1. 用 code 换取用户信息
        platform_user = await client.get_user_by_auth_code(code)
        platform_user_id = platform_user.get("userid", "")

        if not platform_user_id:
            logger.warning(
                f"[im_oauth] No userid returned from {platform} OAuth"
            )
            return api_error(
                ErrorCode.AUTH_TOKEN_INVALID,
                "Could not resolve user identity from platform",
            )

        if not db:
            return api_error(
                ErrorCode.SYSTEM_INTERNAL_ERROR,
                "Database not available",
            )

        # 2. 查 im_user_mappings
        is_new_mapping = False
        mapping_result = (
            await db.table("im_user_mappings")
            .select("user_id")
            .eq("platform", platform)
            .eq("platform_user_id", platform_user_id)
            .execute()
        )

        nexus_user_id = None
        if mapping_result.data:
            nexus_user_id = mapping_result.data[0].get("user_id")
        else:
            # 3. 尝试通过手机号自动关联
            mobile = platform_user.get("mobile", "")
            if mobile:
                user_result = (
                    await db.table("users")
                    .select("id")
                    .eq("phone", mobile)
                    .limit(1)
                    .execute()
                )
                if user_result.data:
                    nexus_user_id = user_result.data[0].get("id")

                    # 自动创建映射
                    try:
                        # 确定 org_id
                        resolved_org_id = org_id
                        if not resolved_org_id:
                            org_result = (
                                await db.table("users")
                                .select("organization_id")
                                .eq("id", nexus_user_id)
                                .single()
                                .execute()
                            )
                            if org_result.data:
                                resolved_org_id = org_result.data.get(
                                    "organization_id", ""
                                )

                        if resolved_org_id:
                            await db.table("im_user_mappings").insert(
                                {
                                    "user_id": nexus_user_id,
                                    "organization_id": resolved_org_id,
                                    "platform": platform,
                                    "platform_user_id": platform_user_id,
                                    "platform_username": platform_user.get("name", ""),
                                }
                            ).execute()
                            is_new_mapping = True
                            logger.info(
                                f"[im_oauth] Auto-mapped {platform} user "
                                f"{platform_user_id} to Nexus user "
                                f"{nexus_user_id} via mobile"
                            )
                    except Exception as e:
                        logger.warning(
                            f"[im_oauth] Failed to auto-create mapping: {e}"
                        )

        if not nexus_user_id:
            return api_error(
                ErrorCode.RESOURCE_NOT_FOUND,
                f"No Nexus user mapped for {platform} user {platform_user_id}. "
                f"Please contact your administrator to set up the mapping.",
            )

        # 4. 获取 Nexus 用户信息
        user_result = (
            await db.table("users")
            .select("id, name, email, role, organization_id")
            .eq("id", nexus_user_id)
            .single()
            .execute()
        )

        user_info = user_result.data if user_result.data else {}

        return api_success(
            data={
                "user": {
                    "nexus_user_id": nexus_user_id,
                    "name": user_info.get("name", ""),
                    "email": user_info.get("email", ""),
                    "role": user_info.get("role", ""),
                    "organization_id": user_info.get("organization_id", ""),
                    "platform": platform,
                    "platform_user_id": platform_user_id,
                    "platform_username": platform_user.get("name", ""),
                },
                "is_new_mapping": is_new_mapping,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[im_oauth] OAuth callback error for {platform}: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
    finally:
        if client:
            await client.close()
