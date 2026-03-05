"""
LLM Model Adaptation Gateway - Circuit Breaker

Per-model circuit breaker to prevent cascading failures
when a model endpoint becomes unhealthy.

States:
- CLOSED: Normal operation, all requests pass through
- OPEN: Model is blocked, requests fail immediately
- HALF_OPEN: Testing recovery, allow 1 probe request

Transitions:
- CLOSED -> OPEN: When error rate exceeds threshold in recent calls
- OPEN -> HALF_OPEN: After cooldown period elapses
- HALF_OPEN -> CLOSED: If probe request succeeds
- HALF_OPEN -> OPEN: If probe request fails
"""

import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitStats:
    """Statistics for a single model's circuit breaker."""

    model_code: str
    state: CircuitState
    total_calls: int
    recent_failures: int
    recent_successes: int
    error_rate: float
    last_failure_at: float | None
    last_success_at: float | None
    opened_at: float | None
    half_open_at: float | None


class ModelCircuitBreaker:
    """
    Circuit breaker for a single model endpoint.

    Tracks the last N calls and their success/failure status.
    When error rate exceeds the threshold, the circuit opens.
    """

    def __init__(
        self,
        model_code: str,
        failure_threshold: float = 0.5,
        window_size: int = 10,
        cooldown_seconds: float = 300.0,  # 5 minutes
    ):
        self.model_code = model_code
        self.failure_threshold = failure_threshold
        self.window_size = window_size
        self.cooldown_seconds = cooldown_seconds

        self._state = CircuitState.CLOSED
        self._results: deque[bool] = deque(maxlen=window_size)  # True=success, False=failure
        self._total_calls = 0
        self._last_failure_at: float | None = None
        self._last_success_at: float | None = None
        self._opened_at: float | None = None
        self._half_open_at: float | None = None

    @property
    def state(self) -> CircuitState:
        """Get current state, handling automatic OPEN -> HALF_OPEN transition."""
        if self._state == CircuitState.OPEN and self._opened_at:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_at = time.monotonic()
                logger.info(
                    f"Circuit breaker HALF_OPEN for model '{self.model_code}' after {self.cooldown_seconds}s cooldown"
                )
        return self._state

    def is_allowed(self) -> bool:
        """
        Check if a request is allowed through the circuit breaker.

        Returns True if the request should proceed, False if blocked.
        """
        current_state = self.state  # triggers auto-transition

        if current_state == CircuitState.CLOSED:
            return True

        # HALF_OPEN: allow exactly one probe request; OPEN: block all
        return current_state == CircuitState.HALF_OPEN

    def record_success(self):
        """Record a successful call."""
        self._total_calls += 1
        self._results.append(True)
        self._last_success_at = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # Probe succeeded - close the circuit
            self._state = CircuitState.CLOSED
            self._opened_at = None
            self._half_open_at = None
            logger.info(f"Circuit breaker CLOSED for model '{self.model_code}' - probe succeeded")

    def record_failure(self):
        """Record a failed call."""
        self._total_calls += 1
        self._results.append(False)
        self._last_failure_at = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            # Probe failed - reopen the circuit
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._half_open_at = None
            logger.warning(f"Circuit breaker re-OPENED for model '{self.model_code}' - probe failed")
            return

        # Check if we should open the circuit
        if self._state == CircuitState.CLOSED and len(self._results) >= self.window_size:
            failures = sum(1 for r in self._results if not r)
            error_rate = failures / len(self._results)
            if error_rate >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    f"Circuit breaker OPENED for model '{self.model_code}' - "
                    f"error rate {error_rate:.0%} >= {self.failure_threshold:.0%} "
                    f"in last {len(self._results)} calls"
                )

    def reset(self):
        """Manually reset the circuit breaker to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._results.clear()
        self._opened_at = None
        self._half_open_at = None
        logger.info(f"Circuit breaker manually RESET for model '{self.model_code}'")

    def get_stats(self) -> CircuitStats:
        """Get current circuit breaker statistics."""
        recent_failures = sum(1 for r in self._results if not r)
        recent_successes = sum(1 for r in self._results if r)
        total_recent = len(self._results)
        error_rate = recent_failures / total_recent if total_recent > 0 else 0.0

        return CircuitStats(
            model_code=self.model_code,
            state=self.state,
            total_calls=self._total_calls,
            recent_failures=recent_failures,
            recent_successes=recent_successes,
            error_rate=round(error_rate, 3),
            last_failure_at=self._last_failure_at,
            last_success_at=self._last_success_at,
            opened_at=self._opened_at,
            half_open_at=self._half_open_at,
        )


class CircuitBreakerManager:
    """
    Manages circuit breakers for all model endpoints.
    One circuit breaker per model_code.
    """

    def __init__(
        self,
        failure_threshold: float = 0.5,
        window_size: int = 10,
        cooldown_seconds: float = 300.0,
    ):
        self._breakers: dict[str, ModelCircuitBreaker] = {}
        self._failure_threshold = failure_threshold
        self._window_size = window_size
        self._cooldown_seconds = cooldown_seconds

    def _get_breaker(self, model_code: str) -> ModelCircuitBreaker:
        """Get or create a circuit breaker for a model."""
        if model_code not in self._breakers:
            self._breakers[model_code] = ModelCircuitBreaker(
                model_code=model_code,
                failure_threshold=self._failure_threshold,
                window_size=self._window_size,
                cooldown_seconds=self._cooldown_seconds,
            )
        return self._breakers[model_code]

    def is_allowed(self, model_code: str) -> bool:
        """Check if requests to a model are currently allowed."""
        return self._get_breaker(model_code).is_allowed()

    def record_success(self, model_code: str):
        """Record a successful call to a model."""
        self._get_breaker(model_code).record_success()

    def record_failure(self, model_code: str):
        """Record a failed call to a model."""
        self._get_breaker(model_code).record_failure()

    def get_state(self, model_code: str) -> CircuitState:
        """Get the circuit state for a model."""
        return self._get_breaker(model_code).state

    def reset(self, model_code: str):
        """Manually reset a model's circuit breaker."""
        self._get_breaker(model_code).reset()

    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    def get_all_stats(self) -> list[dict]:
        """Get statistics for all circuit breakers."""
        stats = []
        for breaker in self._breakers.values():
            cb_stats = breaker.get_stats()
            stats.append(
                {
                    "model_code": cb_stats.model_code,
                    "state": cb_stats.state,
                    "total_calls": cb_stats.total_calls,
                    "recent_failures": cb_stats.recent_failures,
                    "recent_successes": cb_stats.recent_successes,
                    "error_rate": cb_stats.error_rate,
                }
            )
        return stats

    def get_stats(self, model_code: str) -> CircuitStats:
        """Get statistics for a specific model's circuit breaker."""
        return self._get_breaker(model_code).get_stats()


# Global circuit breaker manager
circuit_breaker_manager = CircuitBreakerManager(
    failure_threshold=0.5,
    window_size=10,
    cooldown_seconds=300.0,  # 5 minutes
)
