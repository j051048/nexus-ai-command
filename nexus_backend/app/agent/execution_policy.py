"""Centralized Agent execution guardrails.

This adapter keeps graph routing synchronous while consuming the serialized
tenant policy attached by the router node.
"""

from typing import Any

from app.services.ai_execution_policy_service import (
    AIExecutionMode,
    AIExecutionPolicy,
)


def _complexity_value(complexity: Any) -> str:
    value = getattr(complexity, "value", complexity)
    return str(value or "moderate").lower()


def get_reflection_budget(
    complexity: Any,
    completed_tools: list[Any] | None = None,
    policy: dict[str, Any] | AIExecutionPolicy | None = None,
) -> int:
    """Return at most one verification pass for a run."""
    if policy is None:
        legacy = {"simple": 0, "moderate": 1, "complex": 2, "critical": 3}
        return legacy.get(_complexity_value(complexity), 2)
    active = _coerce_policy(policy)
    if active.mode == AIExecutionMode.ECONOMY:
        return 0

    complexity_value = _complexity_value(complexity)
    irreversible = bool(completed_tools) and any(
        getattr(tool, "is_irreversible", False) for tool in completed_tools
    )
    if irreversible or complexity_value in {"complex", "critical"}:
        return min(1, active.max_verifications)
    return 0


def get_iteration_budget(
    policy: dict[str, Any] | AIExecutionPolicy | None,
    configured_max: int = 5,
) -> int:
    """Cap graph loops with the unified policy."""
    if not policy:
        return configured_max
    return min(configured_max, _coerce_policy(policy).max_iterations)


def _coerce_policy(
    policy: dict[str, Any] | AIExecutionPolicy | None,
) -> AIExecutionPolicy:
    if isinstance(policy, AIExecutionPolicy):
        return policy
    if isinstance(policy, dict):
        try:
            return AIExecutionPolicy.model_validate(policy)
        except Exception:
            pass
    return AIExecutionPolicy.for_mode(AIExecutionMode.BALANCED)
