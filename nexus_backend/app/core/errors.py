"""
P3 Enhancement: Standardized Error Handling and API Responses

Provides:
- Standard error codes for consistent API responses
- HTTP exception helpers
- Response wrapper for consistent API formatting
"""

import logging
import os
from enum import StrEnum
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)


# Error message prefixes for log parsing
ERROR_PREFIX_MAP = {
    "AUTH": "[AUTH_ERROR]",
    "VALIDATION": "[VALIDATION_ERROR]",
    "RESOURCE": "[RESOURCE_ERROR]",
    "RATE": "[RATE_ERROR]",
    "AI": "[AI_ERROR]",
    "DB": "[DB_ERROR]",
    "SYSTEM": "[SYSTEM_ERROR]",
    "VMD": "[VMD_ERROR]",
    "KB": "[KB_ERROR]",
    "COMPLIANCE": "[COMPLIANCE_ERROR]",
    "INTEGRATION": "[INTEGRATION_ERROR]",
}


def format_error_log(code: str, message: str, details: dict = None, trace_id: str = None) -> str:
    """Format error message with prefix for better log parsing"""
    category = code.split("_")[0]
    prefix = ERROR_PREFIX_MAP.get(category, "[ERROR]")

    parts = [prefix, message]
    if details:
        parts.append(f"details={details}")
    if trace_id:
        parts.append(f"trace_id={trace_id}")

    return " | ".join(parts)


def extract_db_error_details(error: Exception) -> dict:
    """Extract detailed info from database errors"""
    error_dict = {"type": type(error).__name__, "message": str(error)}

    # Supabase/PostgreSQL error details
    if hasattr(error, "code"):
        error_dict["code"] = error.code
    if hasattr(error, "details"):
        error_dict["details"] = error.details
    if hasattr(error, "hint"):
        error_dict["hint"] = error.hint

    return error_dict


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

    # LLM Gateway (600xxx series per V2.0 spec)
    LLM_MODEL_NOT_FOUND = "LLM_MODEL_NOT_FOUND"  # 600001
    LLM_CONNECTIVITY_FAILED = "LLM_CONNECTIVITY_FAILED"  # 600002
    LLM_MODEL_DISABLED = "LLM_MODEL_DISABLED"  # 600003
    LLM_QUOTA_EXHAUSTED = "LLM_QUOTA_EXHAUSTED"  # 600004
    LLM_CALL_FAILED = "LLM_CALL_FAILED"  # 601001
    LLM_CALL_TIMEOUT = "LLM_CALL_TIMEOUT"  # 601002
    LLM_ADAPTER_NOT_FOUND = "LLM_ADAPTER_NOT_FOUND"  # 601003
    LLM_TOOL_FORMAT_ERROR = "LLM_TOOL_FORMAT_ERROR"  # 601004

    # VMD Tasks (602xxx)
    VMD_TASK_NOT_FOUND = "VMD_TASK_NOT_FOUND"  # 602001
    VMD_TASK_STATUS_INVALID = "VMD_TASK_STATUS_INVALID"  # 602002
    VMD_TASK_EXEC_FAILED = "VMD_TASK_EXEC_FAILED"  # 602003

    # Knowledge Base (603xxx)
    KB_DOC_NOT_FOUND = "KB_DOC_NOT_FOUND"  # 603001
    KB_PARSE_FAILED = "KB_PARSE_FAILED"  # 603002
    KB_VECTORIZE_FAILED = "KB_VECTORIZE_FAILED"  # 603003
    KB_NO_PERMISSION = "KB_NO_PERMISSION"  # 603004

    # Compliance (605xxx)
    COMPLIANCE_RULE_NOT_FOUND = "COMPLIANCE_RULE_NOT_FOUND"  # 605001
    COMPLIANCE_CHECK_FAILED = "COMPLIANCE_CHECK_FAILED"  # 605002

    # Integration (606xxx)
    INTEGRATION_CONNECT_FAILED = "INTEGRATION_CONNECT_FAILED"  # 606001
    INTEGRATION_SYNC_FAILED = "INTEGRATION_SYNC_FAILED"  # 606002


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
    # LLM Gateway
    ErrorCode.LLM_MODEL_NOT_FOUND: 404,
    ErrorCode.LLM_CONNECTIVITY_FAILED: 503,
    ErrorCode.LLM_MODEL_DISABLED: 403,
    ErrorCode.LLM_QUOTA_EXHAUSTED: 429,
    ErrorCode.LLM_CALL_FAILED: 502,
    ErrorCode.LLM_CALL_TIMEOUT: 504,
    ErrorCode.LLM_ADAPTER_NOT_FOUND: 404,
    ErrorCode.LLM_TOOL_FORMAT_ERROR: 400,
    # VMD Tasks
    ErrorCode.VMD_TASK_NOT_FOUND: 404,
    ErrorCode.VMD_TASK_STATUS_INVALID: 400,
    ErrorCode.VMD_TASK_EXEC_FAILED: 500,
    # Knowledge Base
    ErrorCode.KB_DOC_NOT_FOUND: 404,
    ErrorCode.KB_PARSE_FAILED: 500,
    ErrorCode.KB_VECTORIZE_FAILED: 500,
    ErrorCode.KB_NO_PERMISSION: 403,
    # Compliance
    ErrorCode.COMPLIANCE_RULE_NOT_FOUND: 404,
    ErrorCode.COMPLIANCE_CHECK_FAILED: 500,
    # Integration
    ErrorCode.INTEGRATION_CONNECT_FAILED: 503,
    ErrorCode.INTEGRATION_SYNC_FAILED: 500,
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
    # LLM Gateway
    ErrorCode.LLM_MODEL_NOT_FOUND: "模型配置不存在",
    ErrorCode.LLM_CONNECTIVITY_FAILED: "模型连通性测试失败",
    ErrorCode.LLM_MODEL_DISABLED: "模型已停用",
    ErrorCode.LLM_QUOTA_EXHAUSTED: "模型调用限额已耗尽",
    ErrorCode.LLM_CALL_FAILED: "模型调用失败",
    ErrorCode.LLM_CALL_TIMEOUT: "模型响应超时",
    ErrorCode.LLM_ADAPTER_NOT_FOUND: "适配器不存在",
    ErrorCode.LLM_TOOL_FORMAT_ERROR: "工具调用格式错误",
    # VMD Tasks
    ErrorCode.VMD_TASK_NOT_FOUND: "任务不存在",
    ErrorCode.VMD_TASK_STATUS_INVALID: "任务状态异常",
    ErrorCode.VMD_TASK_EXEC_FAILED: "任务执行失败",
    # Knowledge Base
    ErrorCode.KB_DOC_NOT_FOUND: "文档不存在",
    ErrorCode.KB_PARSE_FAILED: "文档解析失败",
    ErrorCode.KB_VECTORIZE_FAILED: "向量化处理失败",
    ErrorCode.KB_NO_PERMISSION: "无知识库访问权限",
    # Compliance
    ErrorCode.COMPLIANCE_RULE_NOT_FOUND: "合规规则不存在",
    ErrorCode.COMPLIANCE_CHECK_FAILED: "合规校验失败",
    # Integration
    ErrorCode.INTEGRATION_CONNECT_FAILED: "外部系统对接失败",
    ErrorCode.INTEGRATION_SYNC_FAILED: "数据同步失败",
}



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
    safe_message = ERROR_MESSAGES.get(code, "未知错误")
    is_production = os.getenv("ENV", "production").lower() not in ("dev", "development", "test")

    # Security: For 500-level errors in production, never expose str(e) to users.
    # The caller's `message` (usually str(e)) is logged but replaced with a safe default.
    if status_code >= 500 and is_production and message:
        raw_error = message  # preserve for logging
        error_message = safe_message
    else:
        raw_error = None
        error_message = message or safe_message

    error_body: dict[str, Any] = {"code": code.value, "message": error_message}

    if details:
        error_body["details"] = details

    if log_error:
        log_level = logging.WARNING if status_code < 500 else logging.ERROR
        log_msg = format_error_log(
            code=code.value,
            message=raw_error or error_message,
            details=details,
            trace_id=details.get("trace_id") if details else None
        )
        logger.log(log_level, log_msg)

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


# ── #16: User-Friendly Error Mapping ─────────────────────────────────────────

_USER_FRIENDLY_ERRORS: dict[str, str] = {
    # AI 服务
    "rate_limit": "🕐 AI 服务繁忙，请稍后再试。",
    "timeout": "⏱️ 请求超时，请缩短问题长度后重试。",
    "context_too_long": "📝 对话内容过长，建议开启新对话。",
    "model_overloaded": "🔄 模型负载较高，请稍候重试。",
    "api_key_invalid": "🔑 AI 服务配置异常，请联系管理员。",
    # 工具执行
    "tool_not_found": "🔧 该功能暂不可用，请尝试其他方式。",
    "tool_timeout": "⏱️ 操作超时，请稍后重试。",
    "tool_permission_denied": "🔒 您没有执行此操作的权限。",
    "tool_validation_error": "📋 参数不完整，请补充必要信息后重试。",
    # 数据库
    "db_connection": "🗄️ 数据服务暂时不可用，请稍后重试。",
    "db_not_found": "🔍 未找到相关数据。",
    # 通用
    "unknown": "⚠️ 系统遇到意外问题，请稍后重试。如问题持续，请联系管理员。",
}


def friendly_error(error_key: str | None = None, raw_error: str | None = None) -> str:
    """#16: Convert internal error keys/messages to user-friendly text."""
    if error_key and error_key in _USER_FRIENDLY_ERRORS:
        return _USER_FRIENDLY_ERRORS[error_key]
    # Try matching raw error string to known patterns
    if raw_error:
        raw_lower = raw_error.lower()
        if "rate limit" in raw_lower or "429" in raw_lower:
            return _USER_FRIENDLY_ERRORS["rate_limit"]
        if "timeout" in raw_lower or "timed out" in raw_lower:
            return _USER_FRIENDLY_ERRORS["timeout"]
        if "context" in raw_lower and ("long" in raw_lower or "length" in raw_lower):
            return _USER_FRIENDLY_ERRORS["context_too_long"]
        if "permission" in raw_lower or "forbidden" in raw_lower or "403" in raw_lower:
            return _USER_FRIENDLY_ERRORS["tool_permission_denied"]
    return _USER_FRIENDLY_ERRORS["unknown"]
