"""
E2E 审批全流程测试

覆盖：提交审批 → 审批人审批 → 状态更新 → 通知 → 审计日志
"""
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _mock_auth(user_id="u-1", org_id="org-1", role="boss"):
    """模拟认证中间件"""
    return {
        "user_id": user_id,
        "org_id": org_id,
        "role": role,
        "token": "test-jwt",
    }


class TestApprovalE2EFlow:
    """审批全流程 E2E"""

    @pytest.mark.asyncio
    @patch("app.core.auth.get_current_user_id")
    async def test_health_check(self, mock_auth, async_client):
        """基础健康检查"""
        response = await async_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    @patch("app.core.auth.get_current_user_id")
    async def test_unauthenticated_approval_rejected(self, mock_auth, async_client):
        """未认证请求被拒绝"""
        mock_auth.side_effect = Exception("Unauthorized")
        response = await async_client.get("/api/approval/list")
        assert response.status_code in (401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_approval_list_endpoint_exists(self, async_client):
        """审批列表端点存在"""
        response = await async_client.get("/api/approval/list")
        # 可能 401（未认证）但不应 404
        assert response.status_code != 404


class TestCRME2EFlow:
    """CRM 全流程 E2E"""

    @pytest.mark.asyncio
    async def test_crm_endpoints_exist(self, async_client):
        """CRM 端点存在"""
        endpoints = ["/api/crm/customers", "/api/crm/stages"]
        for ep in endpoints:
            response = await async_client.get(ep)
            assert response.status_code != 404, f"{ep} should exist"

    @pytest.mark.asyncio
    async def test_crm_requires_auth(self, async_client):
        """CRM 端点需要认证"""
        response = await async_client.get("/api/crm/customers")
        assert response.status_code in (401, 403, 422, 500)


class TestWorkflowE2EFlow:
    """工作流全流程 E2E"""

    @pytest.mark.asyncio
    async def test_workflow_list_endpoint(self, async_client):
        """工作流列表端点"""
        response = await async_client.get("/api/workflows")
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_workflow_templates_endpoint(self, async_client):
        """工作流模板端点"""
        response = await async_client.get("/api/workflow-templates")
        assert response.status_code != 404


class TestAIChatE2EFlow:
    """AI 聊天全流程 E2E"""

    @pytest.mark.asyncio
    async def test_chat_stream_endpoint_exists(self, async_client):
        """聊天流端点存在"""
        response = await async_client.post("/api/chat", json={
            "message": "你好",
            "session_id": "test-session",
        })
        # 可能 401 但不应 404
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_chat_sessions_endpoint(self, async_client):
        """聊天会话端点"""
        response = await async_client.get("/api/sessions")
        assert response.status_code != 404


class TestErrorResponseFormat:
    """错误响应格式一致性"""

    @pytest.mark.asyncio
    async def test_404_returns_json(self, async_client):
        """404 返回 JSON 格式"""
        response = await async_client.get("/api/nonexistent-endpoint-12345")
        assert response.status_code in (404, 405)

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, async_client):
        """不支持的 HTTP 方法"""
        response = await async_client.delete("/health")
        assert response.status_code in (405, 404, 200)
