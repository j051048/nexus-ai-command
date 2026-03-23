"""
Shared utilities for tool modules.
Extracted to eliminate duplication across 23+ tool files.
"""

import logging as _logging
import os as _os
import uuid as _uuid

from app.core.database import supabase

_logger = _logging.getLogger(__name__)
_IS_PRODUCTION = _os.getenv("ENV", "production").lower() not in ("dev", "development", "test")


def _get_client(config: dict = None):
    """Get scoped DB client if user token available, else fallback to service client."""
    token = config.get("token") if config else None
    return supabase.get_scoped_client(token) if token and supabase else supabase


def _validate_uuid(value: str, field_name: str = "ID") -> str | None:
    """验证UUID格式"""
    try:
        _uuid.UUID(value)
        return None
    except (ValueError, TypeError, AttributeError):
        return f"{field_name} '{value}' 不是有效的UUID格式。"


def safe_tool_error(e: Exception, action: str) -> str:
    """Return a sanitized error message for tool results.

    In production: logs the real exception, returns a generic message.
    In dev/test: includes the original error for debugging.
    """
    _logger.error(f"Tool error during {action}: {e}", exc_info=True)
    if _IS_PRODUCTION:
        return f"❌ {action}失败，请稍后重试或联系管理员。"
    return f"❌ {action}失败: {e}"
