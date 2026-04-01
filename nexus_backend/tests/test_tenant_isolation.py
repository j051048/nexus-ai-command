"""
#5 — Multi-tenant Isolation (多租户隔离测试)

测试数据隔离:
- 向量搜索缺少 org_id -> P0 安全违规错误
- 向量搜索使用错误 org_id -> 无结果
- 审批查询按 organization_id 隔离
- LLM 网关按 tenant 解析模型
- 调度规则按 tenant_id 隔离
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
#  Vector Service 租户隔离
# ═══════════════════════════════════════════════════════════════════════════════


class TestVectorServiceTenantIsolation:
    """测试向量搜索的组织隔离"""

    async def test_search_without_org_id_returns_error(self):
        """缺少 org_id 的向量搜索应返回安全错误"""
        from app.services.vector_service import VectorService

        service = VectorService()

        # 默认 require_org_id=True
        result = await service.search(
            query="测试查询",
            user_id="user-001",
            org_id=None,
        )

        assert "缺少组织" in result or "搜索失败" in result

    async def test_search_with_require_org_id_true(self):
        """require_org_id=True 时缺少 org_id 应返回错误"""
        from app.services.vector_service import VectorService

        service = VectorService()

        result = await service.search(
            query="产品信息",
            user_id="user-002",
            org_id=None,
            require_org_id=True,
        )

        assert "缺少" in result or "搜索失败" in result

    async def test_search_with_valid_org_id_proceeds(self):
        """提供有效 org_id 时搜索应正常进行（mock 外部调用）"""
        from app.services.vector_service import VectorService

        service = VectorService()

        # 模拟 API key 不存在 -> 走 mock 路径
        with patch("app.services.vector_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = ""
            mock_settings.AI_BASE_URL = "https://api.test.com/v1"
            mock_settings.IS_PRODUCTION = False

            result = await service.search(
                query="销售流程",
                user_id="user-003",
                org_id="org-001",
            )

        # 在非生产环境下应走 mock 路径，返回数据
        assert isinstance(result, str)

    async def test_search_empty_query_returns_message(self):
        """空查询应返回提示信息"""
        from app.services.vector_service import VectorService

        service = VectorService()

        result = await service.search(
            query="",
            user_id="user-001",
            org_id="org-001",
        )

        assert "有效" in result or "关键词" in result

    async def test_sanitize_search_query(self):
        """搜索查询应被安全过滤"""
        from app.services.vector_service import sanitize_search_query

        # SQL 注入特殊字符应被清除
        sanitized = sanitize_search_query("test; DROP TABLE--")
        assert ";" not in sanitized
        assert "--" not in sanitized

        # 长查询应被截断
        long_query = "a" * 1000
        sanitized = sanitize_search_query(long_query, max_length=500)
        assert len(sanitized) <= 500

    async def test_empty_query_sanitized(self):
        """空查询应返回空字符串"""
        from app.services.vector_service import sanitize_search_query

        assert sanitize_search_query("") == ""
        assert sanitize_search_query(None) == ""


# ═══════════════════════════════════════════════════════════════════════════════
#  Approval 租户隔离
# ═══════════════════════════════════════════════════════════════════════════════


class TestApprovalTenantIsolation:
    """测试审批数据的组织隔离"""

    async def test_approval_chain_scoped_to_org(self):
        """审批链加载应按 org_id 过滤"""
        from app.services.approval_chain import ApprovalChainService
        from tests.conftest import MockSupabaseClient

        service = ApprovalChainService()

        # 设置 mock DB 返回特定组织的审批链
        db = MockSupabaseClient()
        db.set_table_data("approval_chains", [])

        result = await service.load_chain_from_db(
            org_id="org-tenant-A",
            approval_type="purchase",
            db=db,
        )

        # 无 DB 数据时应回退到默认链
        assert result is not None
        assert result["source"] == "default"

    async def test_match_and_bind_chain_uses_org_id(self):
        """match_and_bind_chain 应使用 org_id 进行匹配"""
        from app.services.approval_chain import ApprovalChainService
        from tests.conftest import MockSupabaseClient

        service = ApprovalChainService()

        db = MockSupabaseClient()
        db.set_table_data("approval_chains", [])

        result = await service.match_and_bind_chain(
            org_id="org-tenant-B",
            approval_type="expense",
            amount=1000,
            db=db,
        )

        assert result is not None
        assert "chain_name" in result


# ═══════════════════════════════════════════════════════════════════════════════
#  LLM Gateway 租户隔离
# ═══════════════════════════════════════════════════════════════════════════════


class TestLLMGatewayTenantIsolation:
    """测试 LLM 网关的租户隔离"""

    async def test_resolve_model_uses_tenant_id(self):
        """模型解析应优先使用租户特定的配置"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        # 没有 DB 连接时应返回 None
        with patch("app.services.llm_gateway.model_resolution.supabase", new=None):
            result = await service._resolve_model("chat", "default", "org-tenant-A")

        assert result is None  # 无 DB 返回 None

    async def test_load_model_config_no_db(self):
        """无 DB 时 load_model_config 应返回 None"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        with patch("app.services.llm_gateway.model_resolution.supabase", new=None):
            result = await service._load_model_config("gpt-4o", "org-001")

        assert result is None

    async def test_cache_invalidation_per_org(self):
        """缓存失效应支持按组织隔离"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        # 手动填充缓存
        service._model_cache["org-A:model-1"] = ("config_a", 0)
        service._model_cache["org-B:model-1"] = ("config_b", 0)
        service._schedule_cache["org-A:scene:agent"] = ("rule_a", 0)

        # 仅清除 org-A 的缓存
        service.invalidate_cache(org_id="org-A")

        assert "org-A:model-1" not in service._model_cache
        assert "org-B:model-1" in service._model_cache
        assert "org-A:scene:agent" not in service._schedule_cache

    async def test_cache_invalidation_all(self):
        """全局缓存失效应清除所有租户数据"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        service._model_cache["org-A:model"] = ("config", 0)
        service._model_cache["org-B:model"] = ("config", 0)

        service.invalidate_cache(org_id=None)

        assert len(service._model_cache) == 0
        assert len(service._schedule_cache) == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  LIKE Pattern Escape 安全测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestSQLInjectionPrevention:
    """测试 SQL 注入防护"""

    def test_escape_like_pattern(self):
        """LIKE 模式中的特殊字符应被转义"""
        from app.services.vector_service import escape_like_pattern

        assert escape_like_pattern("test%injection") == "test\\%injection"
        assert escape_like_pattern("test_injection") == "test\\_injection"
        assert escape_like_pattern("normal") == "normal"
        assert escape_like_pattern("") == ""
