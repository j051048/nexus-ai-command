import importlib
import sys

import pytest


def _import_tool_tasks_without_celery():
    """Import tool_tasks while celery is absent, triggering the except ImportError fallback."""

    # 1. Remove tool_tasks from cache so it will be freshly imported
    sys.modules.pop("app.tasks.tool_tasks", None)

    # 2. Save and replace Celery-related modules with None.
    # Setting to None ensures app.core.celery_app import raises ImportError
    # even if celery is installed in site-packages (CI environment).
    missing = object()
    blocked_names = {
        name
        for name in sys.modules
        if name.startswith("celery") or name == "app.core.celery_app"
    }
    # Block the application module even when it has not been imported yet.
    # The previous helper only blocked modules already present in sys.modules,
    # which made this test depend on collection/import order.
    blocked_names.update({"celery", "app.core.celery_app"})
    saved_celery = {name: sys.modules.get(name, missing) for name in blocked_names}
    for name in blocked_names:
        sys.modules[name] = None

    try:
        # 3. Import with celery blocked — triggers except ImportError branch
        mod = importlib.import_module("app.tasks.tool_tasks")
        return mod
    finally:
        # 4. Restore sys.modules to not affect other tests
        for name, mod_obj in saved_celery.items():
            if mod_obj is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod_obj


def test_execute_tool_isolated_success():
    """当 Celery 不可用时，execute_tool_isolated 应抛出 ImportError"""
    mod = _import_tool_tasks_without_celery()
    with pytest.raises(ImportError) as excinfo:
        mod.execute_tool_isolated(
            tool_name="dummy_tool",
            tool_args={"arg1": "val1"},
            user_id="user1",
            org_id="org1",
        )
    assert "Celery is not installed" in str(excinfo.value)


def test_execute_tool_isolated_not_found():
    """当 Celery 不可用时，execute_tool_isolated 应抛出 ImportError"""
    mod = _import_tool_tasks_without_celery()
    with pytest.raises(ImportError) as excinfo:
        mod.execute_tool_isolated(
            tool_name="missing_tool", tool_args={}, user_id="user1"
        )
    assert "Celery is not installed" in str(excinfo.value)
