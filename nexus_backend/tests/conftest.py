"""Shared test fixtures for nexus_backend tests."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
from typing import Any, List, Optional, Dict


# ──────────────────────────────────────────────────────────────────────────────
# Mock Supabase Client
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class MockResponse:
    """Simulates Supabase query response."""
    data: Any = None
    count: Optional[int] = None


class MockQueryBuilder:
    """Chainable mock for Supabase query builder pattern.

    Usage:
        builder = MockQueryBuilder(data=[{"id": "1", "name": "test"}])
        result = await builder.select("*").eq("id", "1").execute()
        assert result.data == [{"id": "1", "name": "test"}]
    """

    def __init__(self, data=None, count=None):
        self._data = data if data is not None else []
        self._count = count

    # ── Chainable methods ──
    def select(self, *args, **kwargs):
        return self

    def insert(self, data, **kwargs):
        if isinstance(data, list):
            self._data = data
        else:
            self._data = [data]
        return self

    def update(self, data, **kwargs):
        return self

    def delete(self, **kwargs):
        return self

    def upsert(self, data, **kwargs):
        if isinstance(data, list):
            self._data = data
        else:
            self._data = [data]
        return self

    def eq(self, *args, **kwargs):
        return self

    def neq(self, *args, **kwargs):
        return self

    def gt(self, *args, **kwargs):
        return self

    def gte(self, *args, **kwargs):
        return self

    def lt(self, *args, **kwargs):
        return self

    def lte(self, *args, **kwargs):
        return self

    def ilike(self, *args, **kwargs):
        return self

    def in_(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def range(self, *args, **kwargs):
        return self

    def single(self):
        return self

    def maybe_single(self):
        return self

    async def execute(self):
        return MockResponse(data=self._data, count=self._count)


class MockSupabaseClient:
    """Mock Supabase client matching the real interface."""

    def __init__(self, default_data=None):
        self._default_data = default_data if default_data is not None else []
        self._tables: Dict[str, MockQueryBuilder] = {}
        self._rpc_results: Dict[str, Any] = {}

    def table(self, name: str) -> MockQueryBuilder:
        if name in self._tables:
            return self._tables[name]
        return MockQueryBuilder(self._default_data)

    def rpc(self, name: str, params: dict = None) -> MockQueryBuilder:
        data = self._rpc_results.get(name, [])
        return MockQueryBuilder(data)

    def get_scoped_client(self, token: str):
        return self

    # ── Test helpers ──
    def set_table_data(self, name: str, data: list, count=None):
        """Pre-configure data for a specific table."""
        self._tables[name] = MockQueryBuilder(data, count)

    def set_rpc_result(self, name: str, data: Any):
        """Pre-configure result for an RPC call."""
        self._rpc_results[name] = data


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_supabase():
    """Provides a MockSupabaseClient instance."""
    return MockSupabaseClient()


@pytest.fixture
def mock_request(mock_supabase):
    """Mock FastAPI Request with request.state attributes."""
    request = MagicMock()
    request.state.db = mock_supabase
    request.state.user_id = "test-user-123"
    request.state.org_id = "test-org-456"
    request.state.request_id = "req-test-789"
    request.headers = {
        "authorization": "Bearer test-token",
        "x-request-id": "req-test-789",
        "user-agent": "pytest/1.0",
    }
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.url = MagicMock()
    request.url.path = "/api/test"
    request.method = "GET"
    return request


@pytest.fixture
def user_id():
    return "test-user-123"


@pytest.fixture
def org_id():
    return "test-org-456"


@pytest.fixture
def sample_messages():
    """Sample chat messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, what is 2+2?"},
        {"role": "assistant", "content": "2+2 equals 4."},
    ]
