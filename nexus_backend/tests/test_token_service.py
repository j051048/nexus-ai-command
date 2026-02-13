"""Tests for token_service: counting, cost estimation, limits."""

import pytest
from unittest.mock import patch, MagicMock

from app.services.token_service import TokenUsage


class TestTokenCounter:
    def test_count_tokens_basic(self):
        from app.services.token_service import token_counter

        count = token_counter.count_tokens("Hello world", "gpt-4o")
        assert isinstance(count, int)
        assert count > 0

    def test_count_tokens_chinese(self):
        from app.services.token_service import token_counter

        count = token_counter.count_tokens("你好世界，这是一段中文测试", "gpt-4o")
        assert isinstance(count, int)
        assert count > 0

    def test_count_tokens_empty(self):
        from app.services.token_service import token_counter

        count = token_counter.count_tokens("", "gpt-4o")
        assert count == 0

    def test_estimate_cost(self):
        from app.services.token_service import token_counter

        cost = token_counter.estimate_cost(
            input_tokens=1000, output_tokens=500, model="gpt-4o"
        )
        assert isinstance(cost, float)
        assert cost > 0

    def test_estimate_cost_unknown_model(self):
        from app.services.token_service import token_counter

        cost = token_counter.estimate_cost(
            input_tokens=1000, output_tokens=500, model="unknown-model"
        )
        # Should still return a cost (using default pricing)
        assert isinstance(cost, float)


class TestModelPricing:
    def test_all_models_have_pricing(self):
        from app.services.token_service import ModelPricing

        models = list(ModelPricing)
        assert len(models) > 5  # Should have at least 6 models

    def test_pricing_values_positive(self):
        from app.services.token_service import ModelPricing

        for model in ModelPricing:
            input_price, output_price = model.value
            assert input_price >= 0
            assert output_price >= 0


class TestUsageTracker:
    def test_check_limits_within_bounds(self):
        from app.services.token_service import UsageTracker

        tracker = UsageTracker()
        is_valid, error = tracker.check_limits("test-user", 1000)
        assert is_valid is True
        assert error == ""

    def test_check_limits_exceeds_per_request(self):
        from app.services.token_service import UsageTracker

        tracker = UsageTracker()
        # 100K+ tokens should exceed per-request limit
        is_valid, error = tracker.check_limits("test-user", 200000)
        assert is_valid is False
        assert error != ""

    def test_record_usage(self):
        from app.services.token_service import UsageTracker

        tracker = UsageTracker()
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.001,
            model="gpt-4o",
        )
        tracker.record_usage("test-user", usage)
        summary = tracker.get_usage_summary("test-user")
        assert summary["tokens_used"] >= 150

    def test_get_usage_summary_new_user(self):
        from app.services.token_service import UsageTracker

        tracker = UsageTracker()
        summary = tracker.get_usage_summary("new-user-never-seen")
        assert summary["tokens_used"] == 0


class TestValidateRequestTokens:
    def test_valid_request(self):
        from app.services.token_service import validate_request_tokens

        messages = [{"role": "user", "content": "Hello"}]
        is_valid, count, error = validate_request_tokens(
            messages, "gpt-4o", "test-user"
        )
        assert is_valid is True
        assert count > 0
        assert error == ""
