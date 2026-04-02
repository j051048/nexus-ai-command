"""
测试工具：认证客户端装饰器
提供稳定的用户身份注入，解决测试中的认证 Mock 问题
"""

import pytest
from fastapi.testclient import TestClient
from typing import Optional
from unittest.mock import patch


class AuthenticatedTestClient:
    """
    测试客户端装饰器，自动注入用户身份

    用法:
        client = AuthenticatedTestClient(app, user_id="test-user", role="boss")
        response = client.get("/api/projects")
    """

    def __init__(
        self,
        app,
        user_id: str = "test-user-123",
        role: str = "employee",
        org_id: Optional[str] = "test-org-456",
    ):
        self.client = TestClient(app)
        self.user_id = user_id
        self.role = role
        self.org_id = org_id

    def _inject_auth(self):
        """注入认证上下文"""
        return patch("app.core.auth.get_current_user_id", return_value=self.user_id)

    def get(self, *args, **kwargs):
        with self._inject_auth():
            return self.client.get(*args, **kwargs)

    def post(self, *args, **kwargs):
        with self._inject_auth():
            return self.client.post(*args, **kwargs)

    def put(self, *args, **kwargs):
        with self._inject_auth():
            return self.client.put(*args, **kwargs)

    def patch(self, *args, **kwargs):
        with self._inject_auth():
            return self.client.patch(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with self._inject_auth():
            return self.client.delete(*args, **kwargs)


@pytest.fixture
def auth_client_employee(app):
    """普通员工客户端"""
    return AuthenticatedTestClient(app, user_id="emp-001", role="employee")


@pytest.fixture
def auth_client_manager(app):
    """经理客户端"""
    return AuthenticatedTestClient(app, user_id="mgr-001", role="manager")


@pytest.fixture
def auth_client_boss(app):
    """Boss/Founder 客户端"""
    return AuthenticatedTestClient(app, user_id="boss-001", role="boss")
