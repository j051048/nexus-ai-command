"""
P3 Enhancement: Common Dependencies for FastAPI Endpoints

Provides reusable dependency injection functions for:
- Authentication
- Pagination
- Rate limiting
- Role-based access control
"""

import logging
from collections.abc import Callable
from functools import wraps

from fastapi import Depends, HTTPException, Query, Request

from app.core.auth import get_current_user_id
from app.core.database import supabase  # Global fallback
from app.core.errors import ErrorCode, api_error
from app.core.pagination import FilterParams, PaginationParams, SearchParams, SortParams

logger = logging.getLogger(__name__)


async def get_db(request: Request):
    """
    Dependency to get the database client for the current request context.
    The client is injected into request.state by TenantContextMiddleware.
    """
    return getattr(request.state, "db", supabase)


# ============== Pagination Dependencies ==============


def get_pagination(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    """
    Pagination dependency.

    Usage:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends(get_pagination)):
            offset = pagination.offset
            limit = pagination.limit
    """
    return PaginationParams(page=page, page_size=page_size)


def get_sorting(
    sort_by: str | None = Query(default=None, description="Field to sort by"),
    sort_order: str = Query(
        default="desc", regex="^(asc|desc)$", description="Sort order"
    ),
) -> SortParams:
    """Sorting dependency"""
    return SortParams(sort_by=sort_by, sort_order=sort_order)


def get_search(
    q: str | None = Query(default=None, max_length=200, description="Search query")
) -> SearchParams:
    """Search dependency"""
    return SearchParams(q=q)


def get_filters(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: str | None = Query(default=None),
    sort_order: str = Query(default="desc", regex="^(asc|desc)$"),
    q: str | None = Query(default=None, max_length=200),
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> FilterParams:
    """
    Combined filter dependency for list endpoints.

    Usage:
        @router.get("/documents")
        async def list_docs(filters: FilterParams = Depends(get_filters)):
            # Use filters.page, filters.q, filters.start_date, etc.
    """
    return FilterParams(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        q=q,
        start_date=start_date,
        end_date=end_date,
        status=status,
    )


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


def require_manager(user_id: str = Depends(get_current_user_id)) -> str:
    """Convenience dependency for manager-level endpoints"""
    return require_role(["admin", "founder", "boss", "manager"])(user_id)


# ============== Optional Auth ==============


async def get_optional_user_id(authorization: str | None = None) -> str | None:
    """
    Optional authentication - returns user_id if authenticated, None otherwise.

    Useful for endpoints that work differently for authenticated vs anonymous users.
    """
    if not authorization:
        return None

    try:
        # Reuse the existing auth mechanism
        from app.core.auth import get_current_user_id

        return await get_current_user_id(authorization=authorization)
    except HTTPException:
        return None


# ============== Decorators ==============


def requires_database(func: Callable):
    """
    Decorator to ensure database is available before executing endpoint.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        from app.core.database import supabase

        if not supabase:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, message="数据库服务不可用")
        return await func(*args, **kwargs)

    return wrapper
