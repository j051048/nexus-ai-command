"""
Dependency Resolver — Topological sorting for WBS sub-task execution ordering.

Extracted from nodes_orchestrator.py for modularity and independent testability.
Pure algorithm — zero LLM/business dependencies.

Provides:
  resolve_execution_order: Flat topological sort (Kahn's algorithm)
  resolve_execution_layers: Layered topological sort for parallel execution
"""

from __future__ import annotations


def resolve_execution_order(sub_tasks: list[dict]) -> list[int]:
    """
    Resolve execution order based on task dependencies (simple topological sort).

    Tasks with no dependencies are executed first. Tasks that depend on
    earlier tasks are executed after their dependencies complete.

    Returns a list of task indices in execution order.
    """
    n = len(sub_tasks)
    if n == 0:
        return []

    # Build adjacency list
    in_degree = [0] * n
    dependents: list[list[int]] = [[] for _ in range(n)]

    for i, task in enumerate(sub_tasks):
        deps = task.get("dependencies", [])
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, int) and 0 <= dep < n:
                    in_degree[i] += 1
                    dependents[dep].append(i)

    # Kahn's algorithm
    queue = [i for i in range(n) if in_degree[i] == 0]
    order: list[int] = []

    while queue:
        # Sort by priority (lower number = higher priority)
        queue.sort(key=lambda idx: sub_tasks[idx].get("priority", 3))
        current = queue.pop(0)
        order.append(current)

        for dep in dependents[current]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    # If there are cycles, add remaining tasks at the end
    if len(order) < n:
        remaining = [i for i in range(n) if i not in order]
        order.extend(remaining)

    return order


def resolve_execution_layers(sub_tasks: list[dict]) -> list[list[int]]:
    """
    Resolve execution layers: tasks within the same layer have no mutual
    dependencies and can run in parallel.

    Uses Kahn's algorithm but collects each "wave" of zero-in-degree nodes
    as a single layer instead of flattening into one list.

    Returns a list of layers, each layer being a list of task indices.
    """
    n = len(sub_tasks)
    if n == 0:
        return []

    # Build adjacency
    in_degree = [0] * n
    dependents: list[list[int]] = [[] for _ in range(n)]

    for i, task in enumerate(sub_tasks):
        deps = task.get("dependencies", [])
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, int) and 0 <= dep < n:
                    in_degree[i] += 1
                    dependents[dep].append(i)

    # Layered Kahn's algorithm
    current_layer = [i for i in range(n) if in_degree[i] == 0]
    layers: list[list[int]] = []
    visited: set[int] = set()

    while current_layer:
        # Sort within layer by priority
        current_layer.sort(key=lambda idx: sub_tasks[idx].get("priority", 3))
        layers.append(current_layer)
        visited.update(current_layer)

        next_layer: list[int] = []
        for node in current_layer:
            for dep in dependents[node]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    next_layer.append(dep)
        current_layer = next_layer

    # Handle cycles: add remaining as final layer
    if len(visited) < n:
        remaining = [i for i in range(n) if i not in visited]
        layers.append(remaining)

    return layers
