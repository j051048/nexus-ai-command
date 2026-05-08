"""
API key authentication middleware.

Supports X-API-Key and Authorization: Bearer sk-* credentials. Requests without
an API key continue to JWT authentication, but requests that explicitly provide
an API key must pass API key validation and are never silently downgraded.
"""

import contextlib
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

API_PREFIX = "/api/"

EXCLUDED_PATHS = {
    "/api/api-keys",  # API key management endpoints use JWT.
    "/api/admin",  # Super-admin endpoints use JWT.
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Authenticate explicit API key requests before JWT fallback."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.api_key_id = None
        request.state.api_key_auth = False

        if not request.url.path.startswith(API_PREFIX):
            return await call_next(request)

        for excluded in EXCLUDED_PATHS:
            if request.url.path.startswith(excluded):
                return await call_next(request)

        api_key = self._extract_api_key(request)
        if not api_key:
            return await call_next(request)

        start_time = time.time()
        try:
            from app.services.api_key_service import api_key_service

            key_info = await api_key_service.validate_api_key(api_key)
            if not key_info:
                logger.warning("API Key validation failed: path=%s", request.url.path)
                return self._auth_error(
                    401,
                    "INVALID_API_KEY",
                    "Invalid API key",
                )

            request.state.api_key_id = key_info["key_id"]
            request.state.api_key_auth = True
            request.state.org_id = key_info["organization_id"]
            request.state.user_id = key_info.get("created_by")

            from app.core.database import supabase

            if supabase:
                request.state.db = supabase.get_org_filtered_client(
                    key_info["organization_id"]
                )
            else:
                request.state.db = None

            logger.debug(
                "API Key authenticated: key_id=%s org_id=%s",
                key_info["key_id"],
                key_info["organization_id"],
            )

            response = await call_next(request)

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

        except Exception as exc:
            logger.warning("API Key middleware error: %s", exc)
            return self._auth_error(
                503,
                "API_KEY_AUTH_UNAVAILABLE",
                "API key authentication is temporarily unavailable",
            )

    @staticmethod
    def _extract_api_key(request: Request) -> str | None:
        x_api_key = request.headers.get("X-API-Key")
        if x_api_key and x_api_key.startswith("sk-"):
            return x_api_key

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer sk-"):
            return auth_header[7:]

        return None

    @staticmethod
    def _auth_error(status_code: int, code: str, message: str) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error": {
                    "code": code,
                    "message": message,
                },
            },
        )
