"""
API Key 认证中间件

支持 Bearer token 和 X-API-Key header 两种认证方式。
检查请求是否携带 API Key，如果有则验证并注入 org_id 到 request.state，
如果没有则降级到 JWT 认证（由 TenantContextMiddleware 处理）。
"""

import contextlib
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# API Key 请求的路径前缀（仅对 /api/ 路径启用）
API_PREFIX = "/api/"

# 排除的路径（不需要 API Key 检查）
EXCLUDED_PATHS = {
    "/api/api-keys",  # API Key 管理端点使用 JWT
    "/api/admin",  # 超级管理员端点使用 JWT
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    API Key 认证中间件

    认证优先级:
    1. X-API-Key header
    2. Authorization: Bearer sk-xxx (以 sk- 开头的 Bearer token)
    3. 降级到 JWT 认证（由后续的 TenantContextMiddleware 处理）
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # 初始化 API Key 相关 state
        request.state.api_key_id = None
        request.state.api_key_auth = False

        # 仅对 /api/ 路径检查
        if not request.url.path.startswith(API_PREFIX):
            return await call_next(request)

        # 排除特定路径
        for excluded in EXCLUDED_PATHS:
            if request.url.path.startswith(excluded):
                return await call_next(request)

        # 提取 API Key
        api_key = self._extract_api_key(request)

        if api_key:
            start_time = time.time()
            try:
                from app.services.api_key_service import api_key_service

                # 验证 API Key
                key_info = await api_key_service.validate_api_key(api_key)

                if key_info:
                    # 注入认证信息到 request.state
                    request.state.api_key_id = key_info["key_id"]
                    request.state.api_key_auth = True
                    request.state.org_id = key_info["organization_id"]
                    request.state.user_id = key_info.get("created_by")

                    # 使用全局 client（API Key 访问不走 RLS）
                    from app.core.database import supabase

                    request.state.db = supabase

                    logger.debug(
                        f"API Key 认证成功: key_id={key_info['key_id']}, " f"org_id={key_info['organization_id']}"
                    )

                    # 执行请求
                    response = await call_next(request)

                    # 记录使用日志（异步，不阻塞响应）
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    with contextlib.suppress(Exception):
                        await api_key_service.log_api_usage(
                            key_id=key_info["key_id"],
                            endpoint=request.url.path,
                            method=request.method,
                            status_code=response.status_code,
                            response_time_ms=elapsed_ms,
                        )

                    return response
                else:
                    # API Key 无效，不立即拒绝，让后续中间件尝试 JWT
                    logger.warning(f"API Key 验证失败，降级到 JWT: path={request.url.path}")

            except Exception as e:
                logger.warning(f"API Key 中间件错误: {e}")
                # 出错时也降级到 JWT 认证

        return await call_next(request)

    @staticmethod
    def _extract_api_key(request: Request) -> str | None:
        """
        从请求中提取 API Key

        支持两种方式:
        1. X-API-Key header
        2. Authorization: Bearer sk-xxx
        """
        # 方式 1: X-API-Key header
        x_api_key = request.headers.get("X-API-Key")
        if x_api_key and x_api_key.startswith("sk-"):
            return x_api_key

        # 方式 2: Authorization Bearer（仅当 token 以 sk- 开头时）
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer sk-"):
            return auth_header[7:]  # 去掉 "Bearer " 前缀

        return None
