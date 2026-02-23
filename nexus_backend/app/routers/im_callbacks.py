"""
IM 平台卡片回调处理

处理用户在 IM 内点击互动卡片按钮（如审批的"批准/拒绝"）的回调请求。

流程：
1. 验证回调来源签名（平台级安全）
2. 解析 approval_id 和用户决定
3. 调用审批链服务推进审批
4. 返回确认响应
"""

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.core.config import settings
from app.core.database import supabase
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/im-callback", tags=["IM Callbacks"])

SUPPORTED_PLATFORMS = ("wecom", "dingtalk", "feishu")


def _verify_wecom_signature(request_body: bytes, signature: str) -> bool:
    """
    验证企微回调签名。

    企微回调验证需要 Token 和 EncodingAESKey，
    此处简化处理，生产环境应使用完整的企微加解密库。
    """
    # TODO: 实现完整的企微回调签名验证
    # 生产环境需要配置回调 Token 和 EncodingAESKey
    logger.debug("[im_callback] Wecom signature verification (simplified)")
    return True


def _verify_dingtalk_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """
    验证钉钉回调签名。

    钉钉回调签名规则:
    sign = HMAC-SHA256(timestamp + "\n" + secret, secret)
    """
    secret = settings.DINGTALK_SECRET
    if not secret:
        logger.warning("[im_callback] DINGTALK_SECRET not configured, skipping verification")
        return True

    try:
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return hmac_code == signature
    except Exception as e:
        logger.error(f"[im_callback] Dingtalk signature verification failed: {e}")
        return False


def _verify_feishu_signature(request_body: bytes, timestamp: str, nonce: str, signature: str) -> bool:
    """
    验证飞书回调签名。

    飞书签名规则:
    sign = SHA256(timestamp + nonce + encrypt_key + body)
    """
    # TODO: 使用飞书 Encrypt Key 进行完整验证
    logger.debug("[im_callback] Feishu signature verification (simplified)")
    return True


async def _parse_callback_data(platform: str, request: Request) -> dict[str, Any]:
    """
    解析不同平台的回调数据格式，提取审批 ID 和用户决定。

    Returns:
        {
            "approval_id": "xxx",
            "action": "approve" | "reject",
            "user_id": "platform_user_id",
            "response_code": "xxx"  # 仅企微
        }
    """
    body = await request.json()

    if platform == "wecom":
        # 企微模板卡片回调
        event = body.get("event", {})
        event_key = event.get("EventKey", "")
        # EventKey 格式: "approve_{approval_id}" 或 "reject_{approval_id}"
        parts = event_key.split("_", 1)
        action = parts[0] if len(parts) > 0 else ""
        approval_id = parts[1] if len(parts) > 1 else ""

        return {
            "approval_id": approval_id,
            "action": action,
            "user_id": event.get("FromUserName", ""),
            "response_code": event.get("ResponseCode", ""),
        }

    elif platform == "dingtalk":
        # 钉钉: 通过 URL 参数传递（ActionCard 跳转链接）
        # 或者通过 body 传递（如果使用钉钉消息卡片回调）
        return {
            "approval_id": body.get("approval_id", ""),
            "action": body.get("action", ""),
            "user_id": body.get("staffId", body.get("userId", "")),
            "response_code": "",
        }

    elif platform == "feishu":
        # 飞书互动卡片回调
        action_data = body.get("action", {})
        value = action_data.get("value", {})

        return {
            "approval_id": value.get("approval_id", ""),
            "action": value.get("action", ""),
            "user_id": body.get("open_id", body.get("user_id", "")),
            "response_code": body.get("token", ""),
        }

    return {
        "approval_id": "",
        "action": "",
        "user_id": "",
        "response_code": "",
    }


@router.post("/{platform}/approval")
async def handle_approval_callback(platform: str, request: Request):
    """
    处理 IM 内点击"批准/拒绝"按钮的回调。

    Args:
        platform: 平台标识 (wecom/dingtalk/feishu)
        request: 原始请求

    Returns:
        确认响应
    """
    if platform not in SUPPORTED_PLATFORMS:
        return api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            f"Unsupported platform: {platform}",
        )

    try:
        # 1. 读取请求体
        body_bytes = await request.body()

        # 2. 验证回调签名
        is_valid = False
        if platform == "wecom":
            signature = request.headers.get("msg_signature", "")
            is_valid = _verify_wecom_signature(body_bytes, signature)
        elif platform == "dingtalk":
            timestamp = request.headers.get("timestamp", "")
            signature = request.headers.get("sign", "")
            is_valid = _verify_dingtalk_signature(body_bytes, timestamp, signature)
        elif platform == "feishu":
            timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
            nonce = request.headers.get("X-Lark-Request-Nonce", "")
            signature = request.headers.get("X-Lark-Signature", "")
            is_valid = _verify_feishu_signature(body_bytes, timestamp, nonce, signature)

        if not is_valid:
            logger.warning(f"[im_callback] Invalid signature from {platform}")
            return api_error(
                ErrorCode.AUTH_TOKEN_INVALID,
                "Invalid callback signature",
            )

        # 飞书 URL 验证回调（首次配置时飞书会发 challenge）
        try:
            body_json = await request.json()
        except Exception:
            body_json = {}

        if platform == "feishu" and "challenge" in body_json:
            return {"challenge": body_json["challenge"]}

        # 3. 解析回调数据
        callback_data = await _parse_callback_data(platform, request)
        approval_id = callback_data.get("approval_id", "")
        action = callback_data.get("action", "")
        platform_user_id = callback_data.get("user_id", "")

        if not approval_id or not action:
            logger.warning(f"[im_callback] Missing approval_id or action in " f"{platform} callback")
            return api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                "Missing approval_id or action",
            )

        logger.info(
            f"[im_callback] Received {action} for approval {approval_id} " f"from {platform} user {platform_user_id}"
        )

        # 4. 调用审批链服务
        db = getattr(request.state, "db", None) or supabase
        if not db:
            return api_error(
                ErrorCode.SYSTEM_INTERNAL_ERROR,
                "Database not available",
            )

        # 查找 Nexus 用户
        nexus_user_id = None
        if platform_user_id:
            mapping_result = (
                await db.table("im_user_mappings")
                .select("user_id")
                .eq("platform", platform)
                .eq("platform_user_id", platform_user_id)
                .limit(1)
                .execute()
            )
            if mapping_result.data:
                nexus_user_id = mapping_result.data[0].get("user_id")

        # 推进审批流程
        try:
            from app.services.approval_chain import approval_chain_service

            decision = "approved" if action == "approve" else "rejected"
            await approval_chain_service.advance_step(
                request_id=approval_id,
                approver_id=nexus_user_id or "im_callback",
                decision=decision,
                comment=f"Via {platform} interactive card",
                db=db,
            )

            logger.info(
                f"[im_callback] Approval {approval_id} {decision} " f"by user {nexus_user_id or platform_user_id}"
            )

        except Exception as e:
            logger.error(f"[im_callback] Failed to advance approval {approval_id}: {e}")
            return api_error(
                ErrorCode.SYSTEM_INTERNAL_ERROR,
                f"Failed to process approval: {str(e)[:100]}",
            )

        return api_success(
            data={
                "approval_id": approval_id,
                "action": action,
                "status": "processed",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[im_callback] Callback error for {platform}: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
