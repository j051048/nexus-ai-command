"""
Agent A/B Testing Framework.

Lightweight experiment assignment for comparing agent configurations
(prompts, temperatures, models, tool sets) with deterministic bucketing.

Usage:
    from app.agent.ab_testing import get_experiment_variant, EXPERIMENTS

    # In stream.py or node_plan.py:
    variant = get_experiment_variant("prompt_v2_test", user_id)
    if variant == "treatment":
        system_prompt += TREATMENT_SUFFIX
"""

import hashlib
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExperimentVariant:
    """A single variant in an experiment."""

    name: str
    weight: int = 50  # percentage weight (0-100)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Experiment:
    """An A/B experiment definition."""

    name: str
    description: str
    variants: tuple[ExperimentVariant, ...]
    # Only users matching this role filter participate (empty = all)
    role_filter: frozenset[str] = frozenset()
    # Traffic percentage that enters the experiment at all (0-100)
    traffic_pct: int = 100
    enabled: bool = True


# ── Active experiments registry ──────────────────────────────────────────
# Add new experiments here. Disabled experiments always return "control".

EXPERIMENTS: dict[str, Experiment] = {
    # Experiment 1: Test whether concise system instructions improve response quality
    "system_prompt_style": Experiment(
        name="system_prompt_style",
        description="Compare default vs concise system prompt style for response quality",
        variants=(
            ExperimentVariant("control", weight=50),
            ExperimentVariant(
                "concise",
                weight=50,
                config={
                    "prompt_suffix": (
                        "\n\n## 回复风格要求\n"
                        "- 直入主题，省略寒暄和过渡语\n"
                        "- 优先使用列表和表格展示信息\n"
                        "- 每段回复不超过200字"
                    ),
                },
            ),
        ),
        traffic_pct=10,  # Start with 10% of users
        enabled=True,
    ),
}


def _hash_bucket(experiment_name: str, user_id: str) -> int:
    """Deterministic hash bucket (0-99) for consistent user assignment."""
    key = f"{experiment_name}:{user_id}"
    digest = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()
    return int(digest[:8], 16) % 100


def get_experiment_variant(
    experiment_name: str,
    user_id: str,
    user_role: str = "",
) -> str:
    """Get the variant name for a user in an experiment.

    Returns "control" if:
    - Experiment doesn't exist or is disabled
    - User doesn't match role filter
    - User falls outside traffic percentage
    - AB_TESTING_DISABLED env var is set

    Deterministic: same (experiment, user_id) always returns same variant.
    """
    if os.getenv("AB_TESTING_DISABLED"):
        return "control"

    experiment = EXPERIMENTS.get(experiment_name)
    if not experiment or not experiment.enabled:
        return "control"

    # Role filter
    if experiment.role_filter and user_role not in experiment.role_filter:
        return "control"

    bucket = _hash_bucket(experiment_name, user_id)

    # Traffic gate — only a percentage of users enter the experiment
    if bucket >= experiment.traffic_pct:
        return "control"

    # Weighted variant selection within traffic
    # Normalize bucket within traffic range to select variant
    variant_bucket = (bucket * 100) // max(experiment.traffic_pct, 1)
    cumulative = 0
    for variant in experiment.variants:
        cumulative += variant.weight
        if variant_bucket < cumulative:
            return variant.name

    # Fallback to last variant
    return experiment.variants[-1].name if experiment.variants else "control"


def get_experiment_config(
    experiment_name: str,
    user_id: str,
    user_role: str = "",
) -> dict[str, Any]:
    """Get the config dict for the user's assigned variant.

    Returns empty dict if user is in control or experiment doesn't exist.
    """
    variant_name = get_experiment_variant(experiment_name, user_id, user_role)
    experiment = EXPERIMENTS.get(experiment_name)
    if not experiment:
        return {}
    for variant in experiment.variants:
        if variant.name == variant_name:
            return dict(variant.config)
    return {}


def get_active_assignments(user_id: str, user_role: str = "") -> dict[str, str]:
    """Get all active experiment assignments for a user.

    Returns {experiment_name: variant_name} for all enabled experiments.
    Useful for logging/tracing.
    """
    assignments = {}
    for name in EXPERIMENTS:
        variant = get_experiment_variant(name, user_id, user_role)
        if variant != "control":  # Only record non-control assignments
            assignments[name] = variant
    return assignments
