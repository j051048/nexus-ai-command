import httpx
import pytest
import respx

from app.main import app


def _make_client():
    """创建测试客户端，兼容 httpx 0.28+（app 参数已移除）"""
    try:
        from fastapi.testclient import TestClient
        return TestClient(app)
    except TypeError:
        # httpx 0.28+: TestClient(app) 不再接受 app 参数
        # 使用 AsyncClient + ASGITransport（同步桥接）
        from httpx import ASGITransport, AsyncClient
        import asyncio

        class _SyncAsyncBridge:
            """将 AsyncClient 包装为同步接口"""
            def __init__(self):
                self._client = None

            def _ensure(self):
                if self._client is None:
                    loop = asyncio.new_event_loop()
                    self._client = loop.run_until_complete(
                        AsyncClient(transport=ASGITransport(app=app), base_url="http://test").__aenter__()
                    )
                    self._loop = loop

            def post(self, *args, **kwargs):
                self._ensure()
                return self._loop.run_until_complete(self._client.post(*args, **kwargs))

        return _SyncAsyncBridge()


@pytest.fixture(scope="module")
def client():
    return _make_client()


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

    payload = {"message": "Hello, how are you?", "tenant_id": "test_tenant_fault"}

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
        "message": "What is the meaning of life?",
        "tenant_id": "test_tenant_fault",
    }

    headers = {"Content-Type": "application/json", "Authorization": "Bearer fake_token"}

    response = client.post("/api/chat", json=payload, headers=headers)

    # Must intercept Timeout, not return 500
    assert response.status_code in [200, 429, 503, 504]

    if response.status_code == 200:
        data = response.json()
        assert (
            "timeout" in str(data).lower()
            or "later" in str(data).lower()
            or "error" in str(data).lower()
        ), "Expected degradation message in 200 response"
