import importlib
import types
import sys

import pytest
from unittest.mock import AsyncMock, patch


def _import_tool_tasks_without_celery():
    """重新加载 tool_tasks 模块，注入 mock celery 使 except ImportError 分支生效。"""

    saved_celery = {}
    # 移除所有 celery 相关模块
    for name in list(sys.modules):
        if name.startswith("celery"):
            saved_celery[name] = sys.modules.pop(name)

    # 注入 mock celery 模块，让 from celery import shared_task 成功
    # 但后续 reload 时会清除它以触发 except 分支
    mock_celery = types.ModuleType("celery")

    def _noop_task(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]
        def decorator(fn):
            return fn
        return decorator

    mock_celery.shared_task = _noop_task
    sys.modules["celery"] = mock_celery

    # 移除目标模块以便 reload
    tool_tasks_mod = sys.modules.pop("app.tasks.tool_tasks", None)

    try:
        # 先正常加载（try 分支），然后移除 celery 触发 except 分支
        mod = importlib.import_module("app.tasks.tool_tasks")
        # 移除 celery 使 reload 时 from celery import shared_task 失败
        sys.modules.pop("celery", None)
        mod = importlib.reload(mod)
        return mod
    finally:
        # 恢复 sys.modules
        sys.modules.pop("celery", None)
        for name, mod in saved_celery.items():
            sys.modules.setdefault(name, mod)
        if tool_tasks_mod is not None:
            sys.modules["app.tasks.tool_tasks"] = tool_tasks_mod


def test_execute_tool_isolated_success():
    """当 Celery 不可用时，execute_tool_isolated 应抛出 ImportError"""
    mod = _import_tool_tasks_without_celery()
    with pytest.raises(ImportError) as excinfo:
        mod.execute_tool_isolated(
            tool_name="dummy_tool",
            tool_args={"arg1": "val1"},
            user_id="user1",
            org_id="org1"
        )
    assert "Celery is not installed" in str(excinfo.value)

def test_execute_tool_isolated_not_found():
    """当 Celery 不可用时，execute_tool_isolated 应抛出 ImportError"""
    mod = _import_tool_tasks_without_celery()
    with pytest.raises(ImportError) as excinfo:
        mod.execute_tool_isolated(
            tool_name="missing_tool",
            tool_args={},
            user_id="user1"
        )
    assert "Celery is not installed" in str(excinfo.value)
