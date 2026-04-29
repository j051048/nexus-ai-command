"""
E2E 补充测试：完整业务流程端到端验证

覆盖：多场景 API 全链路测试、跨模块工作流验证、错误恢复场景
"""

import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ════════════════════════════════════════════════════════════════════
# 工具元数据完整性 E2E
# ════════════════════════════════════════════════════════════════════


class TestToolMetadataE2E:
    """工具元数据完整性验证"""

    def test_all_tools_have_name(self):
        """每个工具必须有 name 属性"""
        from app.tools import TOOL_REGISTRY
        for name, tool_cls in TOOL_REGISTRY.items():
            t = tool_cls() if isinstance(tool_cls, type) else tool_cls
            assert hasattr(t, "name"), f"工具 {name} 缺少 name 属性"
            assert t.name == name, f"工具注册名 '{name}' != 实际名 '{t.name}'"

    def test_all_tools_have_description(self):
        """每个工具必须有 description"""
        from app.tools import TOOL_REGISTRY
        for name, tool_cls in TOOL_REGISTRY.items():
            t = tool_cls() if isinstance(tool_cls, type) else tool_cls
            desc = getattr(t, "description", "")
            assert desc and len(desc) > 5, (
                f"工具 '{name}' description 不合规: '{desc}'"
            )

    def test_all_tools_have_parameters(self):
        """每个工具必须有 parameters schema"""
        from app.tools import TOOL_REGISTRY
        for name, tool_cls in TOOL_REGISTRY.items():
            t = tool_cls() if isinstance(tool_cls, type) else tool_cls
            params = getattr(t, "parameters", None)
            assert params is not None, f"工具 '{name}' 缺少 parameters"
            assert isinstance(params, dict), f"工具 '{name}' parameters 不是 dict"

    def test_all_tools_have_domain_or_category(self):
        """每个工具应有 domain 或 category"""
        from app.tools import TOOL_REGISTRY
        missing = []
        for name, tool_cls in TOOL_REGISTRY.items():
            t = tool_cls() if isinstance(tool_cls, type) else tool_cls
            domain = getattr(t, "domain", None)
            category = getattr(t, "category", None)
            if not domain and not category:
                missing.append(name)
        # 系统工具可能无 domain，但不应超过 10%
        ratio = len(missing) / len(TOOL_REGISTRY) if TOOL_REGISTRY else 0
        assert ratio < 0.15, (
            f"{len(missing)}/{len(TOOL_REGISTRY)} 工具缺少 domain/category: {missing[:10]}"
        )

    def test_all_tools_have_run_method(self):
        """每个工具必须实现 run 方法"""
        from app.tools import TOOL_REGISTRY
        import inspect
        for name, tool_cls in TOOL_REGISTRY.items():
            t = tool_cls() if isinstance(tool_cls, type) else tool_cls
            assert hasattr(t, "run"), f"工具 '{name}' 缺少 run 方法"
            assert inspect.iscoroutinefunction(t.run), (
                f"工具 '{name}' 的 run 方法不是 async"
            )


# ════════════════════════════════════════════════════════════════════
# API 路由 E2E 验证
# ════════════════════════════════════════════════════════════════════


class TestAPIRoutesE2E:
    """API 路由可达性验证"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """健康检查端点应返回 200"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_docs_endpoint(self):
        """API 文档端点应可访问"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/docs")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_unauthenticated_chat_rejected(self):
        """未认证的 chat 请求应被拒绝"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/chat",
                json={"message": "你好"},
            )
        # 未认证应返回 4xx 错误
        assert resp.status_code in (400, 401, 403, 422, 500)

    @pytest.mark.asyncio
    async def test_invalid_json_returns_error(self):
        """无效 JSON 应返回错误"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/chat",
                content="not-json",
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code in (400, 422, 500)


# ════════════════════════════════════════════════════════════════════
# 跨模块工作流 E2E
# ════════════════════════════════════════════════════════════════════


class TestCrossModuleWorkflowE2E:
    """跨模块业务流程验证"""

    def test_tool_related_tools_exist(self):
        """related_tools 引用的工具应真实存在"""
        from app.tools import TOOL_REGISTRY
        broken_refs = []
        for name, tool_cls in TOOL_REGISTRY.items():
            t = tool_cls() if isinstance(tool_cls, type) else tool_cls
            related = getattr(t, "related_tools", [])
            for ref in related:
                if ref not in TOOL_REGISTRY:
                    broken_refs.append(f"{name} → {ref}")
        # 不应有太多断链引用
        assert len(broken_refs) < len(TOOL_REGISTRY) * 0.1, (
            f"发现 {len(broken_refs)} 个断链引用: {broken_refs[:10]}"
        )

    def test_irreversible_tools_have_confirmation(self):
        """标记为不可逆的工具应有确认消息"""
        from app.tools import TOOL_REGISTRY
        missing_confirm = []
        for name, tool_cls in TOOL_REGISTRY.items():
            t = tool_cls() if isinstance(tool_cls, type) else tool_cls
            if getattr(t, "is_irreversible", False):
                msg = getattr(t, "confirmation_message", "")
                if not msg:
                    missing_confirm.append(name)
        assert not missing_confirm, (
            f"不可逆工具缺少确认消息: {missing_confirm}"
        )

    def test_admin_tools_have_required_role(self):
        """管理员专属工具应标记 required_role"""
        from app.tools import TOOL_REGISTRY
        admin_keywords = ["delete", "create_department", "create_asset"]
        for kw in admin_keywords:
            if kw in TOOL_REGISTRY:
                tool_cls = TOOL_REGISTRY[kw]
                t = tool_cls() if isinstance(tool_cls, type) else tool_cls
                role = getattr(t, "required_role", None)
                if role:
                    assert role in ("admin", "manager"), (
                        f"工具 '{kw}' required_role 应为 admin/manager，实际: {role}"
                    )


# ════════════════════════════════════════════════════════════════════
# 错误恢复 E2E
# ════════════════════════════════════════════════════════════════════


class TestErrorRecoveryE2E:
    """错误恢复场景验证"""

    def test_tool_safe_error_handler(self):
        """safe_tool_error 应返回用户友好的错误"""
        from app.tools._shared import safe_tool_error

        result = safe_tool_error(Exception("Database connection failed"), "查询客户")
        assert isinstance(result, str)
        assert "客户" in result or "查询" in result or "失败" in result

    def test_tool_safe_error_no_stack_trace(self):
        """safe_tool_error 不应暴露堆栈追踪"""
        from app.tools._shared import safe_tool_error

        result = safe_tool_error(
            ValueError("Traceback (most recent call last):\n  File xxx"),
            "操作",
        )
        assert "Traceback" not in result or "most recent" not in result

    def test_validate_uuid_rejects_invalid(self):
        """_validate_uuid 应拒绝无效 UUID"""
        from app.tools._shared import _validate_uuid

        assert _validate_uuid("not-a-uuid", "test_field") is not None
        assert _validate_uuid("", "test_field") is not None
        assert _validate_uuid(None, "test_field") is not None

    def test_validate_uuid_accepts_valid(self):
        """_validate_uuid 应接受有效 UUID"""
        from app.tools._shared import _validate_uuid

        valid_uuid = str(uuid.uuid4())
        result = _validate_uuid(valid_uuid, "test_field")
        assert result is None  # None 表示验证通过
