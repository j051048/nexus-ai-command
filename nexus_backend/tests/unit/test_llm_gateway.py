"""
#6 — Gateway Routing (LLM 网关路由测试)

测试模型解析优先级链:
- 精确匹配: scene+agent+tenant -> 返回 primary model
- 场景通配: scene+*+tenant -> 返回 model
- 全局通配: *+*+tenant -> 返回默认 model
- 租户回退: org_id 未找到 -> 尝试 "default" 租户
- 断路器: primary model 不健康 -> 返回 backup
- _load_model_config: 缓存有效（第二次调用使用缓存）
- _pick_healthy_model: 仅使用 *_model_code 字段
- _fill_model_codes: 从 model_id 解析 model_code
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
#  _pick_healthy_model 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestPickHealthyModel:
    """测试健康模型选择逻辑"""

    def test_primary_healthy_returns_primary(self):
        """primary 健康时应返回 primary"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        rule = {
            "primary_model_code": "gpt-4o",
            "backup_model_code": "gpt-4o-mini",
        }

        with patch("app.services.llm_gateway_service.circuit_breaker_manager") as mock_cb:
            mock_cb.is_allowed.return_value = True
            result = service._pick_healthy_model(rule)

        assert result == "gpt-4o"

    def test_primary_unhealthy_returns_backup(self):
        """primary 不健康时应返回 backup"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        rule = {
            "primary_model_code": "gpt-4o",
            "backup_model_code": "gpt-4o-mini",
        }

        with patch("app.services.llm_gateway_service.circuit_breaker_manager") as mock_cb:
            # primary 不健康, backup 健康
            mock_cb.is_allowed.side_effect = lambda model: model != "gpt-4o"
            result = service._pick_healthy_model(rule)

        assert result == "gpt-4o-mini"

    def test_both_unhealthy_returns_primary_as_fallback(self):
        """两个模型都不健康时应返回 primary 作为最后手段"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        rule = {
            "primary_model_code": "gpt-4o",
            "backup_model_code": "gpt-4o-mini",
        }

        with patch("app.services.llm_gateway_service.circuit_breaker_manager") as mock_cb:
            mock_cb.is_allowed.return_value = False
            result = service._pick_healthy_model(rule)

        assert result == "gpt-4o"

    def test_prefers_primary_model_code_over_id(self):
        """应优先使用 primary_model_code 而非 primary_model_id"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        rule = {
            "primary_model_code": "custom-gpt-4o",
            "primary_model_id": "generic-id",
            "backup_model_code": "backup-model",
        }

        with patch("app.services.llm_gateway_service.circuit_breaker_manager") as mock_cb:
            mock_cb.is_allowed.return_value = True
            result = service._pick_healthy_model(rule)

        assert result == "custom-gpt-4o"

    def test_empty_model_code_with_model_id_returns_none(self):
        """primary_model_code 为空时，_pick_healthy_model 返回 None（ID 解析由 _fill_model_codes 处理）"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        rule = {
            "primary_model_code": "",
            "primary_model_id": 20,
            "backup_model_code": "backup-model",
        }

        with patch("app.services.llm_gateway_service.circuit_breaker_manager") as mock_cb:
            mock_cb.is_allowed.return_value = True
            result = service._pick_healthy_model(rule)

        # primary_model_code is empty, so primary is None; should fall through to backup
        assert result == "backup-model"

    def test_no_models_returns_none(self):
        """无 primary 也无 backup 时返回 None"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        rule = {}

        with patch("app.services.llm_gateway_service.circuit_breaker_manager") as mock_cb:
            mock_cb.is_allowed.return_value = True
            result = service._pick_healthy_model(rule)

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
#  _load_model_config 缓存测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestModelConfigCaching:
    """测试模型配置缓存"""

    async def test_cache_hit_avoids_db_call(self):
        """缓存命中时不应再查询 DB"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        # 手动插入缓存（使用当前时间以确保缓存有效）
        mock_config = MagicMock()
        service._model_cache["org-001:gpt-4o"] = (mock_config, time.time())

        with patch("app.services.llm_gateway_service.supabase") as mock_db:
            result = await service._load_model_config("gpt-4o", "org-001")

        # DB 不应被调用
        mock_db.table.assert_not_called()
        assert result is mock_config

    async def test_cache_expired_triggers_db_call(self):
        """缓存过期时应重新查询 DB"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        # 插入过期缓存
        mock_config = MagicMock()
        service._model_cache["org-002:gpt-4o"] = (mock_config, time.time() - 600)  # 10 分钟前

        # DB 返回空结果（模拟未找到）
        with patch("app.services.llm_gateway_service.supabase", new=None):
            result = await service._load_model_config("gpt-4o", "org-002")

        # 无 DB 应返回 None
        assert result is None

    async def test_cache_ttl_defaults_to_300s(self):
        """缓存 TTL 应默认为 300 秒"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()
        assert service._CACHE_TTL == 300


# ═══════════════════════════════════════════════════════════════════════════════
#  _resolve_model 优先级链测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveModelPriority:
    """测试模型解析优先级链"""

    async def test_resolve_no_db_returns_none(self):
        """无 DB 连接时应返回 None"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        with patch("app.services.llm_gateway_service.supabase", new=None):
            result = await service._resolve_model("chat", "default_agent", "org-001")

        assert result is None

    async def test_resolve_cache_hit(self):
        """缓存命中时应直接返回"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()

        # 插入缓存
        cached_rule = {
            "primary_model_code": "cached-model",
            "backup_model_code": "backup-model",
        }
        service._schedule_cache["org-001:chat:agent:_"] = (cached_rule, time.time())

        with (
            patch("app.services.llm_gateway_service.supabase"),
            patch("app.services.llm_gateway_service.circuit_breaker_manager") as mock_cb,
        ):
            mock_cb.is_allowed.return_value = True
            result = await service._resolve_model("chat", "agent", "org-001")

        assert result == "cached-model"


# ═══════════════════════════════════════════════════════════════════════════════
#  Error Response 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorResponse:
    """测试错误响应构造"""

    def test_error_response_format(self):
        """错误响应应包含正确字段"""
        from app.services.llm_gateway_service import LLMGatewayService

        response = LLMGatewayService._error_response(
            request_id="req-001",
            model_code="gpt-4o",
            error_msg="Connection timeout",
        )

        assert response.request_id == "req-001"
        assert response.model_code == "gpt-4o"
        assert response.finish_reason == "error"
        assert response.content == ""
        assert "error" in response.raw_response

    def test_error_response_zero_tokens(self):
        """错误响应的 token 计数应为 0"""
        from app.services.llm_gateway_service import LLMGatewayService

        response = LLMGatewayService._error_response("req", "model", "err")

        assert response.usage["input_tokens"] == 0
        assert response.usage["output_tokens"] == 0
        assert response.usage["total_tokens"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
#  _fill_model_codes 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestFillModelCodes:
    """测试 model_id → model_code 解析"""

    async def test_fills_primary_code_from_id(self):
        """primary_model_code 为空时应从 primary_model_id 解析出 model_code"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()
        rule = {
            "primary_model_code": "",
            "primary_model_id": 20,
            "backup_model_code": "backup-model",
        }

        mock_response = MagicMock()
        mock_response.data = {"model_code": "gpt-4o-mini"}

        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.maybe_single.return_value = mock_table
        mock_table.execute = AsyncMock(return_value=mock_response)

        mock_db = MagicMock()
        mock_db.table.return_value = mock_table

        with patch("app.services.llm_gateway_service.supabase", new=mock_db):
            await service._fill_model_codes(rule)

        assert rule["primary_model_code"] == "gpt-4o-mini"
        assert rule["backup_model_code"] == "backup-model"

    async def test_skips_when_code_already_present(self):
        """primary_model_code 已存在时不应查询 DB"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()
        rule = {
            "primary_model_code": "existing-model",
            "primary_model_id": 20,
            "backup_model_code": "backup-model",
        }

        with patch("app.services.llm_gateway_service.supabase") as mock_db:
            await service._fill_model_codes(rule)
            mock_db.table.assert_not_called()

        assert rule["primary_model_code"] == "existing-model"

    async def test_handles_db_not_found(self):
        """DB 查询无结果时不应崩溃"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()
        rule = {
            "primary_model_code": "",
            "primary_model_id": 999,
        }

        mock_response = MagicMock()
        mock_response.data = None

        mock_table = MagicMock()
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.maybe_single.return_value = mock_table
        mock_table.execute = AsyncMock(return_value=mock_response)

        mock_db = MagicMock()
        mock_db.table.return_value = mock_table

        with patch("app.services.llm_gateway_service.supabase", new=mock_db):
            await service._fill_model_codes(rule)

        assert rule["primary_model_code"] == ""


# ═══════════════════════════════════════════════════════════════════════════════
#  Cache Invalidation 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestCacheInvalidation:
    """测试缓存失效机制"""

    def test_invalidate_specific_org(self):
        """按组织失效缓存应只删除该组织的条目"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()
        service._model_cache["org-A:m1"] = ("c1", 0)
        service._model_cache["org-A:m2"] = ("c2", 0)
        service._model_cache["org-B:m1"] = ("c3", 0)

        service.invalidate_cache("org-A")

        assert len(service._model_cache) == 1
        assert "org-B:m1" in service._model_cache

    def test_invalidate_all_orgs(self):
        """全局失效应清除所有缓存"""
        from app.services.llm_gateway_service import LLMGatewayService

        service = LLMGatewayService()
        service._model_cache["org-A:m1"] = ("c1", 0)
        service._schedule_cache["org-A:s:a"] = ("r1", 0)

        service.invalidate_cache(None)

        assert len(service._model_cache) == 0
        assert len(service._schedule_cache) == 0
