"""
Global Exception Handlers for FastAPI

Registers standardized exception handlers that ensure all errors
return a consistent JSON format:
    {"success": false, "error": {"code": "...", "message": "..."}}

Key rules:
- NEVER expose stack traces or internal details in production
- Always log the full exception with traceback
- Include request trace_id (from X-Trace-ID header) in error response
"""

import logging
import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.core.responses import UTF8JSONResponse

logger = logging.getLogger(__name__)


async def generic_exception_handler(request: Request, exc: Exception) -> UTF8JSONResponse:
    """Catch unhandled exceptions - return 500 with safe message, log full traceback."""
    trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID", "")

    # Log full traceback for debugging
    logger.error(
        "Unhandled exception: %s | path=%s method=%s trace_id=%s",
        exc,
        request.url.path,
        request.method,
        trace_id,
        exc_info=True,
    )

    # Determine if we're in production (never expose internals)
    from app.core.config import settings

    error_body: dict = {
        "code": "SYSTEM_INTERNAL_ERROR",
        "message": "系统内部错误，请稍后重试",
    }

    if trace_id:
        error_body["trace_id"] = trace_id

    # In development, include the exception type and message for debugging
    if not settings.IS_PRODUCTION:
        error_body["detail"] = f"{type(exc).__name__}: {str(exc)}"

    return UTF8JSONResponse(
        status_code=500,
        content={"success": False, "error": error_body},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> UTF8JSONResponse:
    """Pydantic validation errors - return 422 with field-level details."""
    trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID", "")

    # Build field-level error details
    field_errors = []
    for err in exc.errors():
        loc = " -> ".join(str(l) for l in err.get("loc", []))
        field_errors.append({
            "field": loc,
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        })

    logger.warning(
        "Validation error: path=%s method=%s fields=%s trace_id=%s",
        request.url.path,
        request.method,
        [e["field"] for e in field_errors],
        trace_id,
    )

    error_body: dict = {
        "code": "VALIDATION_INVALID_INPUT",
        "message": "输入数据校验失败",
        "details": field_errors,
    }

    if trace_id:
        error_body["trace_id"] = trace_id

    return UTF8JSONResponse(
        status_code=422,
        content={"success": False, "error": error_body},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> UTF8JSONResponse:
    """Standardize HTTP exceptions into our api_error format."""
    trace_id = request.headers.get("X-Trace-ID") or request.headers.get("X-Request-ID", "")

    error_content = exc.detail

    # If detail is already a dict (from api_error), use it directly
    if isinstance(error_content, dict):
        error_body = error_content
    else:
        # Wrap string detail into standard format
        error_body = {
            "code": "HTTP_ERROR",
            "message": str(error_content),
        }

    if trace_id and "trace_id" not in error_body:
        error_body["trace_id"] = trace_id

    # Log server errors with higher severity
    if exc.status_code >= 500:
        logger.error(
            "HTTP %s: %s | path=%s trace_id=%s",
            exc.status_code,
            error_content,
            request.url.path,
            trace_id,
        )
    else:
        logger.warning(
            "HTTP %s: %s | path=%s trace_id=%s",
            exc.status_code,
            error_content,
            request.url.path,
            trace_id,
        )

    return UTF8JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": error_body},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI app."""
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
