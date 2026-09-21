"""Token budget behaviour when REDIS_URL is set but unusable.

Regression guard for the production warning::

    WARNING [app.agent.stream_checks:72] [Stream] Token budget check failed
        (non-blocking): Redis URL must specify one of the following schemes
        (redis://, rediss://, unix://)

``redis.from_url()`` validates the scheme while building the client, so the
old code raised a ``ValueError`` that escaped the probe handler and surfaced
per request. A misconfigured cost guard-rail must degrade loudly, not turn
into a per-request error or a full AI outage.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.core.token_budget import BudgetVerdict, TokenBudgetManager


@pytest.fixture
def manager() -> TokenBudgetManager:
    return TokenBudgetManager()


async def test_unusable_redis_url_degrades_without_raising(
    manager: TokenBudgetManager,
) -> None:
    with patch("app.core.token_budget.settings") as settings:
        settings.ENV = "production"
        settings.REDIS_URL = "https://cache.zeabur.com:31000"
        settings.TOKEN_BUDGET_MEMORY_FALLBACK_ENABLED = False
        settings.TOKEN_BUDGET_MAX_PER_SESSION = 1000
        settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER = 10000
        settings.TOKEN_BUDGET_MAX_COST_PER_SESSION = 5.0

        # Must not raise ValueError out of the probe.
        assert await manager._get_redis() is None
        # Counters still work, so the guard-rail degrades instead of blocking.
        assert await manager._incr(manager._key("sess_tok", "s1"), 10, 60) == 10.0

        status = await manager.check_budget("s1", "u1")

    assert status.verdict == BudgetVerdict.OK


async def test_missing_redis_url_keeps_fail_closed_semantics(
    manager: TokenBudgetManager,
) -> None:
    with patch("app.core.token_budget.settings") as settings:
        settings.ENV = "production"
        settings.REDIS_URL = None
        settings.TOKEN_BUDGET_MEMORY_FALLBACK_ENABLED = False
        settings.TOKEN_BUDGET_MAX_PER_SESSION = 1000
        settings.TOKEN_BUDGET_MAX_PER_HOUR_PER_USER = 10000
        settings.TOKEN_BUDGET_MAX_COST_PER_SESSION = 5.0

        assert await manager._get_redis() is None
        # No Redis configured at all: production stays fail-closed.
        assert await manager._incr(manager._key("sess_tok", "s1"), 10, 60) == float(
            "inf"
        )

        status = await manager.check_budget("s1", "u1")

    assert status.verdict == BudgetVerdict.EXCEEDED


async def test_bare_host_port_is_repaired_before_connecting(
    manager: TokenBudgetManager,
) -> None:
    seen: list[str] = []

    def fake_from_url(url: str, **_kwargs: object) -> object:
        seen.append(url)
        raise OSError("no network in unit tests")

    with patch("app.core.token_budget.settings") as settings:
        settings.ENV = "production"
        settings.REDIS_URL = "hkg1.clusters.zeabur.com:31000"
        settings.TOKEN_BUDGET_MEMORY_FALLBACK_ENABLED = False

        with (
            patch("redis.asyncio.from_url", fake_from_url),
            patch("app.core.token_budget.os.getenv", return_value=None),
        ):
            assert await manager._get_redis() is None

    assert seen == ["redis://hkg1.clusters.zeabur.com:31000"]
