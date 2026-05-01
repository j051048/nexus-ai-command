import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.asyncio
@respx.mock
async def test_openai_429_rate_limit_fallback(client):
    """
    Integration & API Test (Fault Injection):
    Simulates a scenario where the external LLM provider (OpenAI) returns
    a 429 Rate Limit error. Validates that the system initiates a Fallback
    response (e.g. informing the user to try again later or using a generic response)
    instead of throwing an unhandled 500 Internal Server Error.
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

    # Our backend should intercept the 429 via ErrorRecoveryService / CircuitBreaker
    # and return a 503 or 429 or a graceful 200 with fallback text.
    # It MUST NOT be a 500 error.
    response = client.post("/api/v1/ai/assistant", json=payload, headers=headers)

    assert (
        response.status_code != 500
    ), f"Expected graceful degraded response, got 500 internal server crash. Text: {response.text}"

    # Depending on our specific fallback implementation:
    # 1. We might mask it to 503 Service Unavailable / 429
    # 2. Or we return 200 with a "Service is busy, please try again" fallback payload
    assert response.status_code in [
        200,
        429,
        503,
        504,
    ], f"Unexpected status code under 429 condition: {response.status_code}"

    # Verify the external API was actually called and mocked
    assert openai_route.called


@pytest.mark.asyncio
@respx.mock
async def test_llm_timeout_circuit_breaker(client):
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

    response = client.post("/api/v1/ai/assistant", json=payload, headers=headers)

    # Must intercept Timeout, not return 500
    assert response.status_code in [200, 503, 504]

    if response.status_code == 200:
        data = response.json()
        assert (
            "timeout" in str(data).lower()
            or "later" in str(data).lower()
            or "error" in str(data).lower()
        ), "Expected degradation message in 200 response"

    assert openai_route.called
