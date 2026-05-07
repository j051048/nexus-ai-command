"""Centralized Agent execution guardrails."""

from typing import Any

REFLECTION_BUDGET_BY_COMPLEXITY = {
    "simple": 0,
    "moderate": 1,
    "complex": 2,
    "critical": 3,
}


def _complexity_value(complexity: Any) -> str:
    value = getattr(complexity, "value", complexity)
    return str(value or "moderate").lower()


def get_reflection_budget(
    complexity: Any,
    completed_tools: list[Any] | None = None,
) -> int:
    """Return the max reflect passes for a run.

    Irreversible tools get one extra verification pass, capped at 4.
    """
    budget = REFLECTION_BUDGET_BY_COMPLEXITY.get(_complexity_value(complexity), 2)
    if completed_tools and any(
        getattr(tool, "is_irreversible", False) for tool in completed_tools
    ):
        budget = min(budget + 1, 4)
    return budget
