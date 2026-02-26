"""Tests for token_service: counting, cost estimation, limits, and billing logic."""

import pytest
from app.services.token_service import (
    ModelPricing,
    TokenCounter,
    TokenUsage,
    UsageLimits,
    UsageTracker,
    validate_request_tokens,
    token_counter,
    MODEL_MAPPING,
)


# ─── TokenCounter Tests ─────────────────────────────────────────────────────

class TestTokenCounter:
    def test_count_tokens_basic(self):
        count = token_counter.count_tokens("Hello world", "gpt-4o")
        assert isinstance(count, int)
        assert count > 0

    def test_count_tokens_chinese(self):
        count = token_counter.count_tokens("你好世界，这是一段中文测试", "gpt-4o")
        assert isinstance(count, int)
        assert count > 0

    def test_count_tokens_empty(self):
        count = token_counter.count_tokens("", "gpt-4o")
        assert count == 0

    def test_count_tokens_long_text(self):
        """Long text should produce proportionally more tokens."""
        short = token_counter.count_tokens("Hello", "gpt-4o")
        long = token_counter.count_tokens("Hello " * 500, "gpt-4o")
        assert long > short * 10

    def test_count_messages_tokens(self):
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 1+1?"},
        ]
        count = token_counter.count_messages_tokens(messages, "gpt-4o")
        assert count > 10  # At least the text content
        # Overhead: 4 tokens per message + 3 for conversation = 11
        assert count > 11

    def test_count_messages_multimodal(self):
        """Multimodal messages should only count text parts."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                ],
            }
        ]
        count = token_counter.count_messages_tokens(messages, "gpt-4o")
        assert count > 0

    def test_estimate_cost_gpt4o(self):
        cost = token_counter.estimate_cost(1_000_000, 500_000, "gpt-4o")
        # GPT-4o: $2.50/1M input + $10.00/1M output
        # Expected: 2.50 + 5.00 = 7.50
        assert abs(cost - 7.50) < 0.01

    def test_estimate_cost_gpt4o_mini(self):
        cost = token_counter.estimate_cost(1_000_000, 1_000_000, "gpt-4o-mini")
        # GPT-4o-mini: $0.15/1M input + $0.60/1M output
        # Expected: 0.15 + 0.60 = 0.75
        assert abs(cost - 0.75) < 0.01

    def test_estimate_cost_unknown_model(self):
        cost = token_counter.estimate_cost(1000, 500, "unknown-model-xyz")
        assert isinstance(cost, float)
        assert cost > 0  # Should use DEFAULT pricing

    def test_estimate_cost_zero_tokens(self):
        cost = token_counter.estimate_cost(0, 0, "gpt-4o")
        assert cost == 0.0

    def test_estimate_cost_embedding_model(self):
        """Embedding models have zero output cost."""
        cost = token_counter.estimate_cost(1_000_000, 0, "text-embedding-3-small")
        # $0.02/1M input, $0 output
        assert abs(cost - 0.02) < 0.001


# ─── ModelPricing Tests ──────────────────────────────────────────────────────

class TestModelPricing:
    def test_all_models_have_pricing(self):
        models = list(ModelPricing)
        assert len(models) > 5

    def test_pricing_values_positive(self):
        for model in ModelPricing:
            input_price, output_price = model.value
            assert input_price >= 0
            assert output_price >= 0

    def test_model_mapping_coverage(self):
        """All mapped models should resolve to a valid pricing enum."""
        for model_name, pricing in MODEL_MAPPING.items():
            assert isinstance(pricing, ModelPricing)
            assert len(pricing.value) == 2

    def test_output_more_expensive_than_input(self):
        """For LLM models (not embeddings), output should cost >= input."""
        for model in ModelPricing:
            if model == ModelPricing.TEXT_EMBEDDING_3_SMALL or model == ModelPricing.TEXT_EMBEDDING_3_LARGE:
                continue
            input_p, output_p = model.value
            assert output_p >= input_p, f"{model.name}: output ({output_p}) < input ({input_p})"


# ─── UsageTracker Tests ──────────────────────────────────────────────────────

class TestUsageTracker:
    def test_check_limits_within_bounds(self):
        tracker = UsageTracker()
        is_valid, error = tracker.check_limits("test-user-fresh", 1000)
        assert is_valid is True
        assert error == ""

    def test_check_limits_exceeds_per_request(self):
        tracker = UsageTracker()
        is_valid, error = tracker.check_limits("test-user-big", 200_000)
        assert is_valid is False
        assert "per-request" in error.lower() or "request" in error.lower() or error != ""

    def test_record_usage(self):
        tracker = UsageTracker()
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.001,
            model="gpt-4o",
        )
        tracker.record_usage("test-record-user", usage)
        summary = tracker.get_usage_summary("test-record-user")
        assert summary["tokens_used"] >= 150

    def test_get_usage_summary_new_user(self):
        tracker = UsageTracker()
        summary = tracker.get_usage_summary("new-user-never-seen")
        assert summary["tokens_used"] == 0
        assert summary["cost_usd"] == 0.0
        assert summary["requests"] == 0

    def test_accumulated_usage_exceeds_daily_limit(self):
        """Accumulating many requests should eventually hit daily limit."""
        tracker = UsageTracker()
        user_id = "test-daily-limit-user"

        # Record usage close to daily limit
        big_usage = TokenUsage(
            input_tokens=500_000,
            output_tokens=500_000,
            total_tokens=1_000_000,
            estimated_cost_usd=25.0,
            model="gpt-4o",
        )
        tracker.record_usage(user_id, big_usage)

        # Next request should fail (daily limit is 1M tokens by default)
        is_valid, error = tracker.check_limits(user_id, 50_000)
        assert is_valid is False

    def test_usage_summary_structure(self):
        """Summary should contain all expected fields."""
        tracker = UsageTracker()
        summary = tracker.get_usage_summary("structure-test-user")
        expected_keys = {"tokens_used", "cost_usd", "requests", "tokens_limit", "cost_limit_usd"}
        assert expected_keys.issubset(set(summary.keys()))

    def test_multiple_records_accumulate(self):
        """Multiple record_usage calls should accumulate."""
        tracker = UsageTracker()
        user_id = "test-accumulate-user"
        for _ in range(5):
            tracker.record_usage(
                user_id,
                TokenUsage(
                    input_tokens=100,
                    output_tokens=50,
                    total_tokens=150,
                    estimated_cost_usd=0.001,
                    model="gpt-4o",
                ),
            )
        summary = tracker.get_usage_summary(user_id)
        assert summary["tokens_used"] == 750
        assert summary["requests"] == 5

    def test_cost_accumulates_correctly(self):
        """Cost should add up across multiple calls."""
        tracker = UsageTracker()
        user_id = "test-cost-accum"
        for _ in range(3):
            tracker.record_usage(
                user_id,
                TokenUsage(
                    input_tokens=1000,
                    output_tokens=500,
                    total_tokens=1500,
                    estimated_cost_usd=0.05,
                    model="gpt-4o",
                ),
            )
        summary = tracker.get_usage_summary(user_id)
        assert abs(summary["cost_usd"] - 0.15) < 0.001


# ─── validate_request_tokens Tests ───────────────────────────────────────────

class TestValidateRequestTokens:
    def test_valid_request(self):
        messages = [{"role": "user", "content": "Hello"}]
        is_valid, count, error = validate_request_tokens(messages, "gpt-4o", "test-user-valid")
        assert is_valid is True
        assert count > 0
        assert error == ""

    def test_empty_messages(self):
        """Empty message list should still be valid (just overhead tokens)."""
        messages: list[dict] = []
        is_valid, count, error = validate_request_tokens(messages, "gpt-4o", "test-user-empty")
        assert is_valid is True
        assert count >= 0

    def test_very_long_message(self):
        """A huge message should exceed per-request limit (100K tokens)."""
        # 'x' repeats are compressed by tiktoken, so use varied content
        # Each word is roughly 1 token, so 150K words ≈ 150K tokens
        messages = [{"role": "user", "content": " ".join(f"word{i}" for i in range(150_000))}]
        is_valid, count, error = validate_request_tokens(messages, "gpt-4o", "test-user-long")
        assert is_valid is False
        assert count > 100_000

    def test_multiple_models(self):
        """Should work with different model names."""
        messages = [{"role": "user", "content": "Test"}]
        for model in ["gpt-4o", "gpt-4o-mini", "gemini-pro", "claude-3-sonnet"]:
            is_valid, count, error = validate_request_tokens(messages, model, f"test-{model}")
            assert is_valid is True
            assert count > 0


# ─── UsageLimits Tests ───────────────────────────────────────────────────────

class TestUsageLimits:
    def test_default_limits(self):
        limits = UsageLimits()
        assert limits.max_tokens_per_request == 100_000
        assert limits.max_tokens_per_day == 1_000_000
        assert limits.max_cost_per_day_usd == 50.0
        assert limits.max_requests_per_day == 1000

    def test_custom_limits(self):
        limits = UsageLimits(max_tokens_per_request=50_000, max_cost_per_day_usd=10.0)
        assert limits.max_tokens_per_request == 50_000
        assert limits.max_cost_per_day_usd == 10.0

    def test_org_limits_higher_than_user(self):
        limits = UsageLimits()
        assert limits.max_tokens_per_org_day > limits.max_tokens_per_day
        assert limits.max_cost_per_org_day_usd > limits.max_cost_per_day_usd
