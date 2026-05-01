import httpx
import pytest
import respx
from unittest.mock import AsyncMock, MagicMock

from app.core.auth import get_current_user_id
from app.core.security_middleware import TenantContextMiddleware
from app.main import app


def _mock_db_client():
    """返回模拟的 Supabase 客户端，支持链式调用"""
    mock_user_response = MagicMock()
    mock_user_response.data = {
        "id": "test-user-123",
        "role": "admin",
        "organization_id": "org-456",
    }
    mock_user_response.error = None

    mock_builder = MagicMock()
    mock_builder.select.return_value = mock_builder
    mock_builder.eq.return_value = mock_builder
    mock_builder.maybe_single.return_value = mock_builder
    mock_builder.execute = AsyncMock(return_value=mock_user_response)

    mock_db = MagicMock()
    mock_db.table.return_value = mock_builder
    mock_db.get_scoped_client = MagicMock(return_value=mock_db)
    mock_db.get_org_filtered_client = MagicMock(return_value=mock_db)
    return mock_db


@pytest.fixture(scope="module")
def client():
    """创建测试客户端，绕过认证和数据库依赖。

    关键: Starlette 的 BaseHTTPMiddleware 在 __init__ 时将原始 dispatch
    捕获为 self.dispatch_func。修改类属性不会影响已有实例。
    必须: 1) 修改类属性, 2) 将 app.middleware_stack 置空,
    3) 使新请求触发 rebuild — 新实例会使用修改后的 dispatch。
    """
    mock_db = _mock_db_client()

    # 1. 覆盖 FastAPI 依赖注入
    async def _override_auth():
        return "test-user-123"

    app.dependency_overrides[get_current_user_id] = _override_auth

    # 2. Patch class-level dispatch
    _original_dispatch = TenantContextMiddleware.dispatch

    async def _mocked_dispatch(self_mw, request, call_next):
        request.state.user_id = "test-user-123"
        request.state.org_id = "org-456"
        request.state.db = mock_db
        request.state.auth_failed = False
        return await call_next(request)

    TenantContextMiddleware.dispatch = _mocked_dispatch

    # 3. Force middleware stack rebuild so new instances pick up the patched dispatch
    app.middleware_stack = None

    try:
        from fastapi.testclient import TestClient

        c = TestClient(app)
    except TypeError:
        from httpx import ASGITransport, AsyncClient
        import asyncio

        class _SyncAsyncBridge:
            def __init__(self):
                self._client = None

            def _ensure(self):
                if self._client is None:
                    loop = asyncio.new_event_loop()
                    self._client = loop.run_until_complete(
                        AsyncClient(
                            transport=ASGITransport(app=app), base_url="http://test"
                        ).__aenter__()
                    )
                    self._loop = loop

            def post(self, *args, **kwargs):
                self._ensure()
                return self._loop.run_until_complete(self._client.post(*args, **kwargs))

        c = _SyncAsyncBridge()

    yield c

    # Restore original state
    TenantContextMiddleware.dispatch = _original_dispatch
    app.middleware_stack = None
    app.dependency_overrides.clear()


@pytest.mark.security
@respx.mock
def test_openai_429_rate_limit_fallback(client):
    """
    Integration & API Test (Fault Injection):
    Simulates a scenario where the external LLM provider (OpenAI) returns
    a 429 Rate Limit error. Validates that the system initiates a Fallback
    response instead of throwing an unhandled 500 Internal Server Error.
    """

    # Mocking OpenAI Chat Completions API
    openai_route = respx.post("https://api.openai.com/v1/chat/completions")

    # Force 429 Too Many Requests
    openai_route.mock(
        return_value=httpx.Response(
            429, json={"error": {"message": "Rate limit reached."}}
        )
    )

    payload = {"messages": [{"role": "user", "content": "Hello, how are you?"}]}

    headers = {"Content-Type": "application/json", "Authorization": "Bearer fake_token"}

    response = client.post("/api/chat", json=payload, headers=headers)

    # 系统不应崩溃（500），应返回优雅降级响应
    assert (
        response.status_code != 500
    ), f"Expected graceful degraded response, got 500 internal server crash. Text: {response.text}"

    assert response.status_code in [
        200,
        429,
        503,
        504,
    ], f"Unexpected status code under 429 condition: {response.status_code}"


@pytest.mark.security
@respx.mock
def test_llm_timeout_circuit_breaker(client):
    """
    Integration & API Test (Fault Injection):
    Simulates a complete network timeout from the LLM provider.
    Verifies that the CircuitBreaker trips or the error recovery service
    appropriately sheds the load.
    """
    # Mocking OpenAI Chat Completions API
    openai_route = respx.post("https://api.openai.com/v1/chat/completions")

    # Force ReadTimeout
    openai_route.mock(side_effect=httpx.ReadTimeout("Timeout from API"))

    payload = {
        "messages": [{"role": "user", "content": "What is the meaning of life?"}],
    }

    headers = {"Content-Type": "application/json", "Authorization": "Bearer fake_token"}

    response = client.post("/api/chat", json=payload, headers=headers)

    # Must intercept Timeout, not return 500
    assert response.status_code in [200, 429, 503, 504]

    if response.status_code == 200:
        body = response.text.lower()
        assert (
            "timeout" in body
            or "later" in body
            or "error" in body
            or "quota" in body
            or "exhausted" in body
        ), "Expected degradation message in 200 response"
