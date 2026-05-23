"""Tests for dashboard router — boss-level analytics endpoint."""

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


@dataclass
class _Resp:
    data: Any = None
    count: int | None = None


class _SingleBuilder:
    """Mock query builder where single() makes execute() return a dict (not list)."""

    def __init__(self, data=None, count=None):
        self._data = data if data is not None else []
        self._count = count
        self._is_single = False

    def select(self, *a, **kw):
        return self

    def eq(self, *a, **kw):
        return self

    def gt(self, *a, **kw):
        return self

    def order(self, *a, **kw):
        return self

    def limit(self, *a, **kw):
        return self

    def single(self):
        self._is_single = True
        return self

    async def execute(self):
        if self._is_single and isinstance(self._data, list) and self._data:
            return _Resp(data=self._data[0], count=self._count)
        return _Resp(data=self._data, count=self._count)


class _DashboardMockClient:
    """Mock client with per-table data for dashboard tests.

    Each table() call returns a fresh builder to avoid shared state
    when the same table is queried multiple times (e.g. users for role + top performers).
    """

    def __init__(self):
        self._table_configs: dict[str, tuple[list, int | None]] = {}

    def table(self, name: str) -> _SingleBuilder:
        data, count = self._table_configs.get(name, ([], None))
        return _SingleBuilder(list(data), count)

    def set_table(self, name: str, data: list, count: int | None = None):
        self._table_configs[name] = (data, count)


class TestBossDashboard:

    @pytest.mark.asyncio
    async def test_boss_dashboard_returns_data(self):
        """Boss can access dashboard with pending approvals, expenses, and top performers."""
        from app.routers.dashboard import boss_dashboard

        client = _DashboardMockClient()
        client.set_table(
            "users",
            [{"role": "boss", "name": "Alice", "score": 100, "total_bonus": 5000}],
        )
        client.set_table("approval_requests", [], count=3)

        request = MagicMock()
        request.state.db = client

        result = await boss_dashboard(request=request, user_id="test-user-123")
        assert result["success"] is True
        assert result["data"]["pending_approvals"] == 3
        assert "abnormal_expenses" in result["data"]
        assert "top_performers" in result["data"]
        assert result["data"]["system_status"] == "Healthy"

    @pytest.mark.asyncio
    async def test_non_boss_rejected(self):
        """Non-boss users are rejected with permission denied (403)."""
        from app.routers.dashboard import boss_dashboard

        client = _DashboardMockClient()
        client.set_table("users", [{"role": "employee"}])

        request = MagicMock()
        request.state.db = client

        with pytest.raises(HTTPException) as exc_info:
            await boss_dashboard(request=request, user_id="test-user-123")
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_no_db_connection(self):
        """Rejects when tenant DB context is missing."""
        from app.routers.dashboard import boss_dashboard

        request = MagicMock()
        request.state.db = None
        request.state.auth_failed = True

        with pytest.raises(HTTPException) as exc_info:
            await boss_dashboard(request=request, user_id="test-user-123")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_boss_with_zero_approvals(self):
        """Boss dashboard works with zero pending approvals."""
        from app.routers.dashboard import boss_dashboard

        client = _DashboardMockClient()
        client.set_table(
            "users", [{"role": "boss", "name": "Bob", "score": 50, "total_bonus": 1000}]
        )
        client.set_table("approval_requests", [], count=0)

        request = MagicMock()
        request.state.db = client

        result = await boss_dashboard(request=request, user_id="test-user-123")
        assert result["success"] is True
        assert result["data"]["pending_approvals"] == 0
