"""
PermissionService 单元测试
覆盖: 权限缓存、角色层级、权限检查、条件评估、用户权限列表
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.permission_service import (
    PermissionCache,
    PermissionResult,
    PermissionService,
)

# ─── PermissionCache ───────────────────────────────────────────


class TestPermissionCache:
    """PermissionCache 内存缓存测试"""

    def test_set_and_get(self):
        cache = PermissionCache(ttl_seconds=60)
        cache.set("k1", {"role": "admin"})
        assert cache.get("k1") == {"role": "admin"}

    def test_get_missing_key_returns_none(self):
        cache = PermissionCache()
        assert cache.get("nonexistent") is None

    def test_ttl_expiry(self):
        cache = PermissionCache(ttl_seconds=1)
        cache.set("k1", "val")
        # Simulate time passing
        cache._timestamps["k1"] = time.time() - 2
        assert cache.get("k1") is None
        assert "k1" not in cache._cache

    def test_max_entries_eviction(self):
        cache = PermissionCache(ttl_seconds=60)
        cache._max_entries = 3
        for i in range(4):
            cache.set(f"k{i}", f"v{i}")
            # Stagger timestamps so oldest is deterministic
            cache._timestamps[f"k{i}"] = time.time() + i * 0.001
        # k0 should have been evicted (oldest timestamp)
        assert cache.get("k0") is None
        assert cache.get("k3") == "v3"

    def test_invalidate_key(self):
        cache = PermissionCache()
        cache.set("k1", "v1")
        cache.invalidate("k1")
        assert cache.get("k1") is None

    def test_invalidate_user(self):
        cache = PermissionCache()
        cache.set("user:u1:info", "data1")
        cache.set("user:u1:perms", "data2")
        cache.set("user:u2:info", "data3")
        cache.invalidate_user("u1")
        assert cache.get("user:u1:info") is None
        assert cache.get("user:u1:perms") is None
        assert cache.get("user:u2:info") == "data3"

    def test_clear(self):
        cache = PermissionCache()
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.clear()
        assert cache.get("k1") is None
        assert cache.get("k2") is None


# ─── Role Hierarchy ────────────────────────────────────────────


class TestRoleHierarchy:
    """角色层级继承测试"""

    def setup_method(self):
        self.svc = PermissionService()

    def test_founder_outranks_all(self):
        assert self.svc._role_has_hierarchy_access("founder", ["employee"]) is True
        assert self.svc._role_has_hierarchy_access("founder", ["boss"]) is True

    def test_boss_outranks_manager_and_employee(self):
        assert self.svc._role_has_hierarchy_access("boss", ["manager"]) is True
        assert self.svc._role_has_hierarchy_access("boss", ["employee"]) is True

    def test_employee_cannot_access_manager(self):
        assert self.svc._role_has_hierarchy_access("employee", ["manager"]) is False

    def test_guest_has_no_hierarchy_access(self):
        assert self.svc._role_has_hierarchy_access("guest", ["employee"]) is False

    def test_unknown_role_has_no_access(self):
        assert self.svc._role_has_hierarchy_access("unknown_role", ["employee"]) is False

    def test_get_role_permissions_founder_has_all(self):
        perms = self.svc.get_role_permissions("founder")
        all_perms = list(self.svc.PERMISSION_RULES.keys())
        assert set(perms) == set(all_perms)

    def test_get_role_permissions_employee_subset(self):
        perms = self.svc.get_role_permissions("employee")
        assert "approval.create" in perms
        assert "settings.manage" not in perms


# ─── Static Methods ────────────────────────────────────────────


class TestStaticMethods:
    """不依赖 DB 的静态方法测试"""

    def setup_method(self):
        self.svc = PermissionService()

    def test_get_all_permissions_returns_list(self):
        result = self.svc.get_all_permissions()
        assert isinstance(result, list)
        assert len(result) > 0
        first = result[0]
        assert "permission" in first
        assert "roles" in first
        assert "description" in first


# ─── check_permission ──────────────────────────────────────────


class TestCheckPermission:
    """核心权限检查测试"""

    def setup_method(self):
        self.svc = PermissionService()
        self.svc.clear_cache()

    @pytest.mark.asyncio
    async def test_admin_role_via_founder(self):
        """founder 角色应拥有所有权限"""
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = {"id": "u1", "role": "founder", "department": "exec"}
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        result = await self.svc.check_permission("u1", "settings.manage", db=mock_db)
        assert result is True

    @pytest.mark.asyncio
    async def test_employee_restricted(self):
        """employee 不能管理系统设置"""
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = {"id": "u1", "role": "employee", "department": "sales"}
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        result = await self.svc.check_permission("u1", "settings.manage", db=mock_db)
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_permission_denied(self):
        """未知权限标识应返回 False"""
        mock_db = MagicMock()
        result = await self.svc.check_permission("u1", "nonexistent.perm", db=mock_db)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_db_returns_false(self):
        """无数据库连接应返回 False"""
        with patch("app.services.permission_service.supabase", None):
            result = await self.svc.check_permission("u1", "approval.create", db=None)
            assert result is False

    @pytest.mark.asyncio
    async def test_user_not_found_returns_false(self):
        """用户不存在应返回 False"""
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = None
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        result = await self.svc.check_permission("ghost", "approval.create", db=mock_db)
        assert result is False

    @pytest.mark.asyncio
    async def test_db_exception_returns_false(self):
        """DB 异常应返回 False (fail-closed)"""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(side_effect=Exception("DB down"))

        result = await self.svc.check_permission("u1", "approval.create", db=mock_db)
        assert result is False


# ─── check_permission_detailed ─────────────────────────────────


class TestCheckPermissionDetailed:
    """详细权限检查测试"""

    def setup_method(self):
        self.svc = PermissionService()
        self.svc.clear_cache()

    @pytest.mark.asyncio
    async def test_returns_permission_result(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = {"id": "u1", "role": "boss", "department": "sales"}
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        result = await self.svc.check_permission_detailed("u1", "approval.create", db=mock_db)
        assert isinstance(result, PermissionResult)
        assert result.granted is True
        assert result.reason == "权限通过"

    @pytest.mark.asyncio
    async def test_unknown_permission_detailed(self):
        mock_db = MagicMock()
        result = await self.svc.check_permission_detailed("u1", "fake.perm", db=mock_db)
        assert result.granted is False
        assert "未知权限" in result.reason

    @pytest.mark.asyncio
    async def test_no_db_detailed(self):
        with patch("app.services.permission_service.supabase", None):
            result = await self.svc.check_permission_detailed("u1", "approval.create", db=None)
            assert result.granted is False
            assert "数据库" in result.reason

    @pytest.mark.asyncio
    async def test_role_denied_detailed(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = {"id": "u1", "role": "employee"}
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        result = await self.svc.check_permission_detailed("u1", "settings.manage", db=mock_db)
        assert result.granted is False
        assert "角色" in result.reason


# ─── Condition Evaluation ──────────────────────────────────────


class TestConditionEvaluation:
    """条件评估测试"""

    def setup_method(self):
        self.svc = PermissionService()
        self.svc.clear_cache()

    @pytest.mark.asyncio
    async def test_is_self_condition(self):
        result = await self.svc._evaluate_condition(
            "is_self", "u1", {"id": "u1"}, {"user_id": "u1"}, MagicMock()
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_is_self_condition_different_user(self):
        result = await self.svc._evaluate_condition(
            "is_self", "u1", {"id": "u1"}, {"user_id": "u2"}, MagicMock()
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_is_owner_from_resource(self):
        result = await self.svc._evaluate_condition(
            "is_owner", "u1", {}, {"created_by": "u1"}, MagicMock()
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_is_owner_not_owner(self):
        result = await self.svc._evaluate_condition(
            "is_owner", "u1", {}, {"created_by": "u2"}, MagicMock()
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_same_department_match(self):
        result = await self.svc._evaluate_condition(
            "same_department", "u1",
            {"department": "sales"},
            {"department": "sales"},
            MagicMock(),
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_same_department_no_dept(self):
        result = await self.svc._evaluate_condition(
            "same_department", "u1", {}, {"department": "sales"}, MagicMock()
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_is_approver_found(self):
        mock_db = MagicMock()
        step_resp = MagicMock()
        step_resp.data = {"id": "step-1"}
        mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=step_resp)

        result = await self.svc._evaluate_condition(
            "is_approver", "u1", {}, {"approval_id": "req-1"}, mock_db
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_unknown_condition_returns_false(self):
        result = await self.svc._evaluate_condition(
            "unknown_cond", "u1", {}, {}, MagicMock()
        )
        assert result is False


# ─── get_user_permissions ──────────────────────────────────────


class TestGetUserPermissions:
    """用户权限列表测试"""

    def setup_method(self):
        self.svc = PermissionService()
        self.svc.clear_cache()

    @pytest.mark.asyncio
    async def test_returns_permissions_list(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = {"id": "u1", "role": "manager"}
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        perms = await self.svc.get_user_permissions("u1", db=mock_db)
        assert isinstance(perms, list)
        assert len(perms) > 0
        assert all("permission" in p and "granted" in p for p in perms)

    @pytest.mark.asyncio
    async def test_no_db_returns_empty(self):
        with patch("app.services.permission_service.supabase", None):
            perms = await self.svc.get_user_permissions("u1", db=None)
            assert perms == []

    @pytest.mark.asyncio
    async def test_user_not_found_returns_empty(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = None
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        perms = await self.svc.get_user_permissions("ghost", db=mock_db)
        assert perms == []


# ─── Cache Integration ─────────────────────────────────────────


class TestCacheIntegration:
    """缓存与权限检查集成测试"""

    def setup_method(self):
        self.svc = PermissionService()
        self.svc.clear_cache()

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self):
        mock_db = MagicMock()
        resp = MagicMock()
        resp.data = {"id": "u1", "role": "boss", "department": "exec"}
        mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(return_value=resp)

        await self.svc.check_permission("u1", "approval.create", db=mock_db)
        # Second call should use cache, not hit DB again
        await self.svc.check_permission("u1", "approval.view", db=mock_db)
        # DB should only be called once for user info
        assert mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.call_count == 1

    def test_invalidate_user_cache(self):
        self.svc._cache.set("user:u1:info", {"role": "employee"})
        self.svc.invalidate_user_cache("u1")
        assert self.svc._cache.get("user:u1:info") is None
