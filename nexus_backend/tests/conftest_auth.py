"""
测试工具：认证客户端装饰器
提供稳定的用户身份注入，解决测试中的认证 Mock 问题

策略:
1. FastAPI dependency_overrides 绕过 get_current_user_id / get_db
2. mock _get_user_role 返回指定角色 (用于 require_role)
3. patch TenantContextMiddleware + APIKeyMiddleware 为透传,
   在 ASGI scope 中预注入 request.state 值 (org_id, user_role, db)
"""

import pytest
from httpx import ASGITransport, AsyncClient
from typing import Optional
from unittest.mock import AsyncMock, patch

from app.core.auth import get_current_user_id
from app.core.dependencies import get_db


class _MockDB:
    """最小化的内存 Mock DB，满足路由层 .table().select()... 调用链"""

    def table(self, name):
        return _MockQuery()

    def get_scoped_client(self, token):
        return self


class _MockQuery:
    def __init__(self):
        self._data = []
        self._single = False

    def select(self, *a, **kw):
        return self

    def eq(self, col, val):
        return self

    def neq(self, col, val):
        return self

    def order(self, *a, **kw):
        return self

    def limit(self, n):
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._single = True
        return self

    def insert(self, data):
        self._data = [data] if isinstance(data, dict) else data
        return self

    def update(self, data):
        return self

    def delete(self):
        return self

    def contains(self, *a, **kw):
        return self

    def gte(self, *a, **kw):
        return self

    async def execute(self):
        data = self._data
        if self._single:
            data = data[0] if data else None
        return type("Resp", (), {
            "data": data,
            "error": None,
            "count": len(self._data) if isinstance(self._data, list) else 0,
        })()


class AuthenticatedTestClient:
    """
    测试客户端装饰器，自动注入用户身份（基于 httpx AsyncClient）

    - dependency_overrides 绕过 JWT (get_current_user_id) 和 DB (get_db)
    - mock _get_user_role 返回指定角色 (用于 require_role)
    - patch 中间件为透传 + ASGI scope state 注入 (用于 request.state 访问)

    用法:
        client = AuthenticatedTestClient(app, user_id="test-user", role="boss")
        response = await client.get("/api/projects/")
    """

    def __init__(
        self,
        app,
        user_id: str = "test-user-123",
        role: str = "employee",
        org_id: Optional[str] = "test-org-456",
    ):
        self.app = app
        self.user_id = user_id
        self.role = role
        self.org_id = org_id
        self._mock_db = _MockDB()

    async def _request(self, method, *args, **kwargs):
        user_id = self.user_id
        role = self.role
        org_id = self.org_id
        mock_db = self._mock_db

        # 1. Override FastAPI dependencies
        async def fake_user_id():
            return user_id

        async def fake_get_db():
            return mock_db

        self.app.dependency_overrides[get_current_user_id] = fake_user_id
        self.app.dependency_overrides[get_db] = fake_get_db

        # 2. Create transport that injects ASGI scope state
        transport = _StateInjectingTransport(
            app=self.app,
            user_id=user_id,
            role=role,
            org_id=org_id,
            mock_db=mock_db,
        )

        try:
            # 3. Patch middleware to pass through + mock _get_user_role
            with (
                patch(
                    "app.core.security_middleware.TenantContextMiddleware.dispatch",
                    new=_passthrough_dispatch,
                ),
                patch(
                    "app.core.api_key_middleware.APIKeyMiddleware.dispatch",
                    new=_passthrough_dispatch,
                ),
                patch(
                    "app.core.dependencies._get_user_role",
                    new_callable=AsyncMock,
                    return_value=role,
                ),
            ):
                # Force middleware stack rebuild so newly constructed instances
                # capture the PATCHED dispatch methods.
                # Starlette BaseHTTPMiddleware.__init__ does:
                #     self.dispatch_func = self.dispatch
                # capturing a bound-method at construction time. If the stack
                # was already built by a prior test, dispatch_func holds the
                # ORIGINAL dispatch and class-level patch has no effect.
                self.app.middleware_stack = None
                try:
                    async with AsyncClient(transport=transport, base_url="http://test") as ac:
                        return await getattr(ac, method)(*args, **kwargs)
                finally:
                    # Invalidate the patched stack so the next test without
                    # patches gets a clean rebuild with original methods.
                    self.app.middleware_stack = None
        finally:
            self.app.dependency_overrides.pop(get_current_user_id, None)
            self.app.dependency_overrides.pop(get_db, None)

    async def get(self, *args, **kwargs):
        return await self._request("get", *args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._request("post", *args, **kwargs)

    async def put(self, *args, **kwargs):
        return await self._request("put", *args, **kwargs)

    async def patch(self, *args, **kwargs):
        return await self._request("patch", *args, **kwargs)

    async def delete(self, *args, **kwargs):
        return await self._request("delete", *args, **kwargs)


async def _passthrough_dispatch(self, request, call_next):
    """透传中间件 — 不做认证，但确保 scope state 值在 request.state 上可访问"""
    # Starlette 的 BaseHTTPMiddleware 可能导致 scope state 传递不可靠，
    # 这里主动将 scope state 中的值设置到 request.state 上
    scope_state = request.scope.get("state", {})
    for key, value in scope_state.items():
        setattr(request.state, key, value)
    return await call_next(request)


class _StateInjectingTransport(ASGITransport):
    """在 ASGI scope 中注入 state 值的自定义 Transport

    由于 TenantContextMiddleware 和 APIKeyMiddleware 已被 patch 为透传，
    这里注入的 state 值不会被覆盖。
    """

    def __init__(self, app, user_id, role, org_id, mock_db):
        super().__init__(app=app)
        self._user_id = user_id
        self._role = role
        self._org_id = org_id
        self._mock_db = mock_db

    async def handle_async_request(self, request):
        original_app = self.app
        user_id = self._user_id
        role = self._role
        org_id = self._org_id
        mock_db = self._mock_db

        async def patched_app(scope, receive, send):
            if scope["type"] == "http":
                if "state" not in scope:
                    scope["state"] = {}
                scope["state"]["user_id"] = user_id
                scope["state"]["user_role"] = role
                scope["state"]["org_id"] = org_id
                scope["state"]["db"] = mock_db
                scope["state"]["api_key_auth"] = True
                scope["state"]["auth_failed"] = False
            await original_app(scope, receive, send)

        self.app = patched_app
        try:
            return await super().handle_async_request(request)
        finally:
            self.app = original_app


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
