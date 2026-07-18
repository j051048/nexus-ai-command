"""测试基础设施"""

import os
import socket
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app as _fastapi_app


@pytest.fixture(autouse=True)
def block_unapproved_external_network(monkeypatch):
    """Fail fast when a test accidentally reaches a real external service.

    Staging and live-integration jobs must opt in with ALLOW_TEST_NETWORK=1.
    Loopback remains available for local subprocess and container tests.
    """
    if os.getenv("ALLOW_TEST_NETWORK") == "1":
        yield
        return

    original_getaddrinfo = socket.getaddrinfo
    allowed_hosts = {"localhost", "127.0.0.1", "::1", "test"}

    def guarded_getaddrinfo(host, *args, **kwargs):
        normalized = str(host or "").lower()
        if normalized in allowed_hosts:
            return original_getaddrinfo(host, *args, **kwargs)
        raise RuntimeError(
            f"Unexpected external network request in backend test: {host}. "
            "Mock the dependency or set ALLOW_TEST_NETWORK=1 for a staging job."
        )

    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    yield


@pytest.fixture(autouse=True)
def isolate_process_local_rate_limits(monkeypatch):
    """Keep rate limiting deterministic and event-loop local in tests."""
    from app.core import rate_limiter as rate_limiter_module
    from app.core.rate_limiter import reset_rate_limit_state

    monkeypatch.setattr(rate_limiter_module.settings, "ENV", "test")
    reset_rate_limit_state()
    yield
    reset_rate_limit_state()


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=_fastapi_app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def test_user():
    return {
        "user_id": "test-123",
        "org_id": "org-456",
        "tenant_id": "tenant-789",
        "id": "test-123",
        "role": "admin",
    }


class MockResponse:
    def __init__(
        self, data: Any = None, error: Any | None = None, count: int | None = None
    ):
        self.data = data if data is not None else []
        self.error = error
        self.count = (
            count if count is not None else (len(data) if isinstance(data, list) else 0)
        )


class MockQueryBuilder:
    def __init__(self, table: str, data: list | None = None):
        self.table_name = table
        self._data = data or []
        self._filters = []
        self._do_count = False
        self._is_single = False
        self._pending_update = None

    def select(self, *columns, **kwargs):
        if kwargs.get("count"):
            self._do_count = True
        return self

    def single(self):
        self._is_single = True
        return self

    def maybe_single(self):
        self._is_single = True
        return self

    def eq(self, column, value):
        # 简单的内存过滤逻辑
        if isinstance(self._data, list):
            self._data = [
                d for d in self._data if isinstance(d, dict) and d.get(column) == value
            ]
        return self

    def is_(self, column, value):
        # 处理 status is null 的情况
        if value == "null" and isinstance(self._data, list):
            self._data = [d for d in self._data if d.get(column) is None]
        return self

    def neq(self, column, value):
        if isinstance(self._data, list):
            self._data = [
                d for d in self._data if isinstance(d, dict) and d.get(column) != value
            ]
        return self

    def ilike(self, column, value):
        if isinstance(self._data, list):
            pattern = value.strip("%").lower()
            self._data = [
                d
                for d in self._data
                if isinstance(d, dict) and pattern in str(d.get(column, "")).lower()
            ]
        return self

    def order(self, column, desc=False):
        return self

    def limit(self, count):
        if isinstance(self._data, list):
            self._data = self._data[:count]
        return self

    def insert(self, data):
        # 模拟真实 Supabase 行为：插入时自动生成 id（如果未提供）
        import uuid

        if isinstance(data, dict) and "id" not in data:
            data = {**data, "id": str(uuid.uuid4())}
        self._data = [data]
        return self

    def update(self, data):
        self._pending_update = data
        return self

    def delete(self):
        self._data = []
        return self

    async def execute(self):
        # Apply deferred update after filters have run (matches real Supabase
        # behavior: WHERE filters first, then UPDATE applies to matched rows)
        if self._pending_update is not None:
            for d in self._data:
                d.update(self._pending_update)
        count = len(self._data) if self._do_count else None
        data = self._data
        if self._is_single:
            data = data[0] if data else None
        print(
            f"DEBUG: table={self.table_name} is_single={self._is_single} data_type={type(data)}"
        )
        return MockResponse(data=data, count=count)


class MockRpcBuilder:
    """Mock RPC 调用构建器"""

    def __init__(self, result: Any = None):
        self._result = result

    async def execute(self):
        return MockResponse(data=self._result)


class MockSupabaseClient:
    def __init__(self):
        self.tables = {}
        self._rpc_results: dict[str, Any] = {}

    def set_table_data(self, table_name: str, data: list):
        self.tables[table_name] = data

    def set_rpc_result(self, func_name: str, result: Any):
        self._rpc_results[func_name] = result

    def table(self, table_name: str):
        data = self.tables.get(table_name, [])
        return MockQueryBuilder(table_name, data)

    def rpc(self, func_name: str, params: dict | None = None):
        result = self._rpc_results.get(func_name, [])
        return MockRpcBuilder(result)


@pytest.fixture
def mock_db():
    return MockSupabaseClient()


# ── 缺失 fixture 补充 ──


@pytest.fixture
def mock_agent_config():
    """被 test_agent_flow 等使用"""
    from app.agent.state import AgentConfig

    return AgentConfig(
        user_id="test-123",
        session_id="sess-1",
        agent_name="test_agent",
        org_id="org-456",
        token="fake-token",
        user_role="admin",
    )


@pytest.fixture
async def async_client():
    """被 test_api_smoke, test_billing, test_payments 等使用"""
    async with AsyncClient(
        transport=ASGITransport(app=_fastapi_app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def app():
    """被 test_projects_permissions, test_competitors_permissions 等使用"""
    return _fastapi_app
