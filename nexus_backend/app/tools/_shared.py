"""
Shared utilities for tool modules.
Extracted to eliminate duplication across 23+ tool files.
"""

import logging as _logging
import os as _os
import uuid as _uuid

from app.core.database import supabase

_logger = _logging.getLogger(__name__)
_IS_PRODUCTION = _os.getenv("ENV", "production").lower() not in (
    "dev",
    "development",
    "test",
)


def _get_client(config: dict = None):
    """Get scoped DB client with tenant isolation.

    P0 Security: NEVER fallback to global service_role client.
    - If user token is available → use RLS-scoped client
    - If org_id is available → use OrgFilteredClient (application-level isolation)
    - Otherwise → raise error to prevent cross-tenant data access

    Config keys used:
    - token: User JWT token (from authenticated request)
    - org_id: Organization ID (from TenantContextMiddleware)
    """
    if not supabase:
        raise RuntimeError("Database not configured")

    token = config.get("token") if config else None
    if token:
        return supabase.get_scoped_client(token)

    # Fallback: use OrgFilteredClient for application-level tenant isolation
    # This covers cases where token is unavailable (e.g., Celery tasks, proactive agent)
    org_id = config.get("org_id") if config else None
    if org_id:
        return supabase.get_org_filtered_client(org_id)

    # P0 Security: Refuse to operate without tenant context
    _logger.warning(
        "[_get_client] No token or org_id in config — refusing to return "
        "service_role client. Caller must provide tenant context."
    )
    raise PermissionError(
        "缺少租户上下文 (Missing tenant context: no token or org_id in config). "
        "工具调用必须携带用户 token 或组织 ID。"
    )


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
    Detects "relation does not exist" errors and returns a module-not-enabled hint.
    """
    err_str = str(e).lower()
    # PostgREST / PostgreSQL: relation "xxx" does not exist
    if "does not exist" in err_str and ("relation" in err_str or "table" in err_str):
        _logger.warning(f"Tool '{action}' hit missing table: {e}")
        return (
            f"ℹ️ {action}功能暂未启用（相关数据表尚未创建）。如需使用请联系管理员开通。"
        )

    _logger.error(f"Tool error during {action}: {e}", exc_info=True)
    if _IS_PRODUCTION:
        return f"❌ {action}失败，请稍后重试或联系管理员。"
    return f"❌ {action}失败: {e}"
