"""
Base Repository - Unified Database Access Layer

Provides a generic repository base class that wraps Supabase table operations
with automatic tenant_id filtering, pagination, and soft-delete support.

Usage:
    from app.repositories.base_repository import BaseRepository

    class ProjectRepository(BaseRepository):
        def __init__(self):
            super().__init__(table_name="projects")

    project_repo = ProjectRepository()

    # CRUD with automatic tenant isolation
    await project_repo.get_by_id("proj-123", tenant_id="org-1")
    await project_repo.list(tenant_id="org-1", page=1, page_size=20)
    await project_repo.create(tenant_id="org-1", data={...})
    await project_repo.update("proj-123", tenant_id="org-1", data={...})
    await project_repo.delete("proj-123", tenant_id="org-1")
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BaseRepository:
    """
    Generic repository base class for Supabase table operations.

    Features:
    - Automatic tenant_id filtering on all queries (multi-tenant isolation)
    - Pagination support (page/page_size)
    - Soft-delete support (is_deleted flag)
    - Flexible filtering via operator-based filter dicts
    - Consistent error handling and logging
    """

    def __init__(
        self,
        table_name: str,
        *,
        tenant_column: str = "tenant_id",
        soft_delete: bool = True,
        id_column: str = "id",
    ):
        """
        Args:
            table_name: Supabase table name
            tenant_column: Column name for tenant isolation (set to "" to disable)
            soft_delete: If True, filters out is_deleted=True by default
            id_column: Primary key column name
        """
        self.table_name = table_name
        self.tenant_column = tenant_column
        self.soft_delete = soft_delete
        self.id_column = id_column

    def _get_client(self):
        """Lazy-load the Supabase client to avoid circular imports."""
        from app.core.database import supabase

        if not supabase:
            raise RuntimeError(f"Supabase client unavailable for table '{self.table_name}'")
        return supabase

    def _apply_tenant_filter(self, query, tenant_id: str | None):
        """Apply tenant_id filter if configured and provided."""
        if self.tenant_column and tenant_id:
            query = query.eq(self.tenant_column, tenant_id)
        return query

    def _apply_soft_delete_filter(self, query):
        """Exclude soft-deleted records if enabled."""
        if self.soft_delete:
            query = query.eq("is_deleted", False)
        return query

    def _apply_filters(self, query, filters: dict[str, Any] | None):
        """
        Apply arbitrary filters to a query.

        Filter values can be:
        - Simple values: {"status": "active"} -> .eq("status", "active")
        - Operator tuples: {"amount": ("gte", 100)} -> .gte("amount", 100)
        - List values: {"status": ("in_", ["a", "b"])} -> .in_("status", ["a", "b"])

        Supported operators: eq, neq, gt, gte, lt, lte, in_, like, ilike, is_
        """
        if not filters:
            return query

        for key, value in filters.items():
            if isinstance(value, tuple) and len(value) == 2:
                op, val = value
                op_method = getattr(query, op, None)
                if op_method:
                    query = op_method(key, val)
                else:
                    logger.warning(f"Unknown filter operator: {op}")
                    query = query.eq(key, val)
            else:
                query = query.eq(key, value)

        return query

    # ------------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------------

    async def get_by_id(
        self,
        record_id: str,
        *,
        tenant_id: str | None = None,
        columns: str = "*",
    ) -> dict[str, Any] | None:
        """
        Retrieve a single record by ID.

        Returns None if not found or soft-deleted.
        """
        client = self._get_client()

        try:
            query = client.table(self.table_name).select(columns).eq(self.id_column, record_id)
            query = self._apply_tenant_filter(query, tenant_id)
            query = self._apply_soft_delete_filter(query)

            result = await query.maybe_single().execute()
            return result.data if result else None

        except Exception as e:
            logger.error(f"[{self.table_name}] get_by_id({record_id}) failed: {e}")
            return None

    async def list(
        self,
        *,
        tenant_id: str | None = None,
        filters: dict[str, Any] | None = None,
        columns: str = "*",
        order_by: str | None = None,
        order_desc: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Retrieve a paginated list of records.

        Args:
            tenant_id: Tenant ID for isolation
            filters: Dict of column -> value or column -> (operator, value)
            columns: Columns to select (default: all)
            order_by: Column to sort by
            order_desc: Sort descending (default: True)
            page: Page number (1-based)
            page_size: Records per page (max 100)
        """
        client = self._get_client()
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size

        try:
            query = client.table(self.table_name).select(columns)
            query = self._apply_tenant_filter(query, tenant_id)
            query = self._apply_soft_delete_filter(query)
            query = self._apply_filters(query, filters)

            if order_by:
                query = query.order(order_by, desc=order_desc)

            query = query.range(offset, offset + page_size - 1)
            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"[{self.table_name}] list() failed: {e}")
            return []

    async def count(
        self,
        *,
        tenant_id: str | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """Count records matching the given filters."""
        client = self._get_client()

        try:
            query = client.table(self.table_name).select("*", count="exact")
            query = self._apply_tenant_filter(query, tenant_id)
            query = self._apply_soft_delete_filter(query)
            query = self._apply_filters(query, filters)

            result = await query.limit(0).execute()
            return result.count or 0

        except Exception as e:
            logger.error(f"[{self.table_name}] count() failed: {e}")
            return 0

    async def create(
        self,
        data: dict[str, Any],
        *,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a new record.

        Automatically injects tenant_id if configured.
        Returns the created record.
        """
        client = self._get_client()

        # Inject tenant_id
        if self.tenant_column and tenant_id:
            data = {**data, self.tenant_column: tenant_id}

        try:
            result = await client.table(self.table_name).insert(data).execute()
            if not result.data:
                raise RuntimeError(f"Insert into {self.table_name} returned no data")
            return result.data[0]

        except Exception as e:
            logger.error(f"[{self.table_name}] create() failed: {e}")
            raise

    async def create_many(
        self,
        records: list[dict[str, Any]],
        *,
        tenant_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Batch create multiple records."""
        client = self._get_client()

        if self.tenant_column and tenant_id:
            records = [{**r, self.tenant_column: tenant_id} for r in records]

        try:
            result = await client.table(self.table_name).insert(records).execute()
            return result.data or []

        except Exception as e:
            logger.error(f"[{self.table_name}] create_many({len(records)} records) failed: {e}")
            raise

    async def update(
        self,
        record_id: str,
        data: dict[str, Any],
        *,
        tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Update a record by ID.

        Returns the updated record, or None if not found.
        Tenant isolation is enforced if configured.
        """
        client = self._get_client()

        try:
            query = (
                client.table(self.table_name)
                .update(data)
                .eq(self.id_column, record_id)
            )
            query = self._apply_tenant_filter(query, tenant_id)

            result = await query.execute()
            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"[{self.table_name}] update({record_id}) failed: {e}")
            raise

    async def delete(
        self,
        record_id: str,
        *,
        tenant_id: str | None = None,
        hard: bool = False,
    ) -> bool:
        """
        Delete a record.

        By default performs a soft delete (sets is_deleted=True).
        Pass hard=True for permanent deletion.

        Returns True if a record was affected.
        """
        client = self._get_client()

        try:
            if hard or not self.soft_delete:
                query = (
                    client.table(self.table_name)
                    .delete()
                    .eq(self.id_column, record_id)
                )
            else:
                query = (
                    client.table(self.table_name)
                    .update({"is_deleted": True})
                    .eq(self.id_column, record_id)
                )

            query = self._apply_tenant_filter(query, tenant_id)
            result = await query.execute()
            return bool(result.data)

        except Exception as e:
            logger.error(f"[{self.table_name}] delete({record_id}) failed: {e}")
            raise

    async def upsert(
        self,
        data: dict[str, Any],
        *,
        tenant_id: str | None = None,
        on_conflict: str | None = None,
    ) -> dict[str, Any]:
        """
        Insert or update a record.

        Args:
            data: Record data (must include the primary key for upsert)
            tenant_id: Tenant ID for isolation
            on_conflict: Conflict resolution column(s)
        """
        client = self._get_client()

        if self.tenant_column and tenant_id:
            data = {**data, self.tenant_column: tenant_id}

        try:
            query = client.table(self.table_name).upsert(data)
            if on_conflict:
                query = query.on_conflict(on_conflict)

            result = await query.execute()
            return result.data[0] if result.data else data

        except Exception as e:
            logger.error(f"[{self.table_name}] upsert() failed: {e}")
            raise
