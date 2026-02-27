"""
#39: CSRF 防护中间件

对于主要使用 Bearer Token 认证的 FastAPI 应用，CSRF 风险较低。
但对于使用 Cookie 认证的状态变更请求，添加轻量级 CSRF 检查:

1. Bearer Token 认证的请求 → 跳过 CSRF 检查
2. Webhook/回调路径 → 跳过 CSRF 检查
3. Cookie 认证的 POST/PUT/DELETE 请求 → 要求以下任一:
   - X-Requested-With 请求头（AJAX 标识）
   - X-CSRF-Token 请求头中的有效 CSRF Token
"""

import hashlib
import hmac
import logging
import os
import secrets
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# CSRF Token 密钥（从环境变量获取或自动生成）
_CSRF_SECRET = os.environ.get("CSRF_SECRET", secrets.token_hex(32))

# CSRF Token 有效期（秒）
_CSRF_TOKEN_TTL = 3600  # 1小时


def generate_csrf_token(session_id: str = "") -> str:
    """
    生成 CSRF Token。

    格式: timestamp.signature
    其中 signature = HMAC(secret, timestamp + session_id)
    """
    timestamp = str(int(time.time()))
    payload = f"{timestamp}:{session_id}"
    signature = hmac.new(
        _CSRF_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{timestamp}.{signature}"


def verify_csrf_token(token: str, session_id: str = "") -> bool:
    """验证 CSRF Token 的有效性和时效性。"""
    if not token:
        return False

    parts = token.split(".", 1)
    if len(parts) != 2:
        return False

    timestamp_str, provided_signature = parts

    try:
        timestamp = int(timestamp_str)
    except (ValueError, TypeError):
        return False

    # 检查时效性
    if time.time() - timestamp > _CSRF_TOKEN_TTL:
        return False

    # 验证签名
    payload = f"{timestamp_str}:{session_id}"
    expected_signature = hmac.new(
        _CSRF_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(provided_signature, expected_signature)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    轻量级 CSRF 防护中间件。

    仅对使用 Cookie 认证的状态变更请求（POST/PUT/DELETE）进行 CSRF 检查。
    Bearer Token 认证的请求和特定路径（Webhook、回调）自动跳过。
    """

    # 状态变更方法
    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # 跳过 CSRF 检查的路径前缀
    SKIP_PATH_PREFIXES = (
        "/api/webhooks/",
        "/api/im-callbacks/",
        "/api/im-oauth/",
    )

    # 跳过 CSRF 检查的完整路径
    SKIP_PATHS = {
        "/health",
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
        "/api/test-ai",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        # 非状态变更方法 → 跳过
        if request.method not in self.MUTATING_METHODS:
            return await call_next(request)

        path = request.url.path

        # 跳过特定路径
        if path in self.SKIP_PATHS:
            return await call_next(request)

        # 跳过特定路径前缀（Webhook、回调等）
        for prefix in self.SKIP_PATH_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Bearer Token 认证 → 不需要 CSRF 保护
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return await call_next(request)

        # API Key 认证 → 不需要 CSRF 保护
        if request.headers.get("x-api-key"):
            return await call_next(request)

        # 到这里说明可能是 Cookie 认证的请求，需要 CSRF 检查
        # 但如果根本没有任何认证 cookie，说明是未认证请求，应由 auth 中间件处理
        cookies = request.cookies
        has_auth_cookie = any(
            k.startswith("sb-") or k in ("session", "access_token", "refresh_token")
            for k in cookies
        )
        if not has_auth_cookie:
            # 无 cookie 认证 → 不存在 CSRF 风险，放行到 auth 中间件
            return await call_next(request)

        # 检查 1: X-Requested-With 头（AJAX 标识）
        if request.headers.get("x-requested-with"):
            return await call_next(request)

        # 检查 2: X-CSRF-Token 头
        csrf_token = request.headers.get("x-csrf-token", "")
        if csrf_token and verify_csrf_token(csrf_token):
            return await call_next(request)

        # CSRF 检查失败
        logger.warning(
            f"[CSRF] 拒绝请求: {request.method} {path} - "
            f"缺少有效的 CSRF 令牌或 AJAX 标识"
        )
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": {
                    "code": "CSRF_VALIDATION_FAILED",
                    "message": "CSRF 验证失败，请确保请求包含有效的 CSRF 令牌",
                },
            },
        )
