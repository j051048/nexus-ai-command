"""
Unit tests for A/B Testing framework.
"""

from app.agent.ab_testing import (
    EXPERIMENTS,
    Experiment,
    ExperimentVariant,
    get_active_assignments,
    get_experiment_config,
    get_experiment_variant,
)


def test_experiment_registered():
    """At least one experiment should be registered."""
    assert len(EXPERIMENTS) >= 1
    assert "system_prompt_style" in EXPERIMENTS


def test_get_variant_deterministic():
    """Same (experiment, user_id) should always return the same variant."""
    v1 = get_experiment_variant("system_prompt_style", "user-abc-123")
    v2 = get_experiment_variant("system_prompt_style", "user-abc-123")
    assert v1 == v2
    assert v1 in ("control", "concise")


def test_get_variant_unknown_experiment():
    """Unknown experiment should return 'control'."""
    v = get_experiment_variant("non_existent_experiment", "user-1")
    assert v == "control"


def test_get_experiment_config_returns_dict():
    """Config for a valid experiment variant should be a dict."""
    config = get_experiment_config("system_prompt_style", "user-abc-123")
    assert isinstance(config, dict)


def test_get_active_assignments():
    """Active assignments should be a dict of experiment→variant."""
    assignments = get_active_assignments("user-abc-123")
    assert isinstance(assignments, dict)
    # Only non-control assignments are returned
    for v in assignments.values():
        assert v != "control"


def test_disabled_experiment():
    """Disabled experiment should return 'control'."""
    # Temporarily modify
    exp = Experiment(
        name="test_disabled",
        description="disabled test",
        variants=(ExperimentVariant("control", 50), ExperimentVariant("treatment", 50)),
        enabled=False,
    )
    EXPERIMENTS["test_disabled"] = exp
    try:
        v = get_experiment_variant("test_disabled", "user-1")
        assert v == "control"
    finally:
        del EXPERIMENTS["test_disabled"]
