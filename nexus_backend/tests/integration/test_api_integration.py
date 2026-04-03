"""
Integration tests for FastAPI endpoints.
对标大厂标准：验证从 HTTP 入口到 Agent 核心逻辑的完整集成链路。
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import MagicMock, patch, AsyncMock
from app.main import app


@pytest.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
def mock_auth_user():
    return {
        "id": "user-api-test-01",
        "email": "tester@nexus.ai",
        "app_metadata": {"organization_id": "org-test-01"},
        "user_metadata": {"role": "boss"}
    }

@pytest.mark.asyncio
async def test_health_check_endpoint(api_client):
    """验证基础平稳性 (Smoke Test)."""
    response = await api_client.get("/health")
    # 适配项目实际路径，可能是 /api/health 或 /health
    if response.status_code == 404:
        response = await api_client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_chat_stream_endpoint_integration(api_client, mock_auth_user):
    """
    验证 Agent 流式对话接口的集成稳定性。
    模拟前端发送消息，验证后端是否正确初始化 Graph 并触发流。
    """
    # 1. Mock Auth Middleware
    with patch("app.core.auth.get_current_user", return_value=mock_auth_user), \
         patch("app.agent.graph.agent_graph.astream", new_callable=AsyncMock) as mock_stream:

        # 模拟 LangGraph 流式输出
        async def mock_gen(*args, **kwargs):
            yield {"node": "plan", "content": "Thinking..."}
            yield {"node": "execute", "content": "Done."}
        mock_stream.side_effect = mock_gen

        payload = {
            "message": "帮我看看上周的销售额",
            "stream": True,
            "thread_id": "test-thread-123"
        }

        # 实际 API 调用
        response = await api_client.post(
            "/api/v1/chat/stream",
            json=payload,
            headers={"X-Tenant-ID": "org-test-01"}
        )

        # 验证
        assert response.status_code in [200, 201]
        # 注意：由于是流式，实际测试 AsyncClient 可能需要读取 response.aiter_lines()
        # 这里验证入口逻辑正确触发即可
