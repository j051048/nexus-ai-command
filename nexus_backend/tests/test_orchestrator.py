"""
Tests for orchestrator — execution layers, parallel topology, dependency resolution.
"""

import pytest

from app.agent.nodes_orchestrator import _resolve_execution_layers, _resolve_execution_order


# ── Execution Order (Legacy) ──


class TestResolveExecutionOrder:
    """Test topological sort for execution order."""

    def test_empty_tasks(self):
        assert _resolve_execution_order([]) == []

    def test_no_dependencies(self):
        tasks = [
            {"title": "A"},
            {"title": "B"},
            {"title": "C"},
        ]
        order = _resolve_execution_order(tasks)
        assert sorted(order) == [0, 1, 2]

    def test_linear_dependencies(self):
        tasks = [
            {"title": "A", "dependencies": []},
            {"title": "B", "dependencies": [0]},
            {"title": "C", "dependencies": [1]},
        ]
        order = _resolve_execution_order(tasks)
        assert order.index(0) < order.index(1)
        assert order.index(1) < order.index(2)

    def test_diamond_dependencies(self):
        #   0
        #  / \
        # 1   2
        #  \ /
        #   3
        tasks = [
            {"title": "A", "dependencies": []},
            {"title": "B", "dependencies": [0]},
            {"title": "C", "dependencies": [0]},
            {"title": "D", "dependencies": [1, 2]},
        ]
        order = _resolve_execution_order(tasks)
        assert order.index(0) < order.index(1)
        assert order.index(0) < order.index(2)
        assert order.index(1) < order.index(3)
        assert order.index(2) < order.index(3)

    def test_handles_invalid_dependency_index(self):
        tasks = [
            {"title": "A", "dependencies": [99]},  # Invalid index
        ]
        order = _resolve_execution_order(tasks)
        assert order == [0]

    def test_handles_cycle(self):
        tasks = [
            {"title": "A", "dependencies": [1]},
            {"title": "B", "dependencies": [0]},
        ]
        order = _resolve_execution_order(tasks)
        # Should still return all tasks (cycle broken by fallback)
        assert sorted(order) == [0, 1]


# ── Execution Layers (P4 Parallel) ──


class TestResolveExecutionLayers:
    """Test layer-based parallel execution planning."""

    def test_empty_tasks(self):
        assert _resolve_execution_layers([]) == []

    def test_all_independent_single_layer(self):
        tasks = [
            {"title": "A"},
            {"title": "B"},
            {"title": "C"},
        ]
        layers = _resolve_execution_layers(tasks)
        assert len(layers) == 1
        assert sorted(layers[0]) == [0, 1, 2]

    def test_linear_chain_separate_layers(self):
        tasks = [
            {"title": "A", "dependencies": []},
            {"title": "B", "dependencies": [0]},
            {"title": "C", "dependencies": [1]},
        ]
        layers = _resolve_execution_layers(tasks)
        assert len(layers) == 3
        assert layers[0] == [0]
        assert layers[1] == [1]
        assert layers[2] == [2]

    def test_diamond_two_layers(self):
        #   0       → Layer 0
        #  / \
        # 1   2     → Layer 1
        #  \ /
        #   3       → Layer 2
        tasks = [
            {"title": "A", "dependencies": []},
            {"title": "B", "dependencies": [0]},
            {"title": "C", "dependencies": [0]},
            {"title": "D", "dependencies": [1, 2]},
        ]
        layers = _resolve_execution_layers(tasks)
        assert len(layers) == 3
        assert layers[0] == [0]
        assert sorted(layers[1]) == [1, 2]  # B and C are parallel
        assert layers[2] == [3]

    def test_two_independent_chains(self):
        # Chain 1: 0 → 1
        # Chain 2: 2 → 3
        tasks = [
            {"title": "A", "dependencies": []},
            {"title": "B", "dependencies": [0]},
            {"title": "C", "dependencies": []},
            {"title": "D", "dependencies": [2]},
        ]
        layers = _resolve_execution_layers(tasks)
        assert len(layers) == 2
        assert sorted(layers[0]) == [0, 2]  # A and C are parallel
        assert sorted(layers[1]) == [1, 3]  # B and D are parallel

    def test_mixed_dependencies(self):
        # 0, 1 independent
        # 2 depends on 0
        # 3 depends on 0 and 1
        tasks = [
            {"title": "A", "dependencies": []},
            {"title": "B", "dependencies": []},
            {"title": "C", "dependencies": [0]},
            {"title": "D", "dependencies": [0, 1]},
        ]
        layers = _resolve_execution_layers(tasks)
        assert len(layers) == 2
        assert sorted(layers[0]) == [0, 1]
        assert sorted(layers[1]) == [2, 3]

    def test_handles_cycle_gracefully(self):
        tasks = [
            {"title": "A", "dependencies": [1]},
            {"title": "B", "dependencies": [0]},
        ]
        layers = _resolve_execution_layers(tasks)
        # Should return all tasks despite cycle
        all_tasks = [idx for layer in layers for idx in layer]
        assert sorted(all_tasks) == [0, 1]

    def test_priority_within_layer(self):
        tasks = [
            {"title": "Low", "priority": 5},
            {"title": "High", "priority": 1},
            {"title": "Med", "priority": 3},
        ]
        layers = _resolve_execution_layers(tasks)
        assert len(layers) == 1
        # Should be sorted by priority (1, 3, 5)
        assert layers[0] == [1, 2, 0]

    def test_single_task(self):
        tasks = [{"title": "Only"}]
        layers = _resolve_execution_layers(tasks)
        assert layers == [[0]]
