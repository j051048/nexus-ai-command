"""
APIKeyService 单元测试
覆盖: Key 生成/哈希/创建/验证/撤销/用量统计
"""

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.api_key_service import APIKeyService, API_KEY_PREFIX


# ─── Key Generation ────────────────────────────────────────────


class TestKeyGeneration:
    """API Key 生成测试"""

    def test_key_starts_with_prefix(self):
        key = APIKeyService._generate_key()
        assert key.startswith(API_KEY_PREFIX)

    def test_key_has_sufficient_length(self):
        key = APIKeyService._generate_key()
        assert len(key) > 10

    def test_keys_are_unique(self):
        keys = {APIKeyService._generate_key() for _ in range(100)}
        assert len(keys) == 100


# ─── Key Hashing ───────────────────────────────────────────────


class TestKeyHashing:
    """Key 哈希测试"""

    def test_hash_is_sha256(self):
        key = "sk-test-key-123"
        expected = hashlib.sha256(key.encode("utf-8")).hexdigest()
        assert APIKeyService._hash_key(key) == expected

    def test_same_key_same_hash(self):
        key = "sk-consistent"
        assert APIKeyService._hash_key(key) == APIKeyService._hash_key(key)

    def test_different_keys_different_hashes(self):
        assert APIKeyService._hash_key("sk-a") != APIKeyService._hash_key("sk-b")

    def test_get_prefix(self):
        assert APIKeyService._get_prefix("sk-abcdef123") == "sk-abcde"
        assert APIKeyService._get_prefix("short") == "short"


# ─── Create API Key ────────────────────────────────────────────


class TestCreateApiKey:
    """API Key 创建测试"""

    def setup_method(self):
        self.svc = APIKeyService()

    @pytest.mark.asyncio
    async def test_create_success(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = [{"id": "key-1", "created_at": "2026-01-01T00:00:00Z"}]
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(return_value=resp)

        result = await self.svc.create_api_key(
            org_id="org-1", name="Test Key", scopes=["read"], db=mock_db
        )
        assert result["name"] == "Test Key"
        assert result["key"].startswith("sk-")
        assert "warning" in result

    @pytest.mark.asyncio
    async def test_create_no_db_raises(self):
        with pytest.raises(RuntimeError, match="数据库"):
            await self.svc.create_api_key("org-1", "Test", ["read"], db=None)

    @pytest.mark.asyncio
    async def test_create_db_returns_empty_raises(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = []
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(return_value=resp)

        with pytest.raises(RuntimeError):
            await self.svc.create_api_key("org-1", "Test", ["read"], db=mock_db)


# ─── Validate API Key ──────────────────────────────────────────


class TestValidateApiKey:
    """API Key 验证测试"""

    def setup_method(self):
        self.svc = APIKeyService()

    @pytest.mark.asyncio
    async def test_valid_key(self):
        key = "sk-test-valid-key"
        key_hash = APIKeyService._hash_key(key)
        future = (datetime.now(UTC) + timedelta(days=30)).isoformat()

        mock_db = MagicMock()
        select_resp = MagicMock()
        select_resp.data = {
            "id": "key-1",
            "key_hash": key_hash,
            "organization_id": "org-1",
            "name": "Test",
            "scopes": ["read", "write"],
            "is_active": True,
            "expires_at": future,
            "key_prefix": "sk-test-",
            "usage_count": 5,
            "created_by": "user-1",
        }
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=select_resp)
        mock_db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()

        result = await self.svc.validate_api_key(key, db=mock_db)
        assert result is not None
        assert result["key_id"] == "key-1"
        assert result["organization_id"] == "org-1"

    @pytest.mark.asyncio
    async def test_expired_key_returns_none(self):
        key = "sk-expired"
        past = (datetime.now(UTC) - timedelta(days=1)).isoformat()

        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = {
            "id": "key-1", "key_hash": APIKeyService._hash_key(key),
            "scopes": ["read"], "is_active": True, "expires_at": past,
            "key_prefix": "sk-expir", "usage_count": 0,
        }
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        result = await self.svc.validate_api_key(key, db=mock_db)
        assert result is None

    @pytest.mark.asyncio
    async def test_scope_mismatch_returns_none(self):
        key = "sk-limited"
        future = (datetime.now(UTC) + timedelta(days=30)).isoformat()

        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = {
            "id": "key-1", "key_hash": APIKeyService._hash_key(key),
            "scopes": ["read"], "is_active": True, "expires_at": future,
            "key_prefix": "sk-limit", "usage_count": 0,
        }
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        result = await self.svc.validate_api_key(key, required_scope="admin", db=mock_db)
        assert result is None

    @pytest.mark.asyncio
    async def test_admin_scope_bypasses_check(self):
        key = "sk-admin"
        future = (datetime.now(UTC) + timedelta(days=30)).isoformat()

        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = {
            "id": "key-1", "key_hash": APIKeyService._hash_key(key),
            "scopes": ["admin"], "is_active": True, "expires_at": future,
            "key_prefix": "sk-admin", "usage_count": 0, "organization_id": "org-1",
            "name": "Admin", "created_by": "u1",
        }
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)
        mock_db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()

        result = await self.svc.validate_api_key(key, required_scope="write", db=mock_db)
        assert result is not None

    @pytest.mark.asyncio
    async def test_key_not_found_returns_none(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = None
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        result = await self.svc.validate_api_key("sk-nonexistent", db=mock_db)
        assert result is None


# ─── Revoke / List ─────────────────────────────────────────────


class TestRevokeAndList:
    """撤销和列表测试"""

    def setup_method(self):
        self.svc = APIKeyService()

    @pytest.mark.asyncio
    async def test_revoke_success(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = [{"id": "key-1", "is_active": False}]
        mock_db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock(return_value=resp)

        assert await self.svc.revoke_api_key("key-1", db=mock_db) is True

    @pytest.mark.asyncio
    async def test_revoke_not_found(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = []
        mock_db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock(return_value=resp)

        assert await self.svc.revoke_api_key("ghost", db=mock_db) is False

    @pytest.mark.asyncio
    async def test_revoke_no_db_raises(self):
        with pytest.raises(RuntimeError):
            await self.svc.revoke_api_key("key-1", db=None)

    @pytest.mark.asyncio
    async def test_list_keys(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = [
            {"id": "k1", "name": "Key 1", "key_prefix": "sk-k1xxx"},
            {"id": "k2", "name": "Key 2", "key_prefix": "sk-k2xxx"},
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(return_value=resp)

        result = await self.svc.list_api_keys("org-1", db=mock_db)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_no_db_raises(self):
        with pytest.raises(RuntimeError):
            await self.svc.list_api_keys("org-1", db=None)


# ─── Usage Logging ─────────────────────────────────────────────


class TestApiUsage:
    """API 使用统计测试"""

    def setup_method(self):
        self.svc = APIKeyService()

    @pytest.mark.asyncio
    async def test_log_usage(self):
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        await self.svc.log_api_usage("key-1", "/api/test", "GET", 200, 50, db=mock_db)
        mock_db.table.assert_called_with("api_usage_logs")

    @pytest.mark.asyncio
    async def test_log_usage_no_db_silent(self):
        """无 DB 时静默返回"""
        with patch("app.core.database.supabase", None):
            await self.svc.log_api_usage("key-1", "/api/test", "GET", 200, 50, db=None)

    @pytest.mark.asyncio
    async def test_get_usage_stats(self):
        mock_db = MagicMock()
        key_resp = MagicMock()
        key_resp.data = {"id": "key-1", "name": "Test", "key_prefix": "sk-test", "usage_count": 10, "last_used_at": None, "created_at": "2026-01-01"}
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(return_value=key_resp)

        logs_resp = MagicMock()
        logs_resp.data = [
            {"endpoint": "/api/a", "status_code": 200, "response_time_ms": 100},
            {"endpoint": "/api/a", "status_code": 500, "response_time_ms": 200},
            {"endpoint": "/api/b", "status_code": 200, "response_time_ms": 50},
        ]
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute = AsyncMock(return_value=logs_resp)

        result = await self.svc.get_api_usage("key-1", db=mock_db)
        assert result["period_calls"] == 3
        assert result["success_calls"] == 2
        assert result["error_calls"] == 1

    @pytest.mark.asyncio
    async def test_get_usage_no_db_raises(self):
        with pytest.raises(RuntimeError):
            await self.svc.get_api_usage("key-1", db=None)
