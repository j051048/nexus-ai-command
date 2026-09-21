"""Regression guard for the production error::

    ERROR [app.services.system_config_service:94] 获取配置失败:
        'NoneType' object has no attribute 'data'
    WARNING [app.services.ai_execution_policy_service:481] AI execution policy
        unavailable; using safe defaults org=...

``system_config_service.get_config`` reads ``result.data`` from a
``maybe_single()`` query. Before the postgrest shim a tenant with no saved
config hit the zero-row path, where newer postgrest returns ``None`` instead
of an empty response, so the read raised. This locks the no-row behaviour.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.postgrest_compat import MaybeSingleResponse, install_maybe_single_compat
from app.services.system_config_service import system_config_service


class _FakeQuery:
    """Minimal stand-in for a postgrest builder chain."""

    def __init__(self, result: Any) -> None:
        self._result = result

    def select(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
        return self

    def eq(self, *_args: Any, **_kwargs: Any) -> _FakeQuery:
        return self

    def maybe_single(self) -> _FakeQuery:
        return self

    async def execute(self) -> Any:
        return self._result


class _FakeClient:
    def __init__(self, result: Any) -> None:
        self._result = result

    def table(self, _name: str) -> _FakeQuery:
        return _FakeQuery(self._result)


async def test_get_config_returns_none_when_no_row_matches() -> None:
    # Exactly what the shim hands back for a zero-row maybe_single() query.
    client = _FakeClient(MaybeSingleResponse())

    assert await system_config_service.get_config("org-1", "ai", "policy", db=client) is None


async def test_get_config_returns_the_row_when_present() -> None:
    row = {"config_key": "policy", "config_value": {"mode": "strict"}}
    client = _FakeClient(MaybeSingleResponse(row))

    assert (
        await system_config_service.get_config("org-1", "ai", "policy", db=client)
        == row
    )


async def test_get_config_without_a_db_client_still_fails_loudly() -> None:
    with pytest.raises(RuntimeError):
        await system_config_service.get_config("org-1", "ai", "policy", db=None)


def test_shim_is_installed_on_import() -> None:
    # The service modules above import app.core.database transitively; the shim
    # must be active by the time any query runs.
    assert install_maybe_single_compat() is True
