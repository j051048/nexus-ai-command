"""Comprehensive tests for conversation memory system: extraction, retrieval, cleanup, conflict resolution."""

import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, UTC, timedelta


# ════════════════════════════════════════════════════════════════
# Section 1: Extraction
# ════════════════════════════════════════════════════════════════


class TestExtractPreferences:
    """Tests for extract_preferences() — dual-engine extraction (regex + LLM)."""

    @pytest.mark.asyncio
    async def test_likes_pattern_extracted(self):
        """'我喜欢用表格展示数据' should match the likes pattern."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "我喜欢用表格展示数据"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m1", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        assert len(result) >= 1
        call_kwargs = save_fn.call_args_list[0].kwargs
        assert call_kwargs["category"] == "preference"
        assert call_kwargs["key"].startswith("likes_")

    @pytest.mark.asyncio
    async def test_remember_pattern_extracted(self):
        """'记住我的工号是A12345' should match explicit_memory with remember prefix."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "记住我的工号是A12345"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m2", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        # Should have at least one explicit_memory entry with remember prefix
        remember_calls = [
            c for c in save_fn.call_args_list
            if c.kwargs.get("category") == "explicit_memory" and c.kwargs.get("key", "").startswith("remember_")
        ]
        assert len(remember_calls) >= 1

    @pytest.mark.asyncio
    async def test_dislikes_pattern_extracted(self):
        """'不要给我发英文报告' should match dislikes pattern."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "不要给我发英文报告"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m3", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        dislike_calls = [
            c for c in save_fn.call_args_list
            if c.kwargs.get("key", "").startswith("dislikes_")
        ]
        assert len(dislike_calls) >= 1

    @pytest.mark.asyncio
    async def test_identity_pattern_extracted(self):
        """'我是华东区销售总监' should match identity pattern."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "我是华东区销售总监"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m4", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        identity_calls = [
            c for c in save_fn.call_args_list
            if c.kwargs.get("key", "").startswith("identity_")
        ]
        assert len(identity_calls) >= 1

    @pytest.mark.asyncio
    async def test_routine_pattern_extracted(self):
        """'以后都用markdown格式' should match routine pattern."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "以后都用markdown格式回复"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m5", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        routine_calls = [
            c for c in save_fn.call_args_list
            if c.kwargs.get("key", "").startswith("routine_")
        ]
        assert len(routine_calls) >= 1

    @pytest.mark.asyncio
    async def test_contact_pattern_extracted(self):
        """'我的邮箱是test@example.com' should match contact pattern."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "我的邮箱是test@example.com"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m6", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        contact_calls = [
            c for c in save_fn.call_args_list
            if c.kwargs.get("key", "").startswith("contact_")
        ]
        assert len(contact_calls) >= 1

    @pytest.mark.asyncio
    async def test_correction_pattern_extracted(self):
        """'你又忘了我说的要求' should match anti_pattern correction."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [
            {"role": "assistant", "content": "这是之前的回复内容"},
            {"role": "user", "content": "你又忘了我说的要求不要用英文"},
        ]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m7", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        correction_calls = [
            c for c in save_fn.call_args_list
            if c.kwargs.get("category") == "anti_pattern"
        ]
        assert len(correction_calls) >= 1

    @pytest.mark.asyncio
    async def test_tool_usage_approval_detected(self):
        """Message containing '审批' should produce usage_pattern with action approval."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "帮我提交一下审批流程"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m8", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        usage_calls = [
            c for c in save_fn.call_args_list
            if c.kwargs.get("key") == "usage_approval"
        ]
        assert len(usage_calls) == 1

    @pytest.mark.asyncio
    async def test_tool_usage_report_detected(self):
        """Message containing '报表' should produce usage_pattern with action report."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "帮我生成一份报表"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m9", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        usage_calls = [
            c for c in save_fn.call_args_list
            if c.kwargs.get("key") == "usage_report"
        ]
        assert len(usage_calls) == 1

    @pytest.mark.asyncio
    async def test_no_duplicate_usage_patterns_in_batch(self):
        """Repeated keyword '审批' in one message should yield only 1 usage_pattern entry."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "审批审批审批这个审批需要处理"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m10", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        usage_calls = [
            c for c in save_fn.call_args_list
            if c.kwargs.get("key") == "usage_approval"
        ]
        assert len(usage_calls) == 1

    @pytest.mark.asyncio
    async def test_assistant_messages_ignored(self):
        """Assistant messages should not trigger extraction even with matching patterns."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "assistant", "content": "我喜欢用表格展示数据"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m11", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        save_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_short_match_ignored(self):
        """Matches shorter than 2 characters should be ignored."""
        from app.services.conversation_memory.extraction import extract_preferences

        # "我喜欢a" — the match after "我喜欢" is "a" which is only 1 char
        msgs = [{"role": "user", "content": "我喜欢a"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m12", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)

        likes_calls = [
            c for c in save_fn.call_args_list
            if c.kwargs.get("key", "").startswith("likes_")
        ]
        assert len(likes_calls) == 0

    @pytest.mark.asyncio
    async def test_is_subtask_skips_llm_extraction(self):
        """When is_subtask=True, LLM extraction should be skipped even with signal words."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "请记住以后每次都用中文回复我的消息"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "m13", **kw})

        with patch(
            "app.services.conversation_memory.extraction.extract_with_llm",
            new_callable=AsyncMock,
        ) as mock_llm, patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, save_memory_fn=save_fn, is_subtask=True)
            mock_llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_memory_fn_callback_called(self):
        """save_memory_fn should be called for each extracted entry with correct params."""
        from app.services.conversation_memory.extraction import extract_preferences

        msgs = [{"role": "user", "content": "我喜欢用深色主题"}]
        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "saved1", **kw})

        with patch(
            "app.services.conversation_memory.extraction._enrich_memory_values",
            new_callable=AsyncMock,
            side_effect=lambda entries, msgs: entries,
        ):
            result = await extract_preferences("u1", msgs, org_id="org1", save_memory_fn=save_fn, is_subtask=True)

        assert save_fn.call_count >= 1
        kw = save_fn.call_args_list[0].kwargs
        assert kw["user_id"] == "u1"
        assert kw["org_id"] == "org1"
        assert "value" in kw
        assert "category" in kw


class TestExtractWithLLM:
    """Tests for extract_with_llm() — LLM-based extraction."""

    @pytest.mark.asyncio
    async def test_empty_messages_returns_empty(self):
        """No user messages should return empty list without LLM call."""
        from app.services.conversation_memory.extraction import extract_with_llm

        result = await extract_with_llm([])
        assert result == []

    @pytest.mark.asyncio
    async def test_only_assistant_messages_returns_empty(self):
        """Only assistant messages should return empty list."""
        from app.services.conversation_memory.extraction import extract_with_llm

        result = await extract_with_llm([{"role": "assistant", "content": "你好"}])
        assert result == []

    @pytest.mark.asyncio
    async def test_short_content_returns_empty(self):
        """Content shorter than 10 chars combined should return empty."""
        from app.services.conversation_memory.extraction import extract_with_llm

        result = await extract_with_llm([{"role": "user", "content": "好"}])
        assert result == []


class TestExtractOrgMemories:
    """Tests for extract_org_memories() — org-level memory extraction."""

    @pytest.mark.asyncio
    async def test_company_rule_extracted(self):
        """'我们公司规定每月15号发工资' should be extracted as org preference."""
        from app.services.conversation_memory.extraction import extract_org_memories

        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "org_m1", **kw})
        result = await extract_org_memories(
            org_id="org1",
            user_id="u1",
            message="我们公司规定每月15号发工资给所有员工",
            ai_response="好的，已记录。",
            save_org_memory_fn=save_fn,
        )
        assert len(result) >= 1
        save_fn.assert_called()
        kw = save_fn.call_args_list[0].kwargs
        assert kw["org_id"] == "org1"
        assert kw["category"] == "preference"

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self):
        """Message without org patterns should return empty list."""
        from app.services.conversation_memory.extraction import extract_org_memories

        save_fn = AsyncMock()
        result = await extract_org_memories(
            org_id="org1",
            user_id="u1",
            message="今天天气真好",
            ai_response="是的，天气不错。",
            save_org_memory_fn=save_fn,
        )
        assert result == []
        save_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_org_memory_fn_receives_correct_params(self):
        """save_org_memory_fn should receive org_id, category, key, value, user_id, metadata."""
        from app.services.conversation_memory.extraction import extract_org_memories

        save_fn = AsyncMock(side_effect=lambda **kw: {"id": "org_m2", **kw})
        await extract_org_memories(
            org_id="org1",
            user_id="u1",
            message="我们公司规定所有合同必须经过法务审核才能签署",
            ai_response="好的。",
            save_org_memory_fn=save_fn,
        )
        kw = save_fn.call_args_list[0].kwargs
        assert kw["org_id"] == "org1"
        assert kw["user_id"] == "u1"
        assert kw["metadata"] == {"source": "auto_extract"}
        assert "key" in kw
        assert "value" in kw


# ════════════════════════════════════════════════════════════════
# Section 2: Retrieval
# ════════════════════════════════════════════════════════════════


class TestFormatByTemperature:
    """Tests for _format_by_temperature() — temperature-based display truncation."""

    def test_hot_memory_full_value(self):
        """Hot memory (< 3 days old, importance > 0.7) should show full value."""
        from app.services.conversation_memory.retrieval import _format_by_temperature

        now = datetime.now(UTC).isoformat()
        mem = {
            "updated_at": now,
            "category": "preference",
            "importance": 0.9,
            "value": "用户偏好使用深色主题并且喜欢markdown格式的报告输出",
            "key": "theme_pref",
        }
        result = _format_by_temperature(mem)
        # Full value should appear in output
        assert "用户偏好使用深色主题并且喜欢markdown格式的报告输出" in result
        assert 'importance="0.9"' in result

    def test_warm_memory_truncated(self):
        """Warm memory (< 30 days old, importance <= 0.7) should truncate to 100 chars."""
        from app.services.conversation_memory.retrieval import _format_by_temperature

        ten_days_ago = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        long_value = "A" * 300
        mem = {
            "updated_at": ten_days_ago,
            "category": "preference",
            "importance": 0.5,
            "value": long_value,
            "key": "some_key",
        }
        result = _format_by_temperature(mem)
        # Should contain truncated value (100 chars of A's), not full 300
        assert "A" * 100 in result
        assert "A" * 300 not in result

    def test_cold_memory_shows_search_hint(self):
        """Cold memory (> 30 days old) should show key and search hint."""
        from app.services.conversation_memory.retrieval import _format_by_temperature

        old_date = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        mem = {
            "updated_at": old_date,
            "category": "preference",
            "importance": 0.5,
            "value": "很久以前的偏好设置内容详情",
            "key": "old_pref",
        }
        result = _format_by_temperature(mem)
        assert "search_long_term_memory" in result
        assert "old_pref" in result

    def test_memory_with_no_date_shows_unknown(self):
        """Memory with no date fields should show '未知时间'."""
        from app.services.conversation_memory.retrieval import _format_by_temperature

        mem = {
            "category": "preference",
            "importance": 0.5,
            "value": "some value",
            "key": "some_key",
        }
        result = _format_by_temperature(mem)
        assert "未知时间" in result


class TestRelativeAge:
    """Tests for _relative_age() and _days_since() helper functions."""

    def test_today_returns_today_label(self):
        """Today's date should return '今天'."""
        from app.services.conversation_memory.retrieval import _relative_age

        now = datetime.now(UTC).isoformat()
        assert _relative_age(now) == "今天"

    def test_fifteen_days_ago(self):
        """15 days ago should return '15天前'."""
        from app.services.conversation_memory.retrieval import _relative_age

        date = (datetime.now(UTC) - timedelta(days=15)).isoformat()
        assert _relative_age(date) == "15天前"

    def test_sixty_days_ago_shows_months(self):
        """60 days ago should return '2个月前'."""
        from app.services.conversation_memory.retrieval import _relative_age

        date = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        assert _relative_age(date) == "2个月前"

    def test_four_hundred_days_ago_shows_years(self):
        """400 days ago should return '1年前'."""
        from app.services.conversation_memory.retrieval import _relative_age

        date = (datetime.now(UTC) - timedelta(days=400)).isoformat()
        assert _relative_age(date) == "1年前"

    def test_empty_string_returns_unknown(self):
        """Empty string should return '未知时间'."""
        from app.services.conversation_memory.retrieval import _relative_age

        assert _relative_age("") == "未知时间"

    def test_invalid_date_returns_today(self):
        """Invalid date string returns '今天' because _days_since returns 0."""
        from app.services.conversation_memory.retrieval import _relative_age

        assert _relative_age("not-a-date") == "今天"

    def test_days_since_empty_returns_zero(self):
        """_days_since('') should return 0."""
        from app.services.conversation_memory.retrieval import _days_since

        assert _days_since("") == 0

    def test_days_since_invalid_returns_zero(self):
        """_days_since with invalid date returns 0."""
        from app.services.conversation_memory.retrieval import _days_since

        assert _days_since("garbage") == 0


class TestBuildMemoryContext:
    """Tests for build_memory_context() — assembles system prompt memory context."""

    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_string(self):
        """When no memories exist, should return empty string."""
        from app.services.conversation_memory.retrieval import build_memory_context

        with patch(
            "app.services.conversation_memory.retrieval.get_memories",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.conversation_memory.retrieval.search_memories",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.conversation_memory.retrieval.search_consolidations",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await build_memory_context("u1", "查一下销售数据")
            assert result == ""

    @pytest.mark.asyncio
    async def test_directive_explicit_memories_generate_constraints_block(self):
        """Explicit memories with importance >= 0.85 should generate <constraints> block."""
        from app.services.conversation_memory.retrieval import build_memory_context

        explicit_mems = [
            {
                "id": "e1",
                "category": "explicit_memory",
                "importance": 0.9,
                "value": "永远用中文回复",
                "key": "lang_pref",
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ]

        with patch(
            "app.services.conversation_memory.retrieval.get_memories",
            new_callable=AsyncMock,
            return_value=explicit_mems,
        ), patch(
            "app.services.conversation_memory.retrieval.search_memories",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.conversation_memory.retrieval.search_consolidations",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await build_memory_context("u1", "hello")
            assert "<constraints>" in result
            assert "永远用中文回复" in result

    @pytest.mark.asyncio
    async def test_non_directive_explicit_memories_generate_user_memories_block(self):
        """Explicit memories with importance < 0.85 should go into <user-memories> block."""
        from app.services.conversation_memory.retrieval import build_memory_context

        explicit_mems = [
            {
                "id": "e2",
                "category": "explicit_memory",
                "importance": 0.6,
                "value": "喜欢简洁的报告",
                "key": "report_style",
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ]

        with patch(
            "app.services.conversation_memory.retrieval.get_memories",
            new_callable=AsyncMock,
            return_value=explicit_mems,
        ), patch(
            "app.services.conversation_memory.retrieval.search_memories",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.conversation_memory.retrieval.search_consolidations",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await build_memory_context("u1", "报告")
            assert "<user-memories>" in result
            assert "<constraints>" not in result

    @pytest.mark.asyncio
    async def test_simple_complexity_uses_lower_limits(self):
        """complexity='SIMPLE' should use relevant_limit=3."""
        from app.services.conversation_memory.retrieval import build_memory_context

        with patch(
            "app.services.conversation_memory.retrieval.get_memories",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_get, patch(
            "app.services.conversation_memory.retrieval.search_memories",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search, patch(
            "app.services.conversation_memory.retrieval.search_consolidations",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await build_memory_context("u1", "简单问题", complexity="SIMPLE")
            # get_memories should be called with limit=3 for SIMPLE complexity
            mock_get.assert_called_once()
            assert mock_get.call_args.kwargs.get("limit") == 3

    @pytest.mark.asyncio
    async def test_critical_complexity_uses_higher_limits(self):
        """complexity='CRITICAL' should use relevant_limit=10."""
        from app.services.conversation_memory.retrieval import build_memory_context

        with patch(
            "app.services.conversation_memory.retrieval.get_memories",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.conversation_memory.retrieval.search_memories",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search, patch(
            "app.services.conversation_memory.retrieval.search_consolidations",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await build_memory_context("u1", "复杂分析任务", complexity="CRITICAL")
            # search_memories should be called with limit=10 for CRITICAL
            mock_search.assert_called_once()
            assert mock_search.call_args.kwargs.get("limit") == 10


# ════════════════════════════════════════════════════════════════
# Section 3: Cleanup
# ════════════════════════════════════════════════════════════════


class TestComputeDecayScore:
    """Tests for compute_decay_score() — temporal decay scoring."""

    def test_basic_score_computation(self):
        """Memory with importance=1.0 and recent date should produce a reasonable score."""
        from app.services.conversation_memory.cleanup import compute_decay_score

        now = datetime.now(UTC).isoformat()
        mem = {
            "importance": 1.0,
            "access_count": 0,
            "last_accessed_at": now,
            "category": "preference",
        }
        score = compute_decay_score(mem)
        assert score > 0
        assert score <= 2.0  # importance * recency * access * surprise

    def test_evergreen_explicit_memory_no_decay(self):
        """explicit_memory category should not decay even with old date."""
        from app.services.conversation_memory.cleanup import compute_decay_score

        old_date = (datetime.now(UTC) - timedelta(days=365)).isoformat()
        mem = {
            "importance": 0.8,
            "access_count": 0,
            "last_accessed_at": old_date,
            "category": "explicit_memory",
        }
        score = compute_decay_score(mem)
        # recency_factor should be 1.0 for evergreen, so score = 0.8 * 1.0 * access * surprise
        # access_factor for count=0: log(1)/log(10) + 0.5 = 0 + 0.5 = 0.5
        expected_min = 0.8 * 1.0 * 0.5 * 1.0  # 0.4
        assert score >= expected_min - 0.01

    def test_evergreen_policy_no_decay(self):
        """policy category should not decay even with old date."""
        from app.services.conversation_memory.cleanup import compute_decay_score

        old_date = (datetime.now(UTC) - timedelta(days=365)).isoformat()
        mem = {
            "importance": 0.7,
            "access_count": 0,
            "last_accessed_at": old_date,
            "category": "policy",
        }
        score = compute_decay_score(mem)
        # recency_factor = 1.0 for policy
        assert score >= 0.7 * 1.0 * 0.5 * 1.0 - 0.01

    def test_regular_category_decays_with_age(self):
        """Regular preference category should decay with age (60 days)."""
        from app.services.conversation_memory.cleanup import compute_decay_score

        old_date = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        mem_old = {
            "importance": 0.5,
            "access_count": 0,
            "last_accessed_at": old_date,
            "category": "preference",
        }
        now = datetime.now(UTC).isoformat()
        mem_new = {
            "importance": 0.5,
            "access_count": 0,
            "last_accessed_at": now,
            "category": "preference",
        }
        score_old = compute_decay_score(mem_old)
        score_new = compute_decay_score(mem_new)
        assert score_old < score_new

    def test_access_count_zero_gives_low_access_factor(self):
        """access_count=0 should give access_factor ~0.5."""
        from app.services.conversation_memory.cleanup import compute_decay_score

        # access_factor = log(0+1)/log(10) + 0.5 = 0 + 0.5 = 0.5
        now = datetime.now(UTC).isoformat()
        mem = {
            "importance": 1.0,
            "access_count": 0,
            "last_accessed_at": now,
            "category": "preference",
        }
        score = compute_decay_score(mem)
        # recency ~1.0, access = 0.5, surprise = 1.0 → score ≈ 0.5
        assert abs(score - 0.5) < 0.1

    def test_high_access_count_gives_high_access_factor(self):
        """access_count=100 should give access_factor close to 2.0."""
        from app.services.conversation_memory.cleanup import compute_decay_score

        now = datetime.now(UTC).isoformat()
        mem = {
            "importance": 1.0,
            "access_count": 100,
            "last_accessed_at": now,
            "category": "preference",
        }
        score = compute_decay_score(mem)
        # access_factor = log(101)/log(10) + 0.5 ≈ 2.004 → capped at 2.0
        # score ≈ 1.0 * ~1.0 * 2.0 * surprise ≈ 2.0
        assert score > 1.5

    def test_surprise_factor_with_high_similarity_low_access(self):
        """High similarity + low access should boost surprise_factor > 1.0."""
        from app.services.conversation_memory.cleanup import compute_decay_score

        now = datetime.now(UTC).isoformat()
        mem = {
            "importance": 0.5,
            "access_count": 0,
            "similarity": 0.8,
            "last_accessed_at": now,
            "category": "preference",
        }
        score_with_surprise = compute_decay_score(mem)

        mem_no_sim = {
            "importance": 0.5,
            "access_count": 0,
            "similarity": 0.0,
            "last_accessed_at": now,
            "category": "preference",
        }
        score_no_surprise = compute_decay_score(mem_no_sim)
        assert score_with_surprise > score_no_surprise

    def test_surprise_factor_not_applied_below_threshold(self):
        """Similarity < 0.3 should not apply surprise factor."""
        from app.services.conversation_memory.cleanup import compute_decay_score

        now = datetime.now(UTC).isoformat()
        mem = {
            "importance": 0.5,
            "access_count": 0,
            "similarity": 0.1,
            "last_accessed_at": now,
            "category": "preference",
        }
        score = compute_decay_score(mem)
        # surprise_factor should be 1.0
        # score ≈ 0.5 * ~1.0 * 0.5 * 1.0 = 0.25
        assert abs(score - 0.25) < 0.05

    def test_missing_date_uses_default_60_days(self):
        """Memory with no date fields should use 60 days as default."""
        from app.services.conversation_memory.cleanup import compute_decay_score

        mem = {
            "importance": 1.0,
            "access_count": 0,
            "category": "preference",
        }
        score = compute_decay_score(mem)
        # days_since = 60, recency_factor = 1/(1 + 60/30) = 1/3
        # access_factor = 0.5, surprise = 1.0
        # score ≈ 1.0 * 0.333 * 0.5 * 1.0 ≈ 0.167
        assert abs(score - (1.0 / 3.0 * 0.5)) < 0.05


class TestMMRRerank:
    """Tests for mmr_rerank() — Maximal Marginal Relevance diversity reranking."""

    def test_empty_list_returns_empty(self):
        """Empty input should return empty list."""
        from app.services.conversation_memory.cleanup import mmr_rerank

        assert mmr_rerank([], 5) == []

    def test_single_memory_returned_as_is(self):
        """Single memory should be returned unchanged."""
        from app.services.conversation_memory.cleanup import mmr_rerank

        mem = {"key": "k1", "value": "hello world", "importance": 0.5, "access_count": 0, "category": "preference"}
        result = mmr_rerank([mem], 5)
        assert len(result) == 1
        assert result[0] == mem

    def test_two_identical_memories_only_one_selected(self):
        """Two identical memories should result in at most limit selections, favoring diversity."""
        from app.services.conversation_memory.cleanup import mmr_rerank

        now = datetime.now(UTC).isoformat()
        mem1 = {"key": "k1", "value": "完全相同的内容", "importance": 0.5, "access_count": 0, "category": "preference", "updated_at": now}
        mem2 = {"key": "k1", "value": "完全相同的内容", "importance": 0.5, "access_count": 0, "category": "preference", "updated_at": now}
        result = mmr_rerank([mem1, mem2], 1)
        assert len(result) == 1

    def test_limit_greater_than_memories_returns_all(self):
        """limit > len(memories) should return all memories."""
        from app.services.conversation_memory.cleanup import mmr_rerank

        now = datetime.now(UTC).isoformat()
        mems = [
            {"key": f"k{i}", "value": f"内容{i}", "importance": 0.5, "access_count": 0, "category": "preference", "updated_at": now}
            for i in range(3)
        ]
        result = mmr_rerank(mems, 10)
        assert len(result) == 3

    def test_lambda_one_preserves_relevance_order(self):
        """lambda=1.0 (pure relevance) should preserve input relevance order."""
        from app.services.conversation_memory.cleanup import mmr_rerank

        now = datetime.now(UTC).isoformat()
        mems = [
            {"key": "high", "value": "高重要性记忆", "importance": 0.9, "access_count": 5, "category": "preference", "updated_at": now},
            {"key": "low", "value": "低重要性记忆", "importance": 0.1, "access_count": 0, "category": "preference", "updated_at": now},
        ]
        result = mmr_rerank(mems, 2, lambda_param=1.0)
        assert len(result) == 2
        # Higher importance memory should come first
        assert result[0]["key"] == "high"


# ════════════════════════════════════════════════════════════════
# Section 4: Conflict Resolution
# ════════════════════════════════════════════════════════════════


class TestResolveMemoryConflicts:
    """Tests for resolve_memory_conflicts() — LLM-driven conflict resolution."""

    @pytest.mark.asyncio
    async def test_empty_new_memories_returns_empty(self):
        """Empty new_memories list should return empty results."""
        from app.services.conversation_memory.conflict_resolution import resolve_memory_conflicts

        result = await resolve_memory_conflicts("u1", [], org_id="org1", db=MagicMock())
        assert result == []

    @pytest.mark.asyncio
    async def test_db_none_returns_empty(self):
        """db=None should return empty results."""
        from app.services.conversation_memory.conflict_resolution import resolve_memory_conflicts

        result = await resolve_memory_conflicts("u1", [{"key": "k", "value": "v"}], db=None)
        assert result == []

    @pytest.mark.asyncio
    async def test_pattern_key_dedup_bumps_recurrence_count(self):
        """Existing memory with same pattern_key should trigger DEDUP and bump recurrence_count."""
        from app.services.conversation_memory.conflict_resolution import resolve_memory_conflicts

        # Mock DB: pattern_key lookup returns existing match
        mock_execute = AsyncMock(return_value=MagicMock(
            data=[{"id": "existing1", "recurrence_count": 2, "value": "old value"}]
        ))
        mock_update_execute = AsyncMock(return_value=MagicMock(data=[]))

        mock_db = MagicMock()

        # Chain for select query
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq1 = MagicMock()
        mock_select.eq.return_value = mock_eq1
        mock_eq2 = MagicMock()
        mock_eq1.eq.return_value = mock_eq2
        mock_is = MagicMock()
        mock_eq2.is_.return_value = mock_is
        mock_order = MagicMock()
        mock_is.order.return_value = mock_order
        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit
        mock_limit.execute = mock_execute

        # Chain for update query
        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_update_eq = MagicMock()
        mock_update.eq.return_value = mock_update_eq
        mock_update_eq.execute = mock_update_execute

        new_memories = [{"key": "k1", "value": "new value", "category": "preference", "pattern_key": "preference:likes"}]
        result = await resolve_memory_conflicts("u1", new_memories, db=mock_db)

        assert len(result) == 1
        assert result[0]["event"] == "DEDUP"
        assert result[0]["id"] == "existing1"
        assert result[0]["recurrence_count"] == 3

    @pytest.mark.asyncio
    async def test_near_duplicate_skips_llm(self):
        """Similarity >= 0.92 should skip LLM and bump access_count."""
        from app.services.conversation_memory.conflict_resolution import resolve_memory_conflicts

        # Mock: pattern_key lookup returns nothing, vector search returns near-duplicate
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table

        # Pattern-key lookup returns empty
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq1 = MagicMock()
        mock_select.eq.return_value = mock_eq1
        mock_eq2 = MagicMock()
        mock_eq1.eq.return_value = mock_eq2
        mock_is = MagicMock()
        mock_eq2.is_.return_value = mock_is
        mock_order = MagicMock()
        mock_is.order.return_value = mock_order
        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit
        mock_limit.execute = AsyncMock(return_value=MagicMock(data=[]))

        # Update for near-dup bump
        mock_update = MagicMock()
        mock_table.update.return_value = mock_update
        mock_ueq = MagicMock()
        mock_update.eq.return_value = mock_ueq
        mock_ueq.execute = AsyncMock(return_value=MagicMock(data=[]))

        near_dup_result = [
            {"id": "nd1", "value": "similar text", "similarity": 0.95, "access_count": 3}
        ]

        new_memories = [{"key": "k1", "value": "similar text here", "category": "preference"}]

        with patch(
            "app.services.conversation_memory.conflict_resolution._search_similar",
            new_callable=AsyncMock,
            return_value=near_dup_result,
        ):
            result = await resolve_memory_conflicts("u1", new_memories, db=mock_db)

        assert len(result) == 1
        assert result[0]["event"] == "DEDUP"
        assert result[0]["similarity"] == 0.95

    @pytest.mark.asyncio
    async def test_fast_path_no_similar_adds_all(self):
        """No similar memories found should ADD all new memories directly."""
        from app.services.conversation_memory.conflict_resolution import resolve_memory_conflicts

        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table

        # Pattern-key lookup returns empty
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq1 = MagicMock()
        mock_select.eq.return_value = mock_eq1
        mock_eq2 = MagicMock()
        mock_eq1.eq.return_value = mock_eq2
        mock_is = MagicMock()
        mock_eq2.is_.return_value = mock_is
        mock_order = MagicMock()
        mock_is.order.return_value = mock_order
        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit
        mock_limit.execute = AsyncMock(return_value=MagicMock(data=[]))

        new_memories = [
            {"key": "k1", "value": "全新的记忆内容", "category": "preference", "importance": 0.5},
        ]

        with patch(
            "app.services.conversation_memory.conflict_resolution._search_similar",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "app.services.conversation_memory.storage.save_memory",
            new_callable=AsyncMock,
            return_value={"id": "new1"},
        ) as mock_save, patch(
            "app.services.conversation_memory.conflict_resolution.log_memory_change",
            new_callable=AsyncMock,
        ):
            result = await resolve_memory_conflicts("u1", new_memories, db=mock_db)

        assert len(result) == 1
        assert result[0]["event"] == "ADD"
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_resolve_returns_update_calls_update_existing(self):
        """LLM returning UPDATE should call _update_existing_memory."""
        from app.services.conversation_memory.conflict_resolution import resolve_memory_conflicts

        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table

        # Pattern-key lookup returns empty
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq1 = MagicMock()
        mock_select.eq.return_value = mock_eq1
        mock_eq2 = MagicMock()
        mock_eq1.eq.return_value = mock_eq2
        mock_is = MagicMock()
        mock_eq2.is_.return_value = mock_is
        mock_order = MagicMock()
        mock_is.order.return_value = mock_order
        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit
        mock_limit.execute = AsyncMock(return_value=MagicMock(data=[]))

        similar = [{"id": "old1", "value": "旧记忆", "similarity": 0.7, "category": "preference"}]
        llm_actions = [
            {"id": "old1", "text": "合并后的新记忆", "event": "UPDATE", "old_memory": "旧记忆"}
        ]

        new_memories = [{"key": "k1", "value": "新记忆内容", "category": "preference"}]

        with patch(
            "app.services.conversation_memory.conflict_resolution._search_similar",
            new_callable=AsyncMock,
            return_value=similar,
        ), patch(
            "app.services.conversation_memory.conflict_resolution._llm_resolve",
            new_callable=AsyncMock,
            return_value=llm_actions,
        ), patch(
            "app.services.conversation_memory.conflict_resolution._update_existing_memory",
            new_callable=AsyncMock,
            return_value="new_version_id",
        ) as mock_update, patch(
            "app.services.conversation_memory.conflict_resolution.log_memory_change",
            new_callable=AsyncMock,
        ):
            result = await resolve_memory_conflicts("u1", new_memories, db=mock_db)

        mock_update.assert_called_once()
        assert any(r["event"] == "UPDATE" for r in result)

    @pytest.mark.asyncio
    async def test_llm_resolve_failure_falls_back_to_add_all(self):
        """LLM resolution failure should fall back to ADD all remaining memories."""
        from app.services.conversation_memory.conflict_resolution import resolve_memory_conflicts

        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table

        # Pattern-key lookup returns empty
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq1 = MagicMock()
        mock_select.eq.return_value = mock_eq1
        mock_eq2 = MagicMock()
        mock_eq1.eq.return_value = mock_eq2
        mock_is = MagicMock()
        mock_eq2.is_.return_value = mock_is
        mock_order = MagicMock()
        mock_is.order.return_value = mock_order
        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit
        mock_limit.execute = AsyncMock(return_value=MagicMock(data=[]))

        similar = [{"id": "old1", "value": "existing", "similarity": 0.6}]
        new_memories = [{"key": "k1", "value": "新内容", "category": "preference", "importance": 0.5}]

        with patch(
            "app.services.conversation_memory.conflict_resolution._search_similar",
            new_callable=AsyncMock,
            return_value=similar,
        ), patch(
            "app.services.conversation_memory.conflict_resolution._llm_resolve",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM unavailable"),
        ), patch(
            "app.services.conversation_memory.storage.save_memory",
            new_callable=AsyncMock,
            return_value={"id": "fallback1"},
        ) as mock_save:
            result = await resolve_memory_conflicts("u1", new_memories, db=mock_db)

        assert len(result) == 1
        assert result[0]["event"] == "ADD"
        mock_save.assert_called_once()


class TestFindMatchingNewMem:
    """Tests for _find_matching_new_mem() — character overlap matching."""

    async def test_finds_best_match_by_character_overlap(self):
        """Should return the memory entry with highest character overlap to the text."""
        from app.services.conversation_memory.conflict_resolution import _find_matching_new_mem

        memories = [
            {"key": "k1", "value": "用户喜欢用表格展示数据"},
            {"key": "k2", "value": "用户讨厌英文报告"},
            {"key": "k3", "value": "用户喜欢用表格展示数据分析结果"},
        ]
        result = await _find_matching_new_mem("用户喜欢用表格展示数据分析", memories)
        # k3 has the most character overlap with the query
        assert result["key"] == "k3"

    async def test_empty_memories_returns_empty_dict(self):
        """Empty memories list should return empty dict."""
        from app.services.conversation_memory.conflict_resolution import _find_matching_new_mem

        result = await _find_matching_new_mem("some text", [])
        assert result == {}
