"""
P3 Enhancement: Standardized Error Handling and API Responses

Provides:
- Standard error codes for consistent API responses
- HTTP exception helpers
- Response wrapper for consistent API formatting
"""

import logging
from enum import StrEnum
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    """
    Standardized error codes for API responses.

    Format: CATEGORY_SPECIFIC_ERROR
    Categories:
    - AUTH: Authentication/Authorization errors
    - VALIDATION: Input validation errors
    - RESOURCE: Resource not found/conflict errors
    - RATE: Rate limiting errors
    - AI: AI service errors
    - DB: Database errors
    - SYSTEM: Internal system errors
    """

    # Authentication/Authorization (401, 403)
    AUTH_TOKEN_MISSING = "AUTH_TOKEN_MISSING"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_PERMISSION_DENIED = "AUTH_PERMISSION_DENIED"
    AUTH_ROLE_REQUIRED = "AUTH_ROLE_REQUIRED"

    # Validation (400)
    VALIDATION_INVALID_INPUT = "VALIDATION_INVALID_INPUT"
    VALIDATION_MISSING_FIELD = "VALIDATION_MISSING_FIELD"
    VALIDATION_INVALID_FORMAT = "VALIDATION_INVALID_FORMAT"
    VALIDATION_VALUE_OUT_OF_RANGE = "VALIDATION_VALUE_OUT_OF_RANGE"

    # Resource (404, 409)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"

    # Rate Limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    RATE_QUOTA_EXCEEDED = "RATE_QUOTA_EXCEEDED"

    # AI Service (500, 503)
    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"
    AI_SERVICE_TIMEOUT = "AI_SERVICE_TIMEOUT"
    AI_RESPONSE_INVALID = "AI_RESPONSE_INVALID"
    AI_CONTEXT_TOO_LONG = "AI_CONTEXT_TOO_LONG"

    # Database (500, 503)
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"
    DB_QUERY_ERROR = "DB_QUERY_ERROR"
    DB_INTEGRITY_ERROR = "DB_INTEGRITY_ERROR"

    # System (500)
    SYSTEM_INTERNAL_ERROR = "SYSTEM_INTERNAL_ERROR"
    SYSTEM_CONFIGURATION_ERROR = "SYSTEM_CONFIGURATION_ERROR"
    SYSTEM_MAINTENANCE = "SYSTEM_MAINTENANCE"


# Error code to HTTP status mapping
ERROR_STATUS_MAP: dict[ErrorCode, int] = {
    # 400 Bad Request
    ErrorCode.VALIDATION_INVALID_INPUT: 400,
    ErrorCode.VALIDATION_MISSING_FIELD: 400,
    ErrorCode.VALIDATION_INVALID_FORMAT: 400,
    ErrorCode.VALIDATION_VALUE_OUT_OF_RANGE: 400,
    # 401 Unauthorized
    ErrorCode.AUTH_TOKEN_MISSING: 401,
    ErrorCode.AUTH_TOKEN_INVALID: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    # 403 Forbidden
    ErrorCode.AUTH_PERMISSION_DENIED: 403,
    ErrorCode.AUTH_ROLE_REQUIRED: 403,
    # 404 Not Found
    ErrorCode.RESOURCE_NOT_FOUND: 404,
    # 409 Conflict
    ErrorCode.RESOURCE_ALREADY_EXISTS: 409,
    ErrorCode.RESOURCE_CONFLICT: 409,
    # 429 Too Many Requests
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.RATE_QUOTA_EXCEEDED: 429,
    # 500 Internal Server Error
    ErrorCode.AI_RESPONSE_INVALID: 500,
    ErrorCode.DB_QUERY_ERROR: 500,
    ErrorCode.DB_INTEGRITY_ERROR: 500,
    ErrorCode.SYSTEM_INTERNAL_ERROR: 500,
    ErrorCode.SYSTEM_CONFIGURATION_ERROR: 500,
    # 503 Service Unavailable
    ErrorCode.AI_SERVICE_UNAVAILABLE: 503,
    ErrorCode.AI_SERVICE_TIMEOUT: 503,
    ErrorCode.DB_CONNECTION_ERROR: 503,
    ErrorCode.SYSTEM_MAINTENANCE: 503,
}

# Error messages (Chinese)
ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.AUTH_TOKEN_MISSING: "请先登录",
    ErrorCode.AUTH_TOKEN_INVALID: "登录凭证无效",
    ErrorCode.AUTH_TOKEN_EXPIRED: "登录已过期，请重新登录",
    ErrorCode.AUTH_PERMISSION_DENIED: "权限不足",
    ErrorCode.AUTH_ROLE_REQUIRED: "需要特定角色权限",
    ErrorCode.VALIDATION_INVALID_INPUT: "输入数据无效",
    ErrorCode.VALIDATION_MISSING_FIELD: "缺少必填字段",
    ErrorCode.VALIDATION_INVALID_FORMAT: "数据格式错误",
    ErrorCode.VALIDATION_VALUE_OUT_OF_RANGE: "数值超出允许范围",
    ErrorCode.RESOURCE_NOT_FOUND: "资源不存在",
    ErrorCode.RESOURCE_ALREADY_EXISTS: "资源已存在",
    ErrorCode.RESOURCE_CONFLICT: "资源冲突",
    ErrorCode.RATE_LIMIT_EXCEEDED: "请求过于频繁，请稍后再试",
    ErrorCode.RATE_QUOTA_EXCEEDED: "已超出使用配额",
    ErrorCode.AI_SERVICE_UNAVAILABLE: "AI服务暂时不可用",
    ErrorCode.AI_SERVICE_TIMEOUT: "AI服务响应超时",
    ErrorCode.AI_RESPONSE_INVALID: "AI响应解析失败",
    ErrorCode.AI_CONTEXT_TOO_LONG: "对话内容过长",
    ErrorCode.DB_CONNECTION_ERROR: "数据库连接失败",
    ErrorCode.DB_QUERY_ERROR: "数据库查询错误",
    ErrorCode.DB_INTEGRITY_ERROR: "数据完整性错误",
    ErrorCode.SYSTEM_INTERNAL_ERROR: "系统内部错误",
    ErrorCode.SYSTEM_CONFIGURATION_ERROR: "系统配置错误",
    ErrorCode.SYSTEM_MAINTENANCE: "系统维护中",
}


class APIError(BaseModel):
    """Standard API error response format"""

    success: bool = False
    error: dict[str, Any]


class APISuccess(BaseModel):
    """Standard API success response format"""

    success: bool = True
    data: Any
    meta: dict[str, Any] | None = None


def api_error(
    code: ErrorCode,
    message: str | None = None,
    details: dict[str, Any] | None = None,
    log_error: bool = True,
) -> HTTPException:
    """
    Create a standardized HTTP exception.

    Usage:
        from app.core.errors import api_error, ErrorCode
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, details={"id": doc_id})

    Args:
        code: Standardized error code
        message: Optional custom message (defaults to standard message)
        details: Optional additional error details
        log_error: Whether to log the error

    Returns:
        HTTPException ready to be raised
    """
    status_code = ERROR_STATUS_MAP.get(code, 500)
    error_message = message or ERROR_MESSAGES.get(code, "未知错误")

    error_body = {"code": code.value, "message": error_message}

    if details:
        error_body["details"] = details

    if log_error:
        log_level = logging.WARNING if status_code < 500 else logging.ERROR
        logger.log(
            log_level,
            f"API Error: {code.value} - {error_message}",
            extra={"details": details},
        )

    return HTTPException(status_code=status_code, detail=error_body)


def api_success(data: Any, message: str | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Create a standardized success response.

    Usage:
        from app.core.errors import api_success
        return api_success(data={"user": user}, message="User created")

    Args:
        data: Response data
        message: Optional success message
        meta: Optional metadata (pagination, etc.)

    Returns:
        Dict ready to be returned from endpoint
    """
    response = {"success": True, "data": data}

    if message:
        response["message"] = message

    if meta:
        response["meta"] = meta

    return response


def api_list(
    items: list[Any],
    total: int | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> dict[str, Any]:
    """
    Create a standardized list response with pagination info.

    Usage:
        from app.core.errors import api_list
        return api_list(items=users, total=100, page=1, page_size=20)
    """
    response = {"success": True, "data": items, "meta": {"count": len(items)}}

    if total is not None:
        response["meta"]["total"] = total

    if page is not None:
        response["meta"]["page"] = page

    if page_size is not None:
        response["meta"]["page_size"] = page_size
        if total is not None:
            response["meta"]["total_pages"] = (total + page_size - 1) // page_size

    return response
