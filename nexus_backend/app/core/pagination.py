"""
P3 Enhancement: Pagination and Query Helpers

Provides standardized pagination for list endpoints.
"""

import logging
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

T = TypeVar("T")


class PaginationParams(BaseModel):
    """
    Standard pagination parameters for list endpoints.

    Usage in endpoints:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            ...
    """

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database queries"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit for database queries"""
        return self.page_size


class SortParams(BaseModel):
    """
    Standard sorting parameters.
    """

    sort_by: str | None = Field(default=None, description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: str) -> str:
        return v.lower() if v else "desc"


class SearchParams(BaseModel):
    """
    Standard search parameters.
    """

    q: str | None = Field(default=None, max_length=200, description="Search query")

    @property
    def has_query(self) -> bool:
        return bool(self.q and self.q.strip())

    @property
    def clean_query(self) -> str:
        return self.q.strip() if self.q else ""


@dataclass
class PaginatedResult(Generic[T]):
    """
    Paginated result container.

    Usage:
        result = PaginatedResult(
            items=users,
            total=100,
            page=1,
            page_size=20
        )
    """

    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size if self.page_size > 0 else 0

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def to_response(self) -> dict[str, Any]:
        """Convert to standard API response format"""
        return {
            "success": True,
            "data": self.items,
            "meta": {
                "page": self.page,
                "page_size": self.page_size,
                "total": self.total,
                "total_pages": self.total_pages,
                "has_next": self.has_next,
                "has_prev": self.has_prev,
            },
        }


class DateRangeParams(BaseModel):
    """
    Standard date range parameters.
    """

    start_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Start date (YYYY-MM-DD)",
    )
    end_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="End date (YYYY-MM-DD)",
    )

    @property
    def has_range(self) -> bool:
        return bool(self.start_date and self.end_date)


class FilterParams(BaseModel):
    """
    Combined filter parameters for common list queries.
    """

    # Pagination
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    # Sorting
    sort_by: str | None = None
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")

    # Search
    q: str | None = Field(default=None, max_length=200)

    # Date range
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    # Status filter
    status: str | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def apply_pagination(query: Any, params: PaginationParams) -> Any:
    """
    Apply pagination to a Supabase query.

    Usage:
        query = supabase.table("users").select("*")
        query = apply_pagination(query, pagination)
    """
    # Supabase uses range() for pagination
    start = params.offset
    end = start + params.page_size - 1
    return query.range(start, end)


def apply_sorting(query: Any, params: SortParams, allowed_fields: list[str]) -> Any:
    """
    Apply sorting to a Supabase query with field validation.

    Args:
        query: Supabase query builder
        params: Sort parameters
        allowed_fields: List of field names that are allowed for sorting
    """
    if params.sort_by and params.sort_by in allowed_fields:
        ascending = params.sort_order == "asc"
        return query.order(params.sort_by, desc=not ascending)
    return query
