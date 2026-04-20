import asyncio
import pytest
from datetime import datetime
import time

from app.services.error_recovery_service import (
    ErrorRecoveryService,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    ErrorSeverity,
    RecoveryStrategy,
    ErrorContext
)

class TestErrorRecoveryService:
    @pytest.fixture
    def error_service(self):
        return ErrorRecoveryService()

    @pytest.mark.asyncio
    async def test_classify_error(self, error_service):
        # Test default severity mapping
        class RateLimitError(Exception): pass
        error = RateLimitError("Rate limit exceeded")
        context = error_service.classify_error(error, "llm_client", "generate")
        
        assert context.error_type == "RateLimitError"
        assert context.severity == ErrorSeverity.MEDIUM

        # Test configured severity mapping
        class LLMError(Exception): pass
        error = LLMError("Server rate_limit exceeded")
        context = error_service.classify_error(error, "llm_client", "generate")
        assert context.error_type == "LLMError"
        assert context.severity == ErrorSeverity.HIGH

        class AuthenticationError(Exception): pass
        error = AuthenticationError("Invalid token")
        context = error_service.classify_error(error, "auth_client", "login")
        assert context.severity == ErrorSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_recover_retry_success(self, error_service):
        class ConnectionError(Exception): pass
        error = ConnectionError("Conn failed")
        context = error_service.classify_error(error, "db", "query")

        attempts = 0
        async def mock_operation():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise ValueError("Fail first")
            return "Success"

        result = await error_service.recover(error, context, mock_operation)
        assert result.success is False
        assert result.strategy_used == RecoveryStrategy.RETRY

        # Now context retry count is 1. We mock the sleep to be faster if needed, but it's 2 seconds min.
        # Let's mock sleep to not actually sleep 2 seconds
        import app.services.error_recovery_service
        original_sleep = app.services.error_recovery_service.asyncio.sleep
        
        async def fast_sleep(s):
            pass
        
        app.services.error_recovery_service.asyncio.sleep = fast_sleep
        try:
            result = await error_service.recover(error, context, mock_operation)
            assert result.success is True
            assert result.strategy_used == RecoveryStrategy.RETRY
            assert attempts == 2
        finally:
            app.services.error_recovery_service.asyncio.sleep = original_sleep

    @pytest.mark.asyncio
    async def test_recover_retry_max_exceeded(self, error_service):
        class LLMError(Exception): pass
        context = ErrorContext(
            error_type="LLMError",
            error_message="timeout",
            severity=ErrorSeverity.MEDIUM,
            component="llm",
            operation="generate",
            retry_count=3,
            max_retries=3
        )
        result = await error_service.recover(LLMError(), context)
        assert result.success is False
        assert result.strategy_used == RecoveryStrategy.RETRY
        assert "Max retries" in result.message

    @pytest.mark.asyncio
    async def test_recover_fallback(self, error_service):
        class RateLimitError(Exception): pass
        context = error_service.classify_error(RateLimitError("too many"), "api", "search")

        # Generic fallback
        result = await error_service.recover(RateLimitError("too many"), context)
        assert result.success is False
        assert result.strategy_used == RecoveryStrategy.FALLBACK
        assert result.fallback_data is not None

        # Custom fallback
        async def my_fallback(ctx):
            return "recovered data"
        
        error_service.register_fallback_handler("search", my_fallback)
        result = await error_service.recover(RateLimitError("too many"), context)
        assert result.success is True
        assert result.fallback_data == "recovered data"

    @pytest.mark.asyncio
    async def test_recover_abort(self, error_service):
        class AuthenticationError(Exception): pass
        context = error_service.classify_error(AuthenticationError(), "api", "login")
        result = await error_service.recover(AuthenticationError(), context)
        
        assert result.success is False
        assert result.strategy_used == RecoveryStrategy.ABORT

class TestCircuitBreaker:
    def test_circuit_state_transitions(self):
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=2, recovery_timeout=0.1, success_threshold=2, half_open_max_calls=1
        ))

        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

        # Failure 1
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        
        # Failure 2
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

        # Wait for recovery timeout
        time.sleep(0.2)
        assert cb.state == CircuitState.HALF_OPEN
        
        # Probe call allowed
        assert cb.allow_request() is True
        # Second probe rejected because half_open_max_calls=1
        assert cb.allow_request() is False

        # Suppose probe succeeds
        cb.record_success()
        # Need 2 success to close
        assert cb.state == CircuitState.HALF_OPEN
        
        # Another success
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_circuit_half_open_failure(self):
        cb = CircuitBreaker("test2", CircuitBreakerConfig(
            failure_threshold=1, recovery_timeout=0.1, success_threshold=1
        ))

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        
        time.sleep(0.2)
        assert cb.state == CircuitState.HALF_OPEN

        # Probe fails
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_redis_sync_degraded(self):
        # Even with redis_sync=True, without actual cache_service it degrades to local seamlessly
        cb = CircuitBreaker("test_redis_degraded", redis_sync=True)
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
