"""
P2 Enhancement: Global Error Recovery Service

Implements centralized error handling and recovery strategies.
Fixes Issue #7: Missing global error recovery strategy.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryStrategy(Enum):
    """Recovery strategies for errors."""

    RETRY = "retry"
    FALLBACK = "fallback"
    GRACEFUL_DEGRADATION = "graceful_degradation"
    ABORT = "abort"
    ESCALATE = "escalate"


@dataclass
class ErrorContext:
    """Context information for an error."""

    error_type: str
    error_message: str
    severity: ErrorSeverity
    component: str
    operation: str
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    success: bool
    strategy_used: RecoveryStrategy
    message: str
    should_retry: bool = False
    fallback_data: Any = None


class ErrorRecoveryService:
    """
    P2 Enhancement: Centralized error recovery management.

    Features:
    - Error classification and severity assessment
    - Configurable recovery strategies
    - Automatic retry with exponential backoff
    - Fallback mechanisms
    - Error escalation
    """

    # Error type to strategy mapping
    DEFAULT_STRATEGIES = {
        "ConnectionError": RecoveryStrategy.RETRY,
        "TimeoutError": RecoveryStrategy.RETRY,
        "RateLimitError": RecoveryStrategy.FALLBACK,
        "AuthenticationError": RecoveryStrategy.ABORT,
        "ValidationError": RecoveryStrategy.ABORT,
        "NotFoundError": RecoveryStrategy.GRACEFUL_DEGRADATION,
        "PermissionError": RecoveryStrategy.ABORT,
        "LLMError": RecoveryStrategy.RETRY,
        "ToolError": RecoveryStrategy.FALLBACK,
        "DatabaseError": RecoveryStrategy.RETRY,
    }

    # Severity thresholds
    SEVERITY_THRESHOLDS = {
        ("LLMError", "timeout"): ErrorSeverity.MEDIUM,
        ("LLMError", "rate_limit"): ErrorSeverity.HIGH,
        ("DatabaseError", "connection"): ErrorSeverity.HIGH,
        ("DatabaseError", "deadlock"): ErrorSeverity.HIGH,
        ("AuthenticationError", "*"): ErrorSeverity.CRITICAL,
    }

    def __init__(self):
        self._error_counts: dict[str, int] = {}
        self._recovery_handlers: dict[str, Callable] = {}
        self._fallback_handlers: dict[str, Callable] = {}
        self._error_history: list = []

    def register_recovery_handler(self, error_type: str, handler: Callable):
        """Register a custom recovery handler for an error type."""
        self._recovery_handlers[error_type] = handler

    def register_fallback_handler(self, operation: str, handler: Callable):
        """Register a fallback handler for an operation."""
        self._fallback_handlers[operation] = handler

    def classify_error(self, error: Exception, component: str, operation: str, metadata: dict = None) -> ErrorContext:
        """Classify an error and determine its severity."""
        error_type = type(error).__name__
        error_message = str(error)

        # Determine severity
        severity = ErrorSeverity.MEDIUM
        for (err_type, pattern), sev in self.SEVERITY_THRESHOLDS.items():
            if err_type == error_type and (pattern == "*" or pattern in error_message.lower()):
                severity = sev
                break

        return ErrorContext(
            error_type=error_type,
            error_message=error_message,
            severity=severity,
            component=component,
            operation=operation,
            metadata=metadata or {},
        )

    async def recover(self, error: Exception, context: ErrorContext, operation_func: Callable = None) -> RecoveryResult:
        """
        Attempt to recover from an error.

        Args:
            error: The exception that occurred
            context: Error context information
            operation_func: The original operation to retry if applicable

        Returns:
            RecoveryResult with recovery outcome
        """
        # Track error
        self._track_error(context)

        # Get recovery strategy
        strategy = self._get_strategy(context)

        logger.info(
            f"Recovery attempt for {context.error_type} in {context.component}: "
            f"strategy={strategy.value}, severity={context.severity.value}"
        )

        # Execute recovery strategy
        if strategy == RecoveryStrategy.RETRY:
            return await self._retry_recovery(error, context, operation_func)
        elif strategy == RecoveryStrategy.FALLBACK:
            return await self._fallback_recovery(error, context)
        elif strategy == RecoveryStrategy.GRACEFUL_DEGRADATION:
            return self._degradation_recovery(error, context)
        elif strategy == RecoveryStrategy.ABORT:
            return self._abort_recovery(error, context)
        elif strategy == RecoveryStrategy.ESCALATE:
            return self._escalate_recovery(error, context)

        return RecoveryResult(success=False, strategy_used=strategy, message="Unknown recovery strategy")

    def _get_strategy(self, context: ErrorContext) -> RecoveryStrategy:
        """Determine recovery strategy based on error context."""
        # Check for custom handler
        if context.error_type in self._recovery_handlers:
            return RecoveryStrategy.FALLBACK  # Let handler decide

        # Use default mapping
        return self.DEFAULT_STRATEGIES.get(context.error_type, RecoveryStrategy.GRACEFUL_DEGRADATION)

    async def _retry_recovery(
        self, error: Exception, context: ErrorContext, operation_func: Callable
    ) -> RecoveryResult:
        """Attempt retry with exponential backoff."""
        if context.retry_count >= context.max_retries:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RETRY,
                message=f"Max retries ({context.max_retries}) exceeded",
            )

        if not operation_func:
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RETRY,
                should_retry=True,
                message="Retry requested - caller should re-execute",
            )

        # Exponential backoff
        backoff = min(2**context.retry_count, 30)
        await asyncio.sleep(backoff)

        try:
            await operation_func()
            return RecoveryResult(success=True, strategy_used=RecoveryStrategy.RETRY, message="Retry successful")
        except Exception as e:
            context.retry_count += 1
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.RETRY,
                should_retry=context.retry_count < context.max_retries,
                message=f"Retry failed: {str(e)}",
            )

    async def _fallback_recovery(self, error: Exception, context: ErrorContext) -> RecoveryResult:
        """Attempt fallback operation."""
        handler = self._fallback_handlers.get(context.operation)

        if not handler:
            # Generic fallback
            return RecoveryResult(
                success=False,
                strategy_used=RecoveryStrategy.FALLBACK,
                fallback_data=self._get_generic_fallback(context),
                message="Using generic fallback",
            )

        try:
            fallback_data = await handler(context)
            return RecoveryResult(
                success=True,
                strategy_used=RecoveryStrategy.FALLBACK,
                fallback_data=fallback_data,
                message="Fallback successful",
            )
        except Exception as e:
            return RecoveryResult(
                success=False, strategy_used=RecoveryStrategy.FALLBACK, message=f"Fallback failed: {str(e)}"
            )

    def _degradation_recovery(self, error: Exception, context: ErrorContext) -> RecoveryResult:
        """Implement graceful degradation."""
        degraded_response = self._get_degraded_response(context)

        return RecoveryResult(
            success=True,
            strategy_used=RecoveryStrategy.GRACEFUL_DEGRADATION,
            fallback_data=degraded_response,
            message="Operating in degraded mode",
        )

    def _abort_recovery(self, error: Exception, context: ErrorContext) -> RecoveryResult:
        """Abort operation and return error."""
        logger.error(f"Aborting operation {context.operation} in {context.component}: {context.error_message}")

        return RecoveryResult(
            success=False, strategy_used=RecoveryStrategy.ABORT, message=f"Operation aborted: {context.error_message}"
        )

    def _escalate_recovery(self, error: Exception, context: ErrorContext) -> RecoveryResult:
        """Escalate error to monitoring/alerting."""
        # Log for alerting
        logger.critical(
            f"ESCALATE: {context.error_type} in {context.component}: {context.error_message}",
            extra={"error_context": context.__dict__, "alert_required": True},
        )

        return RecoveryResult(
            success=False, strategy_used=RecoveryStrategy.ESCALATE, message="Error escalated for human review"
        )

    def _get_generic_fallback(self, context: ErrorContext) -> Any:
        """Get generic fallback data based on operation type."""
        fallbacks = {
            "search": {"results": [], "message": "搜索暂时不可用，请稍后重试"},
            "generate": {"content": "内容生成暂时不可用，请稍后重试"},
            "analyze": {"analysis": None, "message": "分析服务暂时不可用"},
            "default": {"message": "服务暂时不可用，请稍后重试"},
        }
        return fallbacks.get(context.operation, fallbacks["default"])

    def _get_degraded_response(self, context: ErrorContext) -> dict:
        """Get degraded mode response."""
        return {
            "status": "degraded",
            "message": "部分功能暂时不可用",
            "available_features": self._get_available_features(context),
            "retry_suggested": True,
        }

    def _get_available_features(self, context: ErrorContext) -> list:
        """Determine which features are still available."""
        # In degraded mode, some features may still work
        return ["basic_chat", "history"]

    def _track_error(self, context: ErrorContext):
        """Track error for monitoring."""
        key = f"{context.component}:{context.error_type}"
        self._error_counts[key] = self._error_counts.get(key, 0) + 1

        # Keep history manageable
        self._error_history.append(
            {
                "type": context.error_type,
                "component": context.component,
                "severity": context.severity.value,
                "timestamp": context.timestamp.isoformat(),
            }
        )
        if len(self._error_history) > 1000:
            self._error_history = self._error_history[-500:]

    def get_error_stats(self) -> dict:
        """Get error statistics."""
        return {"error_counts": dict(self._error_counts), "recent_errors": self._error_history[-10:]}


# ──────────────────────────────────────────────────────────────────────────────
# Circuit Breaker
# ──────────────────────────────────────────────────────────────────────────────


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject fast
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: float = 60.0  # Seconds before trying half-open
    half_open_max_calls: int = 1  # Probe calls in half-open
    success_threshold: int = 2  # Successes to close from half-open


class CircuitBreaker:
    """Circuit breaker for protecting external service calls.

    Prevents cascading failures by cutting off calls to a failing service
    and periodically probing to check recovery.

    States:
        CLOSED   → Normal. Failures increment counter.
        OPEN     → Service deemed down. All calls rejected immediately.
        HALF_OPEN → After recovery_timeout, allow probe calls to test recovery.
    """

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0  # P1 Fix: track probe calls in half-open

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and time.time() - self._last_failure_time >= self.config.recovery_timeout:
            self._state = CircuitState.HALF_OPEN
            self._success_count = 0
            self._half_open_calls = 0  # Reset probe counter
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        current = self.state
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            # P1 Fix: Only allow limited probe requests in half-open state
            if self._half_open_calls < self.config.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False  # Reject until probe completes
        return False  # OPEN — reject fast

    def record_success(self):
        """Record a successful call."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._half_open_calls = 0
                logger.info(f"Circuit breaker '{self.name}' closed (service recovered)")
        else:
            self._failure_count = 0

    def record_failure(self):
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker '{self.name}' re-opened (probe failed)")
        elif self._failure_count >= self.config.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker '{self.name}' opened after {self._failure_count} failures")

    def get_status(self) -> dict:
        """Get circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
            },
        }


# ──────────────────────────────────────────────────────────────────────────────
# Global Instances
# ──────────────────────────────────────────────────────────────────────────────

error_recovery_service = ErrorRecoveryService()

# Circuit breakers for key external services
llm_circuit_breaker = CircuitBreaker(
    "llm_service",
    CircuitBreakerConfig(failure_threshold=5, recovery_timeout=30.0, success_threshold=2),
)
tool_circuit_breaker = CircuitBreaker(
    "tool_service",
    CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0, success_threshold=2),
)
