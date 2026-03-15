"""
Shared utilities for tool modules.
Extracted to eliminate duplication across 23+ tool files.
"""

import uuid as _uuid

from app.core.database import supabase


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
