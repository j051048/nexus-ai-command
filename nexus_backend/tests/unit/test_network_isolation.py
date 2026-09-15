import socket

import httpcore
import httpx
import pytest


def test_external_network_is_blocked_by_default() -> None:
    with pytest.raises(RuntimeError, match="Unexpected external network request"):
        socket.getaddrinfo("unexpected-test-network.invalid", 443)


@pytest.mark.parametrize("host", ["unexpected-test-network.invalid", "198.51.100.1"])
def test_http_transport_is_blocked_before_connecting(monkeypatch, host) -> None:
    def unexpected_pool_request(*args, **kwargs):
        raise AssertionError("External request reached the connection pool")

    monkeypatch.setattr(httpcore.ConnectionPool, "handle_request", unexpected_pool_request)
    with httpx.Client(trust_env=False) as client:
        with pytest.raises(RuntimeError, match="Unexpected external network request"):
            client.get(f"https://{host}/")


@pytest.mark.parametrize("host", ["unexpected-test-network.invalid", "198.51.100.1"])
async def test_async_http_transport_is_blocked_before_connecting(monkeypatch, host):
    async def unexpected_pool_request(*args, **kwargs):
        raise AssertionError("External request reached the connection pool")

    monkeypatch.setattr(
        httpcore.AsyncConnectionPool, "handle_async_request", unexpected_pool_request
    )
    async with httpx.AsyncClient(trust_env=False) as client:
        with pytest.raises(RuntimeError, match="Unexpected external network request"):
            await client.get(f"https://{host}/")


async def test_explicit_mock_transport_remains_available():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        response = await client.get("https://mocked-test-network.invalid/")
    assert response.json() == {"ok": True}
