"""
#38: 敏感字段脱敏

提供常见敏感字段的脱敏函数和自动脱敏中间件，
防止 API 响应中泄露手机号、身份证、API Key 等敏感信息。
"""

import json
import logging
import re
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# 需要自动脱敏的字段名列表（支持嵌套 JSON 的递归匹配）
SENSITIVE_FIELD_NAMES: set[str] = {
    "phone",
    "mobile",
    "phone_number",
    "mobile_number",
    "id_card",
    "identity_card",
    "id_number",
    "api_key",
    "secret_key",
    "api_key_encrypted",
    "secret_key_encrypted",
    "access_token",
    "refresh_token",
}

# 需要 email 脱敏的字段名
EMAIL_FIELD_NAMES: set[str] = {"email", "user_email"}


def mask_phone(phone: str) -> str:
    """
    手机号脱敏: 138****1234

    保留前3位和后4位，中间用 **** 替代。
    """
    if not phone or not isinstance(phone, str):
        return phone
    phone = phone.strip()
    if len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def mask_id_card(id_card: str) -> str:
    """
    身份证号脱敏: 110***********1234

    保留前3位和后4位，中间用 * 替代。
    """
    if not id_card or not isinstance(id_card, str):
        return id_card
    id_card = id_card.strip()
    if len(id_card) < 8:
        return id_card
    masked_len = len(id_card) - 7
    return f"{id_card[:3]}{'*' * masked_len}{id_card[-4:]}"


def mask_api_key(key: str) -> str:
    """
    API Key 脱敏: sk-...abc

    保留前缀（如 sk-）和最后3个字符，中间用 ... 替代。
    """
    if not key or not isinstance(key, str):
        return key
    key = key.strip()
    if len(key) <= 8:
        return "***"
    # 找到前缀（如 sk-, pk- 等）
    prefix_match = re.match(r"^([a-zA-Z]{1,4}[-_])", key)
    if prefix_match:
        prefix = prefix_match.group(1)
        return f"{prefix}...{key[-3:]}"
    return f"{key[:3]}...{key[-3:]}"


def mask_email(email: str) -> str:
    """
    邮箱脱敏: u***@example.com

    保留第一个字符和域名，中间用 *** 替代。
    """
    if not email or not isinstance(email, str):
        return email
    email = email.strip()
    at_idx = email.find("@")
    if at_idx <= 0:
        return email
    local_part = email[:at_idx]
    domain = email[at_idx:]
    if len(local_part) <= 1:
        return f"{local_part}***{domain}"
    return f"{local_part[0]}***{domain}"


def mask_sensitive_value(field_name: str, value: str) -> str:
    """根据字段名选择合适的脱敏策略。"""
    if not isinstance(value, str) or not value:
        return value

    lower_name = field_name.lower()

    if lower_name in EMAIL_FIELD_NAMES:
        return mask_email(value)
    if lower_name in ("phone", "mobile", "phone_number", "mobile_number"):
        return mask_phone(value)
    if lower_name in ("id_card", "identity_card", "id_number"):
        return mask_id_card(value)
    if lower_name in (
        "api_key",
        "secret_key",
        "api_key_encrypted",
        "secret_key_encrypted",
        "access_token",
        "refresh_token",
    ):
        return mask_api_key(value)
    # 默认：通用脱敏
    return mask_api_key(value)


def mask_dict_recursive(data: Any) -> Any:
    """
    递归遍历字典/列表，对敏感字段自动脱敏。
    不修改原对象，返回脱敏后的副本。
    """
    if isinstance(data, dict):
        result = {}
        for k, v in data.items():
            lower_k = k.lower()
            if lower_k in SENSITIVE_FIELD_NAMES or lower_k in EMAIL_FIELD_NAMES:
                if isinstance(v, str):
                    result[k] = mask_sensitive_value(k, v)
                else:
                    result[k] = v
            else:
                result[k] = mask_dict_recursive(v)
        return result
    elif isinstance(data, list):
        return [mask_dict_recursive(item) for item in data]
    return data


class DataMaskingMiddleware(BaseHTTPMiddleware):
    """
    响应数据自动脱敏中间件。

    对 JSON 响应体中的敏感字段自动进行脱敏处理。
    仅对 application/json 响应生效。

    跳过的路径:
    - /docs, /redoc, /openapi.json (文档)
    - /health (健康检查)
    - /api/admin/* (管理员接口可能需要完整数据)
    """

    # 跳过脱敏的路径前缀
    SKIP_PATHS: set[str] = {
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/favicon.ico",
    }

    # 流式/SSE 路径前缀 — 不能缓冲整个 body
    STREAMING_PATH_PREFIXES: tuple[str, ...] = (
        "/api/chat",
        "/api/ws",
        "/api/agent",
        "/api/sse",
    )

    # 管理员路径前缀（可选跳过）
    ADMIN_PATH_PREFIX = "/api/super-admin"

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 跳过非 JSON 响应
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # 跳过特定路径
        path = request.url.path
        if path in self.SKIP_PATHS:
            return response
        if path.startswith(self.ADMIN_PATH_PREFIX):
            return response

        # P0 Fix: 跳过流式/SSE 路径，避免破坏 SSE 流 + 内存激增
        if path.startswith(self.STREAMING_PATH_PREFIXES):
            return response

        # 对非流式 JSON 响应进行脱敏处理
        # 注意: BaseHTTPMiddleware 的 call_next 总是返回 StreamingResponse，
        # 所以需要读取 body 再重建 Response
        try:
            body_chunks = []
            async for chunk in response.body_iterator:
                if isinstance(chunk, bytes):
                    body_chunks.append(chunk)
                else:
                    body_chunks.append(chunk.encode("utf-8"))
            body = b"".join(body_chunks)

            data = json.loads(body)
            masked_data = mask_dict_recursive(data)
            masked_body = json.dumps(masked_data, ensure_ascii=False).encode("utf-8")

            # 移除原始 Content-Length，让 Starlette 根据新 body 重新计算
            headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
            return Response(
                content=masked_body,
                status_code=response.status_code,
                headers=headers,
                media_type=response.media_type,
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        except Exception as e:
            logger.debug(f"[DataMasking] 脱敏处理异常: {e}")
            return response
