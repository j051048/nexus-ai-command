"""
P3 Enhancement: Common Dependencies for FastAPI Endpoints

Provides reusable dependency injection functions for:
- Authentication
- Pagination
- Rate limiting
- Role-based access control
"""

import logging

from fastapi import Depends, HTTPException, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error

logger = logging.getLogger(__name__)


async def get_db(request: Request):
    """
    Dependency to get the database client for the current request context.

    The client is injected into request.state by TenantContextMiddleware:
    - JWT auth → scoped client with RLS via user token
    - API Key auth → OrgFilteredClient with application-level org isolation

    P0-1 Security Fix: NEVER fall back to global service_role client.
    If middleware fails to set request.state.db, reject the request
    to prevent RLS bypass and cross-tenant data leakage.

    Usage in routers:
        @router.get("/items")
        async def list_items(db=Depends(get_db)):
            result = await db.table("items").select("*").execute()
    """
    db = getattr(request.state, "db", None)
    if db is None:
        logger.error(
            "P0-1: get_db() called without tenant context — "
            "TenantContextMiddleware may have failed or route is not covered. "
            "path=%s method=%s",
            request.url.path,
            request.method,
        )
        raise HTTPException(
            status_code=401,
            detail="租户上下文未建立，请重新登录",
        )
    return db


async def get_org_id(request: Request) -> str | None:
    """
    Dependency to get the organization_id from request context.
    Set by TenantContextMiddleware after auth.
    """
    return getattr(request.state, "org_id", None)


# ============== Role-Based Access Control ==============


async def _get_user_role(user_id: str) -> str | None:
    """Helper to fetch user role from database"""
    from app.core.database import supabase
    from app.services.cache_service import cache_service

    # Try cache first
    cached_role = await cache_service.get_user_role(user_id)
    if cached_role:
        return cached_role

    # Fetch from database
    if supabase:
        try:
            result = (
                await supabase.table("users")
                .select("role")
                .eq("id", user_id)
                .single()
                .execute()
            )
            if result.data:
                role = result.data.get("role", "employee")
                await cache_service.set_user_role(user_id, role)
                return role
        except Exception as e:
            logger.warning(f"Failed to fetch user role: {e}")

    return "employee"


def require_role(allowed_roles: list[str]):
    """
    Dependency factory for role-based access control.

    Usage:
        @router.get("/admin/users")
        async def admin_only(user_id: str = Depends(require_role(["admin", "boss"]))):
            ...
    """

    async def role_checker(user_id: str = Depends(get_current_user_id)) -> str:
        role = await _get_user_role(user_id)

        if role not in allowed_roles:
            raise api_error(
                ErrorCode.AUTH_ROLE_REQUIRED,
                message=f"需要以下角色之一: {', '.join(allowed_roles)}",
                details={"required_roles": allowed_roles, "user_role": role},
            )

        return user_id

    return role_checker


def require_admin(user_id: str = Depends(get_current_user_id)) -> str:
    """Convenience dependency for admin-only endpoints"""
    return require_role(["admin", "founder", "boss"])(user_id)


# ============== Optional Auth ==============
