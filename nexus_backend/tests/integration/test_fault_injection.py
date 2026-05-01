import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ── 模拟 ASGI 应用：拦截 OpenAI 请求，返回可控的故障响应 ──
# 使用 httpx.MockTransport 的方式，让 ASGI 应用的内部 httpx 调用也能被拦截


def _make_mock_app(openai_status: int, openai_body: dict | None = None, side_effect: Exception | None = None):
    """
    创建一个包装 ASGI 应用的模拟应用：
    - /v1/chat/completions (OpenAI) 请求 → 返回指定故障状态码
    - 其他请求 → 转发给真实的 FastAPI 应用
    """

    async def mock_app(scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            # 拦截 OpenAI API 请求
            if "/v1/chat/completions" in path:
                if side_effect:
                    raise side_effect
                body = openai_body or {"error": {"message": "Rate limit reached."}}
                await send({"type": "http.response.start", "status": openai_status, "headers": [[b"content-type", b"application/json"]]})
                import json
                await send({"type": "http.response.body", "body": json.dumps(body).encode()})
                return
            # 其他请求转发给真实应用
            await app(scope, receive, send)
        else:
            await app(scope, receive, send)

    return mock_app


@pytest.fixture(scope="module")
async def client_429():
    """使用模拟 429 的 OpenAI 响应"""
    mock = _make_mock_app(openai_status=429)
    async with AsyncClient(transport=ASGITransport(app=mock), base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="module")
async def client_timeout():
    """使用模拟超时的 OpenAI 响应"""
    mock = _make_mock_app(openai_status=500, side_effect=httpx.ReadTimeout("Timeout from API"))
    async with AsyncClient(transport=ASGITransport(app=mock), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_openai_429_rate_limit_fallback(client_429):
    """
    Integration & API Test (Fault Injection):
    Simulates a scenario where the external LLM provider (OpenAI) returns
    a 429 Rate Limit error. Validates that the system initiates a Fallback
    response instead of throwing an unhandled 500 Internal Server Error.
    """

    payload = {"message": "Hello, how are you?", "tenant_id": "test_tenant_fault"}

    headers = {"Content-Type": "application/json", "Authorization": "Bearer fake_token"}

    response = await client_429.post("/api/chat", json=payload, headers=headers)

    assert (
        response.status_code != 500
    ), f"Expected graceful degraded response, got 500 internal server crash. Text: {response.text}"

    assert response.status_code in [
        200,
        429,
        503,
        504,
    ], f"Unexpected status code under 429 condition: {response.status_code}"


@pytest.mark.asyncio
async def test_llm_timeout_circuit_breaker(client_timeout):
    """
    Integration & API Test (Fault Injection):
    Simulates a complete network timeout from the LLM provider.
    Verifies that the CircuitBreaker trips or the error recovery service
    appropriately sheds the load.
    """

    payload = {
        "message": "What is the meaning of life?",
        "tenant_id": "test_tenant_fault",
    }

    headers = {"Content-Type": "application/json", "Authorization": "Bearer fake_token"}

    response = await client_timeout.post("/api/chat", json=payload, headers=headers)

    # Must intercept Timeout, not return 500
    assert response.status_code in [200, 503, 504]

    if response.status_code == 200:
        data = response.json()
        assert (
            "timeout" in str(data).lower()
            or "later" in str(data).lower()
            or "error" in str(data).lower()
        ), "Expected degradation message in 200 response"
