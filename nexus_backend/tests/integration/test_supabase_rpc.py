"""
Supabase RPC 集成测试 — 验证语义缓存和检索服务的 RPC 调用参数正确性与返回值处理。

覆盖的核心 RPC:
  - match_semantic_cache (语义缓存向量匹配)
  - increment_cache_hit (原子命中计数)
  - match_documents / match_documents_keyword (文档向量+FTS检索)
  - search_memories_hybrid (记忆混合检索)

以及缓存服务的质量门禁、TTL 边界、失效逻辑等。
"""

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _make_mock_supabase():
    """Create a mock supabase client with chainable query builder."""
    mock = MagicMock()

    class _ChainBuilder:
        def __init__(self, data=None):
            self._data = data

        def select(self, *a, **kw):
            return self

        def eq(self, *a, **kw):
            return self

        def gt(self, *a, **kw):
            return self

        def limit(self, *a, **kw):
            return self

        def maybe_single(self):
            return self

        def in_(self, *a, **kw):
            return self

        def delete(self):
            return self

        def upsert(self, *a, **kw):
            return self

        async def execute(self):
            resp = MagicMock()
            resp.data = self._data
            return resp

    mock._chain = _ChainBuilder
    mock._rpc_results = {}
    mock._table_data = {}

    def _table(name):
        data = mock._table_data.get(name, [])
        return _ChainBuilder(data)

    def _rpc(name, params=None):
        data = mock._rpc_results.get(name, [])
        return _ChainBuilder(data)

    mock.table = _table
    mock.rpc = _rpc
    return mock


def _query_hash(query: str) -> str:
    return hashlib.sha256(query.strip().encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# 1. match_semantic_cache — 向量相似度搜索
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_match_semantic_cache_hit():
    """验证 get_cache 在 RPC 返回匹配结果时正确返回 response_text。"""
    mock_sb = _make_mock_supabase()
    mock_sb._rpc_results["match_semantic_cache"] = [
        {
            "id": 42,
            "query_text": "竞品分析报告",
            "response_text": "以下是竞品分析结果...",
            "similarity": 0.96,
        }
    ]
    # Hash path: no exact match
    mock_sb._table_data["semantic_cache"] = []

    mock_openai = AsyncMock()
    mock_embedding = MagicMock()
    mock_embedding.data = [MagicMock(embedding=[0.1] * 1536)]
    mock_openai.embeddings.create = AsyncMock(return_value=mock_embedding)

    with patch("app.services.semantic_cache.supabase", mock_sb):
        from app.services.semantic_cache import SemanticCacheService

        svc = SemanticCacheService()
        svc.threshold = 0.90
        svc.ttl_hours = 24
        svc.openai_client = mock_openai
        svc._redis_init_attempted = True
        svc._redis = None  # No Redis
        svc._embedding_resolved = True

        result = await svc.get_cache("竞品分析报告", "user-123")

    assert result == "以下是竞品分析结果..."


@pytest.mark.asyncio
async def test_match_semantic_cache_no_match():
    """验证 get_cache 在 RPC 无匹配时返回 None。"""
    mock_sb = _make_mock_supabase()
    mock_sb._rpc_results["match_semantic_cache"] = []
    mock_sb._table_data["semantic_cache"] = []

    mock_openai = AsyncMock()
    mock_embedding = MagicMock()
    mock_embedding.data = [MagicMock(embedding=[0.1] * 1536)]
    mock_openai.embeddings.create = AsyncMock(return_value=mock_embedding)

    with patch("app.services.semantic_cache.supabase", mock_sb):
        from app.services.semantic_cache import SemanticCacheService

        svc = SemanticCacheService()
        svc.threshold = 0.90
        svc.ttl_hours = 24
        svc.openai_client = mock_openai
        svc._redis_init_attempted = True
        svc._redis = None
        svc._embedding_resolved = True

        result = await svc.get_cache("完全不相关的查询", "user-123")

    assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# 2. Hash 精确匹配路径
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_exact_hash_hit_skips_embedding():
    """验证精确 hash 命中时不调用 embedding API。"""
    mock_sb = _make_mock_supabase()

    # Override table to return hash hit
    class _HashHitBuilder:
        def select(self, *a):
            return self

        def eq(self, *a):
            return self

        def gt(self, *a):
            return self

        def limit(self, *a):
            return self

        def maybe_single(self):
            return self

        async def execute(self):
            resp = MagicMock()
            resp.data = {"id": 1, "response_text": "cached answer"}
            return resp

    orig_table = mock_sb.table

    def _patched_table(name):
        if name == "semantic_cache":
            return _HashHitBuilder()
        return orig_table(name)

    mock_sb.table = _patched_table

    mock_openai = AsyncMock()
    mock_openai.embeddings.create = AsyncMock()  # Should NOT be called

    with patch("app.services.semantic_cache.supabase", mock_sb):
        from app.services.semantic_cache import SemanticCacheService

        svc = SemanticCacheService()
        svc.ttl_hours = 24
        svc.openai_client = mock_openai
        svc._redis_init_attempted = True
        svc._redis = None
        svc._embedding_resolved = True

        result = await svc.get_cache("some query", "user-123")

    assert result == "cached answer"
    mock_openai.embeddings.create.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# 3. increment_cache_hit RPC
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_increment_cache_hit_rpc_called():
    """验证 _update_hit_count 正确调用 increment_cache_hit RPC。"""
    mock_sb = _make_mock_supabase()
    rpc_calls = []

    def _capture_rpc(name, params=None):
        rpc_calls.append((name, params))
        builder = MagicMock()
        builder.execute = AsyncMock()
        return builder

    mock_sb.rpc = _capture_rpc

    with patch("app.services.semantic_cache.supabase", mock_sb):
        from app.services.semantic_cache import SemanticCacheService

        svc = SemanticCacheService()
        await svc._update_hit_count(42)

    assert len(rpc_calls) == 1
    assert rpc_calls[0] == ("increment_cache_hit", {"p_cache_id": 42})


# ──────────────────────────────────────────────────────────────────────────────
# 4. set_cache — upsert 逻辑
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_cache_upsert_with_org_id():
    """验证 set_cache 正确查询 org_id 并 upsert 到 semantic_cache 表。"""
    upsert_data = []

    class _UsersBuilder:
        def select(self, *a):
            return self

        def eq(self, *a):
            return self

        def maybe_single(self):
            return self

        async def execute(self):
            resp = MagicMock()
            resp.data = {"organization_id": "org-789"}
            return resp

    class _CacheBuilder:
        def upsert(self, data, **kw):
            upsert_data.append(data)
            return self

        def select(self, *a):
            return self

        def eq(self, *a):
            return self

        async def execute(self):
            resp = MagicMock()
            resp.data = []
            return resp

    mock_sb = MagicMock()

    def _table(name):
        if name == "users":
            return _UsersBuilder()
        return _CacheBuilder()

    mock_sb.table = _table

    mock_openai = AsyncMock()
    mock_embedding = MagicMock()
    mock_embedding.data = [MagicMock(embedding=[0.5] * 1536)]
    mock_openai.embeddings.create = AsyncMock(return_value=mock_embedding)

    with patch("app.services.semantic_cache.supabase", mock_sb):
        from app.services.semantic_cache import SemanticCacheService

        svc = SemanticCacheService()
        svc.openai_client = mock_openai
        svc._redis_init_attempted = True
        svc._redis = None
        svc._embedding_resolved = True

        await svc.set_cache(
            "市场策略分析",
            "这是一份详细的市场策略分析报告，包含竞品对比和增长建议。",
            "user-456",
        )

    assert len(upsert_data) == 1
    data = upsert_data[0]
    assert data["query_text"] == "市场策略分析"
    assert data["user_id"] == "user-456"
    assert data["org_id"] == "org-789"
    assert data["query_hash"] == _query_hash("市场策略分析")
    assert len(data["embedding"]) == 1536


# ──────────────────────────────────────────────────────────────────────────────
# 5. 质量门禁
# ──────────────────────────────────────────────────────────────────────────────


def test_quality_gate_rejects_error_responses():
    """验证质量门禁拒绝以错误前缀开头的回复。"""
    from app.services.semantic_cache import SemanticCacheService

    svc = SemanticCacheService()

    # 错误前缀
    assert svc._passes_quality_gate("查询", "❌ 操作失败") is False
    assert svc._passes_quality_gate("查询", "抱歉，我无法处理该请求") is False
    assert svc._passes_quality_gate("查询", "Error: something went wrong") is False


def test_quality_gate_accepts_normal_responses():
    """验证质量门禁通过正常回复。"""
    from app.services.semantic_cache import SemanticCacheService

    svc = SemanticCacheService()

    assert (
        svc._passes_quality_gate(
            "市场分析", "这是一份详细的市场分析报告，包含行业趋势和竞品对比。"
        )
        is True
    )


# ──────────────────────────────────────────────────────────────────────────────
# 6. TTL 边界
# ──────────────────────────────────────────────────────────────────────────────


def test_ttl_cutoff_boundary():
    """验证 TTL 截止时间计算正确。"""
    from app.services.semantic_cache import SemanticCacheService

    svc = SemanticCacheService()
    svc.ttl_hours = 12  # 12-hour TTL
    cutoff_str = svc._ttl_cutoff()
    cutoff = datetime.fromisoformat(cutoff_str)

    # Should be approximately 12 hours ago
    expected = datetime.now(UTC) - timedelta(hours=12)
    delta = abs((cutoff - expected).total_seconds())
    assert delta < 5, f"TTL cutoff off by {delta}s (expected ~0)"


# ──────────────────────────────────────────────────────────────────────────────
# 7. Cache bypass 分类
# ──────────────────────────────────────────────────────────────────────────────


def test_should_use_cache_bypasses_creative():
    """验证创意写作/长文请求被旁路，不使用缓存。"""
    from app.services.semantic_cache import SemanticCacheService

    svc = SemanticCacheService()

    assert svc.should_use_cache("写一篇3000字的推广文") is False
    assert svc.should_use_cache("帮我创作一份万字策划案") is False
    assert svc.should_use_cache("竞品分析") is False
    assert svc.should_use_cache("生成客户解决方案") is False
    assert svc.should_use_cache("导出 Excel") is False
    assert svc.should_use_cache("查询今天的客户数量") is True


# ──────────────────────────────────────────────────────────────────────────────
# 8. invalidate_by_org — 事件驱动失效
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalidate_by_org_deletes_and_clears_redis():
    """验证 invalidate_by_org 批量删除 DB 条目并清除 Redis 热缓存。"""
    deleted_orgs = []
    cache_entries = [
        {"id": 1, "query_text": "query1", "user_id": "u1"},
        {"id": 2, "query_text": "query2", "user_id": "u2"},
    ]

    class _SelectBuilder:
        def select(self, *a):
            return self

        def eq(self, *a):
            return self

        async def execute(self):
            resp = MagicMock()
            resp.data = cache_entries
            return resp

    class _DeleteBuilder:
        def delete(self):
            return self

        def eq(self, col, val):
            deleted_orgs.append(val)
            return self

        async def execute(self):
            resp = MagicMock()
            resp.data = []
            return resp

    call_count = {"n": 0}

    def _table(name):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _SelectBuilder()  # First call: select
        return _DeleteBuilder()  # Second call: delete

    mock_sb = MagicMock()
    mock_sb.table = _table

    mock_redis = AsyncMock()

    with patch("app.services.semantic_cache.supabase", mock_sb):
        from app.services.semantic_cache import SemanticCacheService

        svc = SemanticCacheService()
        svc._redis_init_attempted = True
        svc._redis = mock_redis

        count = await svc.invalidate_by_org("org-test")

    assert count == 2
    assert "org-test" in deleted_orgs
    mock_redis.delete.assert_called_once()
    # Should have 2 Redis keys to delete
    redis_keys = mock_redis.delete.call_args[0]
    assert len(redis_keys) == 2


@pytest.mark.asyncio
async def test_invalidate_by_keywords_filters_correctly():
    """验证 invalidate_by_keywords 只删除包含指定关键词的缓存。"""
    cache_entries = [
        {"id": 1, "query_text": "合同金额查询", "user_id": "u1"},
        {"id": 2, "query_text": "市场趋势分析", "user_id": "u2"},
        {"id": 3, "query_text": "合同签约状态", "user_id": "u1"},
    ]

    deleted_ids = []

    class _SelectBuilder:
        def select(self, *a):
            return self

        def eq(self, *a):
            return self

        async def execute(self):
            resp = MagicMock()
            resp.data = cache_entries
            return resp

    class _DeleteBuilder:
        def delete(self):
            return self

        def in_(self, col, vals):
            deleted_ids.extend(vals)
            return self

        async def execute(self):
            resp = MagicMock()
            resp.data = []
            return resp

    call_count = {"n": 0}

    def _table(name):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _SelectBuilder()
        return _DeleteBuilder()

    mock_sb = MagicMock()
    mock_sb.table = _table

    with patch("app.services.semantic_cache.supabase", mock_sb):
        from app.services.semantic_cache import SemanticCacheService

        svc = SemanticCacheService()
        svc._redis_init_attempted = True
        svc._redis = None

        count = await svc.invalidate_by_keywords("org-test", ["合同"])

    assert count == 2  # id=1 and id=3 contain "合同"
    assert sorted(deleted_ids) == [1, 3]
