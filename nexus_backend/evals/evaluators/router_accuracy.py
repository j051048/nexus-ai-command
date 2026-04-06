"""Router 分类准确性评估器

直接调用 classify_query() 验证复杂度分类结果，无需 LLM API。
Mocks heavy dependencies (langchain, langgraph) that aren't needed for
the pure-heuristic classify_query() function.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from evals.eval_metrics import EvalDimension, EvalResult

_classify_query = None


def _mock_module(name: str):
    """Create a mock module that behaves as a package."""
    if name not in sys.modules:
        mock = MagicMock()
        mock.__path__ = []  # make it a package
        sys.modules[name] = mock


def _get_classify_query():
    global _classify_query
    if _classify_query is not None:
        return _classify_query

    backend_root = Path(__file__).parent.parent.parent

    # Save sys.modules snapshot so we can restore after loading classify_query.
    # This prevents MagicMock pollution from breaking subsequent imports in
    # other test modules within the same pytest session.
    saved_modules = dict(sys.modules)

    try:
        # Mock all heavy deps before any import
        heavy_packages = [
            "langchain_core", "langchain_core.messages", "langchain_core.runnables",
            "langchain_core.tools", "langchain_core.outputs",
            "langchain_openai",
            "langgraph", "langgraph.graph", "langgraph.checkpoint",
            "langgraph.checkpoint.memory",
            "supabase",
            "redis", "redis.asyncio",
            "celery",
        ]
        for mod_name in heavy_packages:
            _mock_module(mod_name)

        # Clean up any previously imported app.agent modules
        for k in [k for k in sys.modules if k.startswith("app.agent")]:
            del sys.modules[k]

        # Prevent app.agent.__init__ from running (it imports graph.py etc.)
        # by pre-registering it as a mock package
        agent_pkg = MagicMock()
        agent_pkg.__path__ = [str(backend_root / "app" / "agent")]
        agent_pkg.__package__ = "app.agent"
        agent_pkg.__spec__ = None
        sys.modules["app.agent"] = agent_pkg

        # Ensure app package exists
        if "app" not in sys.modules:
            app_pkg = MagicMock()
            app_pkg.__path__ = [str(backend_root / "app")]
            app_pkg.__package__ = "app"
            app_pkg.__spec__ = None
            sys.modules["app"] = app_pkg

        # Pre-register node_helpers as mock so router.py's import succeeds
        helpers_mock = MagicMock()
        helpers_mock.__spec__ = None
        helpers_mock.__path__ = []
        helpers_mock.__package__ = "app.agent.node_helpers"
        sys.modules["app.agent.node_helpers"] = helpers_mock

        # Load state.py directly (for QueryComplexity, AgentPhase, etc.)
        state_path = backend_root / "app" / "agent" / "state.py"
        spec = importlib.util.spec_from_file_location("app.agent.state", state_path)
        state_mod = importlib.util.module_from_spec(spec)
        sys.modules["app.agent.state"] = state_mod
        spec.loader.exec_module(state_mod)

        # Load router.py directly
        router_path = backend_root / "app" / "agent" / "router.py"
        spec = importlib.util.spec_from_file_location("app.agent.router", router_path)
        router_mod = importlib.util.module_from_spec(spec)
        sys.modules["app.agent.router"] = router_mod
        spec.loader.exec_module(router_mod)

        _classify_query = router_mod.classify_query
    finally:
        # Restore sys.modules: remove any keys we added, restore any we deleted
        added_keys = set(sys.modules) - set(saved_modules)
        for k in added_keys:
            del sys.modules[k]
        for k, v in saved_modules.items():
            if k not in sys.modules or sys.modules[k] is not v:
                sys.modules[k] = v

    return _classify_query


class RouterAccuracyEvaluator:
    """评估 Router 的 classify_query() 是否输出正确的复杂度等级。"""

    dimension = EvalDimension.ROUTER_ACCURACY

    async def evaluate(self, case: dict[str, Any]) -> EvalResult:
        """评估单个用例的 Router 分类准确性。"""
        classify_query = _get_classify_query()

        user_message: str = case["user_message"]
        expected_complexity: str = case["expected_complexity"]

        complexity, intent_summary = classify_query(user_message)
        actual = complexity.value

        passed = actual == expected_complexity

        return EvalResult(
            case_id=case["id"],
            dimension=self.dimension,
            passed=passed,
            score=1.0 if passed else 0.0,
            details={
                "expected_complexity": expected_complexity,
                "actual_complexity": actual,
                "intent_summary": intent_summary,
            },
        )
