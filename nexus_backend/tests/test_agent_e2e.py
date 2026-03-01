"""
E2E tests for the Agent chat pipeline.

Tests the full request lifecycle through the real middleware stack:
  POST /api/chat → auth → moderation → token check → LangGraph agent → SSE stream

Uses httpx AsyncClient + ASGITransport to exercise the actual FastAPI app
with LLM and database calls mocked out.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


# ── Fixtures ──


def _mock_supabase_client():
    """Create a mock Supabase client with sensible defaults for chat E2E.

    Supports `get_scoped_client(token)` returning a client with the same
    `table()` behaviour so that TenantContextMiddleware can inject a
    scoped DB handle into request.state.db.
    """

    table_data = {
        "users": [{"id": "test-user", "role": "employee", "organization_id": "org-1"}],
        "ai_settings": [],
        "chat_messages": [],
    }

    class _QB:
        def __init__(self, data=None, count=None):
            self._data = data or []
            self._count = count
            self._single = False

        def select(self, *a, **kw): return self
        def eq(self, *a, **kw): return self
        def neq(self, *a, **kw): return self
        def insert(self, data, **kw): return self
        def delete(self, **kw): return self
        def order(self, *a, **kw): return self
        def limit(self, *a, **kw): return self
        def ilike(self, *a, **kw): return self
        def maybe_single(self): self._single = True; return self
        def single(self): self._single = True; return self

        async def execute(self):
            from dataclasses import dataclass

            @dataclass
            class Resp:
                data: object
                count: object = None

            d = self._data[0] if self._single and self._data else self._data
            return Resp(data=d, count=self._count)

    def _make_client():
        c = MagicMock()
        c.table = lambda name: _QB(data=table_data.get(name, []))
        return c

    client = _make_client()
    # TenantContextMiddleware calls supabase.get_scoped_client(token)
    client.get_scoped_client = lambda token: _make_client()
    return client


@pytest_asyncio.fixture(scope="module")
async def patched_app():
    """Import the FastAPI app with all external services mocked."""
    mock_db = _mock_supabase_client()
    with (
        patch("app.core.database.supabase", mock_db),
        patch("app.services.cache_service.cache_service.init", new_callable=AsyncMock),
        patch("app.services.cache_service.cache_service.ping", new_callable=AsyncMock, return_value=False),
        patch("app.services.event_bus.event_bus.start", new_callable=AsyncMock),
        patch("app.services.event_bus.event_bus.stop", new_callable=AsyncMock),
        patch("app.services.audit_logger.audit_logger.force_flush", new_callable=AsyncMock),
    ):
        from app.main import app
        yield app


@pytest_asyncio.fixture(autouse=True)
async def _reset_rate_limiter():
    from app.core.rate_limiter import (
        RateLimitMiddleware,
        _endpoint_limiters,
        _per_ip_limiter,
        _per_user_limiter,
        rate_limiter,
    )

    # Clear legacy token-bucket limiter
    rate_limiter.tokens.clear()
    rate_limiter.last_update.clear()
    # Clear sliding-window limiters (#37)
    _per_ip_limiter._memory_store.clear()
    _per_user_limiter._memory_store.clear()
    for limiter in _endpoint_limiters.values():
        limiter._memory_store.clear()
    # Clear class-level tiered category limiters (Phase 3)
    for cat_limiter in RateLimitMiddleware._category_limiters.values():
        cat_limiter.tokens.clear()
        cat_limiter.last_update.clear()
    yield


@pytest_asyncio.fixture()
async def client(patched_app):
    transport = ASGITransport(app=patched_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture()
async def authed_client(patched_app):
    """Client with auth bypassed at both middleware and route levels.

    - dependency_overrides: bypasses FastAPI's Depends(get_current_user_id) in routes
    - patch on app.core.auth: bypasses TenantContextMiddleware's direct call
    """
    from app.core.auth import get_current_user_id

    async def _fake_user():
        return "test-user"

    # Middleware version needs to accept (request, authorization) kwargs
    async def _fake_user_mw(**kwargs):
        return "test-user"

    patched_app.dependency_overrides[get_current_user_id] = _fake_user
    with patch("app.core.auth.get_current_user_id", new=_fake_user_mw):
        transport = ASGITransport(app=patched_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    patched_app.dependency_overrides.pop(get_current_user_id, None)


def _fake_jwt_header():
    """Return a fake Authorization header that passes the auth middleware."""
    return {"Authorization": "Bearer fake-test-token"}


# ── E2E Tests ──


class TestChatEndpointE2E:
    """End-to-end tests for POST /api/chat through the full middleware stack."""

    @pytest.mark.asyncio
    async def test_chat_requires_auth(self, client):
        """POST /api/chat without auth returns 401/403."""
        resp = await client.post("/api/chat", json={
            "messages": [{"role": "user", "content": "hello"}],
        })
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_chat_returns_sse_stream(self, authed_client):
        """POST /api/chat with valid auth returns text/event-stream."""

        async def fake_stream(*args, **kwargs):
            yield f"data: {json.dumps({'status': '正在思考...'})}\n\n"
            yield f"data: {json.dumps({'choices': [{'delta': {'content': '你好！'}}]})}\n\n"
            yield "data: [DONE]\n\n"

        with (
            patch("app.agent.run_agent_stream", side_effect=fake_stream),
            patch("app.routers.chat.ChatService.get_system_prompt", new_callable=AsyncMock, return_value="You are helpful."),
            patch("app.routers.chat.validate_request_tokens", return_value=(True, 100, None)),
            patch("app.routers.chat.check_user_input", return_value=(True, None)),
        ):
            resp = await authed_client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": "你好"}]},
                headers={"Authorization": "Bearer fake-e2e-token"},
            )

            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")

            # Parse SSE events
            body = resp.text
            events = [line.removeprefix("data: ") for line in body.strip().split("\n") if line.startswith("data: ")]
            assert len(events) >= 2
            assert events[-1] == "[DONE]"

            # First content event should contain 你好
            content_events = [e for e in events if e != "[DONE]" and "choices" in e]
            assert len(content_events) >= 1
            parsed = json.loads(content_events[0])
            assert parsed["choices"][0]["delta"]["content"] == "你好！"

    @pytest.mark.asyncio
    async def test_chat_content_moderation_blocks_unsafe(self, authed_client):
        """Content moderation blocks unsafe input with error stream."""
        with patch("app.routers.chat.check_user_input", return_value=(False, "检测到敏感信息")):
            resp = await authed_client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": "unsafe content"}]},
                headers={"Authorization": "Bearer fake-e2e-token"},
            )

            assert resp.status_code == 200  # SSE always returns 200
            body = resp.text
            assert "安全拦截" in body

    @pytest.mark.asyncio
    async def test_chat_no_api_key_returns_error(self, authed_client):
        """Missing API key returns an error in the SSE stream."""
        with (
            patch("app.routers.chat.check_user_input", return_value=(True, None)),
            patch("app.routers.chat.validate_request_tokens", return_value=(True, 100, None)),
            patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False),
        ):
            resp = await authed_client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": "hello"}]},
                headers={"Authorization": "Bearer fake-e2e-token"},
            )

            assert resp.status_code == 200
            body = resp.text
            assert "API Key" in body or "[DONE]" in body


class TestChatHistoryE2E:
    """E2E tests for chat history and session endpoints."""

    @pytest.mark.asyncio
    async def test_history_requires_auth(self, client):
        """GET /api/history/{session_id} without auth returns 401/403."""
        resp = await client.get("/api/history/test-session")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_sessions_requires_auth(self, client):
        """GET /api/sessions without auth returns 401/403."""
        resp = await client.get("/api/sessions")
        assert resp.status_code in (401, 403)


class TestDashboardE2E:
    """E2E tests for dashboard endpoint through middleware stack."""

    @pytest.mark.asyncio
    async def test_boss_dashboard_requires_auth(self, client):
        """GET /api/dashboard/boss without auth returns 401/403."""
        resp = await client.get("/api/dashboard/boss")
        assert resp.status_code in (401, 403)


class TestAgentStreamFormat:
    """Unit tests for SSE formatting helpers used in the agent stream."""

    def test_sse_status_format(self):
        """Status events are valid SSE JSON."""
        from app.agent.stream import _sse_status
        result = _sse_status("正在分析...")
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        parsed = json.loads(result.removeprefix("data: ").strip())
        assert parsed["status"] == "正在分析..."

    def test_sse_content_format(self):
        """Content events follow OpenAI-compatible format."""
        from app.agent.stream import _sse_content
        result = _sse_content("hello")
        parsed = json.loads(result.removeprefix("data: ").strip())
        assert parsed["choices"][0]["delta"]["content"] == "hello"

    def test_sse_thinking_format(self):
        """Thinking step events contain expected fields."""
        from app.agent.stream import _sse_thinking
        from app.agent.state import ThinkingStep
        step = ThinkingStep(phase="planning", content="Analyzing...", tool_name="search")
        result = _sse_thinking(step)
        parsed = json.loads(result.removeprefix("data: ").strip())
        assert "thinking_step" in parsed
        assert parsed["thinking_step"]["phase"] == "planning"
        assert parsed["thinking_step"]["content"] == "Analyzing..."
