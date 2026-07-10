"""Runtime contracts that must stay aligned with durable database schemas."""

import re
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.agent.roles.registry import RoleConfig
from app.services.llm_gateway.call_logging import CallLoggingMixin
from app.services.llm_quota_service import _quota_configs_from_row
from app.services.scheduled_task_runner import ScheduledTaskRunner
from app.tools.base_tool import BaseTool, ToolActionType, ToolRiskLevel


class _LoggingHarness(CallLoggingMixin):
    _LOG_BATCH_SIZE = 10
    _LOG_FLUSH_INTERVAL = 60.0

    def __init__(self):
        self._log_buffer = []
        self._log_last_flush = time.time()


class _UnknownTool(BaseTool):
    name = "unknown_tool"
    description = "test"
    parameters = {"type": "object", "properties": {}}

    async def run(self, args, user_id, config=None):
        return "ok"


class _ReadTool(_UnknownTool):
    name = "read_tool"

    @property
    def action_type(self):
        return ToolActionType.READ


@pytest.mark.asyncio
async def test_llm_call_log_uses_canonical_database_columns():
    harness = _LoggingHarness()
    await harness._log_call(
        org_id="00000000-0000-0000-0000-000000000001",
        model_code="deepseek-v4-flash",
        scene_code="test",
        agent_code="test_agent",
        user_id="00000000-0000-0000-0000-000000000002",
        request_id="req-1",
        status="success",
        input_tokens=10,
        output_tokens=5,
        cost=0.001,
        latency_ms=120,
    )

    row = harness._log_buffer[0]
    assert row["call_cost"] == 0.001
    assert row["exec_time_ms"] == 120
    assert row["error_message"] is None
    assert "create_time" in row
    assert "cost" not in row
    assert "latency_ms" not in row
    assert "id" not in row


def test_quota_rows_expand_to_daily_and_monthly_runtime_rules():
    configs = _quota_configs_from_row(
        {
            "tenant_id": "org-1",
            "quota_type": "model",
            "target_id": "deepseek-v4-flash",
            "daily_token_limit": 1000,
            "daily_cost_limit": 5,
            "monthly_token_limit": 20000,
            "monthly_cost_limit": 80,
            "daily_request_limit": 50,
            "overage_action": "block",
        },
        "org-1",
        123.0,
    )

    assert [config.period for config in configs] == ["daily", "monthly"]
    assert configs[0].model_code == "deepseek-v4-flash"
    assert configs[0].max_requests == 50
    assert configs[1].max_cost == 80


def test_unsupported_quota_scope_does_not_become_tenant_wide():
    assert (
        _quota_configs_from_row(
            {
                "quota_type": "department",
                "target_id": "sales",
                "daily_cost_limit": 5,
            },
            "org-1",
            123.0,
        )
        == []
    )


def test_unknown_tool_policy_is_fail_closed_and_not_cacheable():
    tool = _UnknownTool()
    assert tool.action_type == ToolActionType.UNKNOWN
    assert tool.risk_level == ToolRiskLevel.MEDIUM
    assert tool.has_side_effects is True
    assert tool.cacheable is False


def test_declared_read_tool_is_cacheable():
    tool = _ReadTool()
    assert tool.has_side_effects is False
    assert tool.cacheable is True


def test_empty_role_tool_whitelist_denies_all_tools():
    role = RoleConfig("empty", "Empty", "test", tool_whitelist=[])
    with patch("app.tools.get_all_tools_schema") as get_all:
        assert role.get_tool_schemas() == []
        get_all.assert_not_called()


@pytest.mark.asyncio
async def test_user_scheduler_claims_tasks_through_atomic_database_rpc(monkeypatch):
    class FakeDatabase:
        def __init__(self):
            self.calls = []

        def rpc(self, name, params):
            self.calls.append((name, params))
            return self

        async def execute(self):
            return SimpleNamespace(data=[])

    database = FakeDatabase()
    monkeypatch.setattr("app.core.database.supabase", database)

    await ScheduledTaskRunner().run_once()

    assert len(database.calls) == 1
    name, params = database.calls[0]
    assert name == "claim_due_user_scheduled_tasks"
    assert params["p_limit"] == 5
    assert params["p_worker_id"]


def test_user_scheduler_claim_rpc_uses_skip_locked():
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "20260710_p0_runtime_contract_convergence.sql"
    ).read_text(encoding="utf-8")

    assert "FOR UPDATE SKIP LOCKED" in migration
    assert "REVOKE ALL ON FUNCTION public.claim_due_user_scheduled_tasks" in migration


def test_llm_call_log_consumers_use_canonical_columns():
    root = Path(__file__).parents[2]
    source_paths = [
        root / "app" / "routers" / "dashboard.py",
        root / "app" / "routers" / "vmd_dashboard.py",
        root / "app" / "tasks" / "scheduler.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)

    legacy_selects = (
        "cost",
        "org_id",
        "cost_usd, total_tokens, duration_ms",
    )
    for columns in legacy_selects:
        pattern = rf'table\("llm_call_log"\)\s*\.select\("{re.escape(columns)}"\)'
        assert re.search(pattern, source) is None
