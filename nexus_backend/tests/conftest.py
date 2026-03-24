"""
Shared test fixtures for nexus_backend tests.

提供所有测试文件共享的 mock 对象和 fixture:
- MockSupabaseClient: 模拟 Supabase 数据库客户端
- MockQueryBuilder: 支持链式调用的查询构造器
- mock_agent_config: 测试用 AgentConfig
- async_client: httpx AsyncClient 用于 FastAPI 端点测试
"""

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Mock Supabase Client
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class MockResponse:
    """Simulates Supabase query response."""

    data: Any = None
    count: int | None = None


class MockQueryBuilder:
    """Chainable mock for Supabase query builder pattern.

    Usage:
        builder = MockQueryBuilder(data=[{"id": "1", "name": "test"}])
        result = await builder.select("*").eq("id", "1").execute()
        assert result.data == [{"id": "1", "name": "test"}]

    NOTE: 每次链式调用返回新的 MockQueryBuilder 副本以避免状态污染。
    """

    def __init__(self, data=None, count=None, _single=False, _maybe_single=False):
        self._data = data if data is not None else []
        self._count = count
        self._single = _single
        self._maybe_single = _maybe_single

    def _clone(self, **overrides):
        """创建当前 builder 的浅拷贝, 可覆盖属性"""
        kwargs = {
            "data": self._data,
            "count": self._count,
            "_single": self._single,
            "_maybe_single": self._maybe_single,
        }
        kwargs.update(overrides)
        return MockQueryBuilder(**kwargs)

    # ── Chainable methods ──
    def select(self, *args, **kwargs):
        return self._clone()

    def insert(self, data, **kwargs):
        # Auto-generate 'id' for inserted records if missing (mimics Supabase RETURNING *)
        import uuid as _uuid
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "id" not in item:
                    item["id"] = str(_uuid.uuid4())[:8]
            return self._clone(data=data)
        else:
            if isinstance(data, dict) and "id" not in data:
                data["id"] = str(_uuid.uuid4())[:8]
            return self._clone(data=[data])

    def update(self, data, **kwargs):
        return self._clone()

    def delete(self, **kwargs):
        return self._clone()

    def upsert(self, data, **kwargs):
        if isinstance(data, list):
            return self._clone(data=data)
        else:
            return self._clone(data=[data])

    def eq(self, *args, **kwargs):
        return self._clone()

    def neq(self, *args, **kwargs):
        return self._clone()

    def gt(self, *args, **kwargs):
        return self._clone()

    def gte(self, *args, **kwargs):
        return self._clone()

    def lt(self, *args, **kwargs):
        return self._clone()

    def lte(self, *args, **kwargs):
        return self._clone()

    def ilike(self, *args, **kwargs):
        return self._clone()

    def in_(self, *args, **kwargs):
        return self._clone()

    def contains(self, *args, **kwargs):
        return self._clone()

    def order(self, *args, **kwargs):
        return self._clone()

    def limit(self, *args, **kwargs):
        return self._clone()

    def range(self, *args, **kwargs):
        return self._clone()

    def single(self):
        return self._clone(_single=True)

    def maybe_single(self):
        return self._clone(_maybe_single=True)

    async def execute(self):
        data = self._data
        # maybe_single / single 应返回单条记录而非列表
        if self._maybe_single or self._single:
            if isinstance(data, list):
                data = data[0] if data else None
        return MockResponse(data=data, count=self._count)


class MockSupabaseClient:
    """Mock Supabase client matching the real interface."""

    def __init__(self, default_data=None):
        self._default_data = default_data if default_data is not None else []
        self._tables: dict[str, MockQueryBuilder] = {}
        self._rpc_results: dict[str, Any] = {}

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
    """提供 MockSupabaseClient 实例"""
    return MockSupabaseClient()


@pytest.fixture
def mock_request(mock_supabase):
    """模拟 FastAPI Request, 包含 request.state 属性"""
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
def mock_user_id():
    """测试用用户 UUID"""
    return "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def org_id():
    return "test-org-456"


@pytest.fixture
def mock_org_id():
    """测试用组织 UUID"""
    return "660e8400-e29b-41d4-a716-446655440001"


@pytest.fixture
def sample_messages():
    """Sample chat messages for testing."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, what is 2+2?"},
        {"role": "assistant", "content": "2+2 equals 4."},
    ]


@pytest.fixture
def mock_agent_config():
    """提供测试用 AgentConfig 实例"""
    from app.agent.state import AgentConfig

    return AgentConfig(
        user_id="550e8400-e29b-41d4-a716-446655440000",
        session_id="test-session-001",
        agent_name="test-agent",
        api_key="sk-test-key-fake-000000000000000000000000",
        base_url="https://api.test.com/v1",
        model="gpt-4o",
        mini_model="gpt-4o-mini",
        system_confirmed=False,
        org_id="660e8400-e29b-41d4-a716-446655440001",
        user_role="employee",
        max_iterations=5,
        temperature=0.5,
        reflect_use_llm=False,  # 测试时禁用 LLM 反思以避免外部调用
        tool_timeout=10,
        gather_timeout=30,
    )


@pytest.fixture
async def async_client():
    """
    提供 httpx AsyncClient 用于 FastAPI 端点测试。
    通过替换 lifespan 避免启动时的 Redis/DB/Checkpointer 初始化。
    """
    import httpx
    from contextlib import asynccontextmanager
    from unittest.mock import patch

    # 替换 lifespan 为空操作, 避免初始化真实的 Redis/DB/Checkpointer
    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    from app.main import app

    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        app.router.lifespan_context = original_lifespan
