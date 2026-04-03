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
