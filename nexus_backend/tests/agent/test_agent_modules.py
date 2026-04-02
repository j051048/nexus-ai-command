"""Tests for extracted agent modules: think_tags, stream_checks, domain routing."""

import importlib
import inspect
import pkgutil
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.think_tags import extract_clean_content, strip_think_tags


# ── Helpers ──────────────────────────────────────────────────────────────────


class FakeMsg:
    """Lightweight stand-in for langchain AIMessage."""

    def __init__(self, content, additional_kwargs=None):
        self.content = content
        self.additional_kwargs = additional_kwargs or {}


class FakeBudgetStatus:
    """Minimal budget status for stream_checks tests."""

    def __init__(self, verdict, message=""):
        self.verdict = verdict
        self.message = message


# ═══════════════════════════════════════════════════════════════════════════
# Section 1: think_tags
# ═══════════════════════════════════════════════════════════════════════════


class TestStripThinkTags:
    """Tests for strip_think_tags()."""

    def test_empty_string(self):
        assert strip_think_tags("") == ""

    def test_none_returns_none(self):
        # `not text` is True for None, so the function returns it as-is
        result = strip_think_tags(None)
        assert result is None

    def test_no_think_tags_unchanged(self):
        text = "Hello, this is normal content."
        assert strip_think_tags(text) == text

    def test_single_complete_block(self):
        text = "before<think>reasoning</think>after"
        assert strip_think_tags(text) == "beforeafter"

    def test_multiple_blocks(self):
        text = "a<think>x</think>b<think>y</think>c"
        assert strip_think_tags(text) == "abc"

    def test_nested_like_tags(self):
        # regex is non-greedy so <think>outer<think>inner</think> is the first match
        text = "<think>outer<think>inner</think>rest</think>more"
        result = strip_think_tags(text)
        # After removing first match "<think>outer<think>inner</think>",
        # leftover is "rest</think>more", orphan </think> gets removed too
        assert "<think>" not in result
        assert "</think>" not in result
        assert "more" in result

    def test_multiline_content_inside(self):
        text = "start<think>\nline1\nline2\nline3\n</think>end"
        assert strip_think_tags(text) == "startend"

    def test_orphan_opening_tag(self):
        text = "text<think>incomplete"
        result = strip_think_tags(text)
        assert "<think>" not in result
        assert result == "textincomplete"

    def test_orphan_closing_tag(self):
        text = "text</think>remaining"
        result = strip_think_tags(text)
        assert "</think>" not in result
        assert "remaining" in result

    def test_think_tags_with_trailing_whitespace(self):
        text = "<think>x</think>\n\nreal content"
        result = strip_think_tags(text)
        assert result == "real content"

    def test_content_only_think_tags(self):
        text = "<think>all reasoning, no content</think>"
        assert strip_think_tags(text) == ""

    def test_content_only_think_tags_with_newlines(self):
        text = "<think>reasoning\n</think>\n"
        assert strip_think_tags(text) == ""

    def test_empty_think_block(self):
        text = "before<think></think>after"
        assert strip_think_tags(text) == "beforeafter"

    def test_mixed_orphan_and_complete(self):
        text = "<think>complete</think>middle</think>end"
        result = strip_think_tags(text)
        assert "<think>" not in result
        assert "</think>" not in result
        assert "end" in result


class TestExtractCleanContent:
    """Tests for extract_clean_content()."""

    def test_simple_content_no_reasoning(self):
        msg = FakeMsg(content="Hello, world!")
        assert extract_clean_content(msg) == "Hello, world!"

    def test_content_with_think_tags(self):
        msg = FakeMsg(content="<think>reasoning</think>Answer here")
        assert extract_clean_content(msg) == "Answer here"

    def test_reasoning_content_in_additional_kwargs(self):
        # Case 1: reasoning_content stored separately, content is clean
        msg = FakeMsg(
            content="The answer is 42.",
            additional_kwargs={"reasoning_content": "Let me think..."},
        )
        result = extract_clean_content(msg)
        assert result == "The answer is 42."

    def test_reasoning_content_merged_into_content_proxy(self):
        # Case 3: proxy merged reasoning into content
        reasoning = "Let me think step by step..."
        answer = "The answer is 42."
        msg = FakeMsg(
            content=reasoning + answer,
            additional_kwargs={"reasoning_content": reasoning},
        )
        result = extract_clean_content(msg)
        assert result == answer

    def test_reasoning_content_merged_with_newlines(self):
        reasoning = "Step 1. Step 2."
        answer = "Final answer."
        msg = FakeMsg(
            content=reasoning + "\n\n" + answer,
            additional_kwargs={"reasoning_content": reasoning},
        )
        result = extract_clean_content(msg)
        assert result == answer

    def test_both_reasoning_content_and_think_tags(self):
        reasoning = "deep thought"
        msg = FakeMsg(
            content=reasoning + "<think>more thinking</think>actual answer",
            additional_kwargs={"reasoning_content": reasoning},
        )
        result = extract_clean_content(msg)
        assert result == "actual answer"

    def test_content_is_none(self):
        msg = FakeMsg(content=None)
        assert extract_clean_content(msg) == ""

    def test_msg_without_additional_kwargs(self):
        msg = MagicMock()
        msg.content = "plain response"
        del msg.additional_kwargs  # force getattr fallback
        result = extract_clean_content(msg)
        assert result == "plain response"


# ═══════════════════════════════════════════════════════════════════════════
# Section 2: stream_checks
# ═══════════════════════════════════════════════════════════════════════════


# Common patch targets for stream_checks
_PATCH_USAGE = "app.agent.stream_checks.usage_tracker"
_PATCH_VALIDATE = "app.agent.stream_checks.validate_request_tokens"
_PATCH_BUDGET = "app.agent.stream_checks.token_budget_manager"
_PATCH_CREDIT = "app.agent.stream_checks.tenant_credit_service"
_PATCH_MODERATION = "app.agent.stream_checks.check_user_input"
_PATCH_PII = "app.services.content_moderation.sanitize_pii_for_llm"


def _make_messages(*contents: str) -> list[dict]:
    """Create a list of user messages from content strings."""
    return [{"role": "user", "content": c} for c in contents]


class TestRunPreChecks:
    """Tests for run_pre_checks()."""

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: x)
    @patch(_PATCH_MODERATION, return_value=(True, ""))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(False, 0, "exceeded"))
    @patch(_PATCH_USAGE)
    async def test_token_validation_failure(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks

        mock_usage.ensure_loaded = AsyncMock()
        msgs = _make_messages("hello")

        passed, events, _ = await run_pre_checks(msgs, "u1", "gpt-4", "s1", "org1")

        assert passed is False
        assert any("⛔" in e for e in events)

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: x)
    @patch(_PATCH_MODERATION, return_value=(True, ""))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(True, 100, ""))
    @patch(_PATCH_USAGE)
    async def test_token_budget_exceeded(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks
        from app.core.token_budget import BudgetVerdict

        mock_usage.ensure_loaded = AsyncMock()
        mock_budget.check_budget = AsyncMock(
            return_value=FakeBudgetStatus(BudgetVerdict.EXCEEDED, "Budget exceeded")
        )
        msgs = _make_messages("hello")

        passed, events, _ = await run_pre_checks(msgs, "u1", "gpt-4", "s1", "org1")

        assert passed is False
        assert any("⛔" in e for e in events)

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: x)
    @patch(_PATCH_MODERATION, return_value=(True, ""))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(True, 100, ""))
    @patch(_PATCH_USAGE)
    async def test_token_budget_warning_non_blocking(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks
        from app.core.token_budget import BudgetVerdict

        mock_usage.ensure_loaded = AsyncMock()
        mock_budget.check_budget = AsyncMock(
            return_value=FakeBudgetStatus(BudgetVerdict.WARNING, "80% used")
        )
        mock_credit.check_credit = AsyncMock(return_value=(True, ""))
        msgs = _make_messages("hello")

        passed, events, content = await run_pre_checks(msgs, "u1", "gpt-4", "s1", "org1")

        assert passed is True

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: x)
    @patch(_PATCH_MODERATION, return_value=(True, ""))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(True, 100, ""))
    @patch(_PATCH_USAGE)
    async def test_token_budget_exception_non_blocking(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks

        mock_usage.ensure_loaded = AsyncMock()
        mock_budget.check_budget = AsyncMock(side_effect=RuntimeError("redis down"))
        mock_credit.check_credit = AsyncMock(return_value=(True, ""))
        msgs = _make_messages("hello")

        passed, events, content = await run_pre_checks(msgs, "u1", "gpt-4", "s1", "org1")

        assert passed is True  # graceful degradation

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: x)
    @patch(_PATCH_MODERATION, return_value=(True, ""))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(True, 100, ""))
    @patch(_PATCH_USAGE)
    async def test_tenant_credit_insufficient(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks
        from app.core.token_budget import BudgetVerdict

        mock_usage.ensure_loaded = AsyncMock()
        mock_budget.check_budget = AsyncMock(
            return_value=FakeBudgetStatus(BudgetVerdict.OK)
        )
        mock_credit.check_credit = AsyncMock(return_value=(False, "no credit"))
        msgs = _make_messages("hello")

        passed, events, _ = await run_pre_checks(msgs, "u1", "gpt-4", "s1", "org1")

        assert passed is False
        assert any("配额不足" in e for e in events)

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: x)
    @patch(_PATCH_MODERATION, return_value=(True, ""))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(True, 100, ""))
    @patch(_PATCH_USAGE)
    async def test_credit_check_skipped_when_no_org_id(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks
        from app.core.token_budget import BudgetVerdict

        mock_usage.ensure_loaded = AsyncMock()
        mock_budget.check_budget = AsyncMock(
            return_value=FakeBudgetStatus(BudgetVerdict.OK)
        )
        msgs = _make_messages("hello")

        passed, events, _ = await run_pre_checks(msgs, "u1", "gpt-4", "s1", None)

        assert passed is True
        mock_credit.check_credit.assert_not_called()

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: x)
    @patch(_PATCH_MODERATION, return_value=(False, "harmful content"))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(True, 100, ""))
    @patch(_PATCH_USAGE)
    async def test_content_moderation_failure(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks
        from app.core.token_budget import BudgetVerdict

        mock_usage.ensure_loaded = AsyncMock()
        mock_budget.check_budget = AsyncMock(
            return_value=FakeBudgetStatus(BudgetVerdict.OK)
        )
        mock_credit.check_credit = AsyncMock(return_value=(True, ""))
        msgs = _make_messages("bad input")

        passed, events, _ = await run_pre_checks(msgs, "u1", "gpt-4", "s1", "org1")

        assert passed is False
        assert any("安全警告" in e for e in events)

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: f"[REDACTED:{x}]")
    @patch(_PATCH_MODERATION, return_value=(True, ""))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(True, 100, ""))
    @patch(_PATCH_USAGE)
    async def test_pii_sanitization(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks
        from app.core.token_budget import BudgetVerdict

        mock_usage.ensure_loaded = AsyncMock()
        mock_budget.check_budget = AsyncMock(
            return_value=FakeBudgetStatus(BudgetVerdict.OK)
        )
        mock_credit.check_credit = AsyncMock(return_value=(True, ""))
        msgs = _make_messages("my SSN is 123-45-6789")

        passed, events, last_content = await run_pre_checks(
            msgs, "u1", "gpt-4", "s1", "org1"
        )

        assert passed is True
        # The message content should have been mutated in-place
        assert msgs[0]["content"] != "my SSN is 123-45-6789"

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: x)
    @patch(_PATCH_MODERATION, return_value=(True, ""))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(True, 100, ""))
    @patch(_PATCH_USAGE)
    async def test_all_checks_pass(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks
        from app.core.token_budget import BudgetVerdict

        mock_usage.ensure_loaded = AsyncMock()
        mock_budget.check_budget = AsyncMock(
            return_value=FakeBudgetStatus(BudgetVerdict.OK)
        )
        mock_credit.check_credit = AsyncMock(return_value=(True, ""))
        msgs = _make_messages("What is the weather?")

        passed, events, last_content = await run_pre_checks(
            msgs, "u1", "gpt-4", "s1", "org1"
        )

        assert passed is True
        assert events == []
        assert last_content == "What is the weather?"

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: x)
    @patch(_PATCH_MODERATION, return_value=(True, ""))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(True, 0, ""))
    @patch(_PATCH_USAGE)
    async def test_empty_messages(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks
        from app.core.token_budget import BudgetVerdict

        mock_usage.ensure_loaded = AsyncMock()
        mock_budget.check_budget = AsyncMock(
            return_value=FakeBudgetStatus(BudgetVerdict.OK)
        )
        msgs = []

        passed, events, last_content = await run_pre_checks(
            msgs, "u1", "gpt-4", "s1", None
        )

        assert passed is True
        assert last_content == ""

    @pytest.mark.asyncio
    @patch(_PATCH_PII, side_effect=lambda x: f"[S:{x}]")
    @patch(_PATCH_MODERATION, return_value=(True, ""))
    @patch(_PATCH_CREDIT)
    @patch(_PATCH_BUDGET)
    @patch(_PATCH_VALIDATE, return_value=(True, 100, ""))
    @patch(_PATCH_USAGE)
    async def test_multiple_user_messages_all_sanitized(
        self, mock_usage, mock_validate, mock_budget, mock_credit, mock_mod, mock_pii
    ):
        from app.agent.stream_checks import run_pre_checks
        from app.core.token_budget import BudgetVerdict

        mock_usage.ensure_loaded = AsyncMock()
        mock_budget.check_budget = AsyncMock(
            return_value=FakeBudgetStatus(BudgetVerdict.OK)
        )
        mock_credit.check_credit = AsyncMock(return_value=(True, ""))
        msgs = [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "msg2"},
            {"role": "user", "content": "msg3"},
        ]

        passed, events, last_content = await run_pre_checks(
            msgs, "u1", "gpt-4", "s1", "org1"
        )

        assert passed is True
        # All user messages should have been sanitized (2a-ext loop)
        for m in msgs:
            if m["role"] == "user":
                assert m["content"].startswith("[S:")
        # Assistant messages should be untouched
        assert msgs[1]["content"] == "reply"


# ═══════════════════════════════════════════════════════════════════════════
# Section 3: Domain Routing
# ═══════════════════════════════════════════════════════════════════════════

# Known valid domain values
_KNOWN_DOMAINS = {
    "oa_leave",
    "oa_task",
    "attendance",
    "approval",
    "finance",
    "project",
    "crm",
    "hr",
    "asset",
    "tender",
    "analytics",
    "knowledge",
    "schedule",
    "vmd_content",
    "vmd_market",
    "admin",
    "inventory",
    "system",
}


def _discover_all_tool_classes():
    """Import all modules under app.tools and find BaseTool subclasses."""
    from app.tools.base_tool import BaseTool

    tool_classes = []
    tools_pkg = importlib.import_module("app.tools")
    pkg_path = tools_pkg.__path__

    for importer, modname, ispkg in pkgutil.walk_packages(
        pkg_path, prefix="app.tools."
    ):
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name, None)
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseTool)
                and obj is not BaseTool
                and not inspect.isabstract(obj)
            ):
                tool_classes.append(obj)
    return tool_classes


class TestToolDomainCoverage:
    """Tests for tool domain declarations and routing infrastructure."""

    def test_all_tool_classes_have_non_none_domain(self):
        tool_classes = _discover_all_tool_classes()
        missing = []
        for cls in tool_classes:
            instance = cls()
            if instance.domain is None:
                missing.append(cls.__name__)
        # All concrete tools should declare a domain
        assert len(missing) == 0, (
            f"Tools without domain: {missing}"
        )

    def test_domain_count_at_least_127(self):
        """There should be at least 127 domain declarations across all tools."""
        tool_classes = _discover_all_tool_classes()
        count = sum(1 for cls in tool_classes if cls().domain is not None)
        assert count >= 127, (
            f"Expected at least 127 domain declarations, got {count}"
        )

    def test_sync_tool_domains_registers_tools(self):
        from app.agent.node_helpers import _DOMAIN_TOOL_MAP, _sync_tool_domains

        # Reset sync state so we can re-run
        import app.agent.node_helpers as nh

        nh._domains_synced = False
        _sync_tool_domains()

        # After sync, _DOMAIN_TOOL_MAP should have entries
        assert len(_DOMAIN_TOOL_MAP) > 0
        # Each value should be a set of tool name strings
        for domain, tools in _DOMAIN_TOOL_MAP.items():
            assert isinstance(tools, set)
            assert all(isinstance(t, str) for t in tools)

    def test_all_domains_are_valid(self):
        tool_classes = _discover_all_tool_classes()
        invalid = []
        for cls in tool_classes:
            instance = cls()
            d = instance.domain
            if d is not None and d not in _KNOWN_DOMAINS:
                invalid.append((cls.__name__, d))
        assert len(invalid) == 0, (
            f"Tools with unrecognised domains: {invalid}"
        )

    def test_clock_in_out_tool_domain(self):
        from app.tools.attendance_tools import ClockInOutTool

        assert ClockInOutTool().domain == "attendance"

    def test_get_customers_tool_domain(self):
        from app.tools.crm_tools import GetCustomersTool

        assert GetCustomersTool().domain == "crm"

    def test_expense_claim_tool_domain(self):
        from app.tools.finance_tools import ExpenseClaimTool

        assert ExpenseClaimTool().domain == "finance"

    def test_tender_analysis_tool_domain(self):
        from app.tools.tender_tool import TenderAnalysisTool

        assert TenderAnalysisTool().domain == "tender"

    def test_smart_report_tool_domain(self):
        from app.tools.ai_insight_tools import SmartReportTool

        assert SmartReportTool().domain == "analytics"

    def test_web_fetch_tool_domain(self):
        from app.tools.web_fetch_tools import WebFetchTool

        assert WebFetchTool().domain == "knowledge"
