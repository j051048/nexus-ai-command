import importlib
import sys

import pytest


def _import_tool_tasks_without_celery():
    """Import tool_tasks while celery is absent, triggering the except ImportError fallback."""

    # 1. Remove tool_tasks from cache so it will be freshly imported
    sys.modules.pop("app.tasks.tool_tasks", None)

    # 2. Save and replace ALL celery-related modules with None
    # Setting to None ensures `from celery import shared_task` raises ImportError
    # even if celery is installed in site-packages (CI environment).
    saved_celery = {}
    for name in list(sys.modules):
        if name.startswith("celery"):
            saved_celery[name] = sys.modules.pop(name)
            sys.modules[name] = None

    try:
        # 3. Import with celery blocked — triggers except ImportError branch
        mod = importlib.import_module("app.tasks.tool_tasks")
        return mod
    finally:
        # 4. Restore sys.modules to not affect other tests
        for name in list(sys.modules):
            if name.startswith("celery") and sys.modules[name] is None:
                sys.modules.pop(name, None)
        for name, mod_obj in saved_celery.items():
            sys.modules.setdefault(name, mod_obj)


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
