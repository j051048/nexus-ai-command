"""Tests for error_recovery_service including CircuitBreaker."""

import time
from unittest.mock import AsyncMock

import pytest

from app.services.error_recovery_service import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    ErrorContext,
    ErrorRecoveryService,
    ErrorSeverity,
    RecoveryStrategy,
)


class TestErrorClassification:
    def test_classify_known_error(self):
        service = ErrorRecoveryService()
        ctx = service.classify_error(
            ConnectionError("refused"),
            component="agent",
            operation="llm_call",
        )
        assert ctx.error_type == "ConnectionError"
        assert ctx.severity == ErrorSeverity.MEDIUM

    def test_classify_critical_auth_error(self):
        service = ErrorRecoveryService()

        class AuthenticationError(Exception):
            pass

        ctx = service.classify_error(
            AuthenticationError("invalid token"),
            component="auth",
            operation="login",
        )
        assert ctx.error_type == "AuthenticationError"
        assert ctx.severity == ErrorSeverity.CRITICAL

    def test_classify_unknown_error(self):
        service = ErrorRecoveryService()
        ctx = service.classify_error(
            ValueError("bad value"),
            component="parser",
            operation="parse",
        )
        assert ctx.error_type == "ValueError"


class TestStrategySelection:
    def test_retry_strategy_for_timeout(self):
        service = ErrorRecoveryService()
        ctx = ErrorContext(
            error_type="TimeoutError",
            error_message="timed out",
            severity=ErrorSeverity.MEDIUM,
            component="agent",
            operation="tool_call",
        )
        strategy = service._get_strategy(ctx)
        assert strategy == RecoveryStrategy.RETRY

    def test_abort_strategy_for_auth(self):
        service = ErrorRecoveryService()
        ctx = ErrorContext(
            error_type="AuthenticationError",
            error_message="invalid",
            severity=ErrorSeverity.CRITICAL,
            component="auth",
            operation="login",
        )
        strategy = service._get_strategy(ctx)
        assert strategy == RecoveryStrategy.ABORT

    def test_fallback_for_unknown_type(self):
        service = ErrorRecoveryService()
        ctx = ErrorContext(
            error_type="SomeRandomError",
            error_message="oops",
            severity=ErrorSeverity.LOW,
            component="test",
            operation="test",
        )
        strategy = service._get_strategy(ctx)
        assert strategy == RecoveryStrategy.GRACEFUL_DEGRADATION


class TestRetryRecovery:
    @pytest.mark.asyncio
    async def test_retry_success(self):
        """Test that _retry_recovery succeeds when operation_func succeeds."""
        service = ErrorRecoveryService()

        async def ok_op():
            return "success"

        ctx = ErrorContext(
            error_type="ConnectionError",
            error_message="retry me",
            severity=ErrorSeverity.MEDIUM,
            component="test",
            operation="test",
            retry_count=0,
            max_retries=3,
        )
        result = await service._retry_recovery(ConnectionError("retry me"), ctx, ok_op)
        assert result.success is True
        assert result.strategy_used == RecoveryStrategy.RETRY

    @pytest.mark.asyncio
    async def test_retry_failure_increments_count(self):
        """Test that a failed retry increments retry_count and allows further retries."""
        service = ErrorRecoveryService()

        async def failing_op():
            raise ConnectionError("still failing")

        ctx = ErrorContext(
            error_type="ConnectionError",
            error_message="fail",
            severity=ErrorSeverity.MEDIUM,
            component="test",
            operation="test",
            retry_count=0,
            max_retries=3,
        )
        result = await service._retry_recovery(ConnectionError("fail"), ctx, failing_op)
        assert result.success is False
        assert result.should_retry is True
        assert ctx.retry_count == 1

    @pytest.mark.asyncio
    async def test_retry_max_exceeded(self):
        service = ErrorRecoveryService()
        ctx = ErrorContext(
            error_type="ConnectionError",
            error_message="fail",
            severity=ErrorSeverity.MEDIUM,
            component="test",
            operation="test",
            retry_count=3,
            max_retries=3,
        )
        result = await service._retry_recovery(ConnectionError("fail"), ctx, AsyncMock())
        assert result.success is False
        assert "Max retries" in result.message


class TestErrorStats:
    def test_error_tracking(self):
        service = ErrorRecoveryService()
        ctx = ErrorContext(
            error_type="TimeoutError",
            error_message="slow",
            severity=ErrorSeverity.MEDIUM,
            component="agent",
            operation="call",
        )
        service._track_error(ctx)
        service._track_error(ctx)
        stats = service.get_error_stats()
        assert stats["error_counts"]["agent:TimeoutError"] == 2
        assert len(stats["recent_errors"]) == 2


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_opens_after_threshold(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60.0))
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1))
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_closes_after_success_in_half_open(self):
        cb = CircuitBreaker(
            "test",
            CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1, success_threshold=1),
        )
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1))
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 0
        assert cb.state == CircuitState.CLOSED
