"""
Unit tests for A/B Testing framework.
"""

import pytest
from unittest.mock import MagicMock
from app.agent.ab_testing import ab_test_manager, ABTestConfig


@pytest.fixture
def clean_manager():
    """Reset manager state before each test."""
    ab_test_manager._tests.clear()
    return ab_test_manager


def test_register_and_get_test(clean_manager):
    config = ABTestConfig(
        name="test_logic",
        variants=["A", "B"],
        weights=[0.5, 0.5],
        description="Test description"
    )
    clean_manager.register_test(config)
    
    assert "test_logic" in clean_manager._tests
    assert clean_manager.get_test("test_logic").variants == ["A", "B"]


def test_get_variant_deterministic(clean_manager):
    config = ABTestConfig(
        name="ui_theme",
        variants=["dark", "light"],
        weights=[0.5, 0.5]
    )
    clean_manager.register_test(config)
    
    # Same user_id should always get same variant
    v1 = clean_manager.get_variant("ui_theme", "user-1")
    v2 = clean_manager.get_variant("ui_theme", "user-1")
    assert v1 == v2
    
    # Different user_id might get different variant (hash based)
    # We test hash consistency here
    v3 = clean_manager.get_variant("ui_theme", "user-6") # Chosen to likely be different
    # This is statistical, but for specific IDs it's deterministic
    pass

def test_get_variant_unregistered(clean_manager):
    # Should return None or default for unregistered tests
    variant = clean_manager.get_variant("non_existent", "user-1")
    assert variant is None

def test_active_tests_filtering(clean_manager):
    clean_manager.register_test(ABTestConfig(name="test1", variants=["A", "B"], is_active=True))
    clean_manager.register_test(ABTestConfig(name="test2", variants=["A", "B"], is_active=False))
    
    active = clean_manager.get_active_tests()
    assert len(active) == 1
    assert active[0].name == "test1"
