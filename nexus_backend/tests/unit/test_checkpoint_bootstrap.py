"""Production checkpoint initialization without real database connections."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import unquote, urlsplit

import pytest

from app.agent import checkpointer


@pytest.fixture(autouse=True)
def isolated_checkpoint(monkeypatch):
    monkeypatch.setattr(checkpointer, "_checkpointer_instance", None)
    monkeypatch.setattr(checkpointer, "_checkpointer_persistent", False)
    monkeypatch.setattr(
        checkpointer,
        "settings",
        SimpleNamespace(
            DATABASE_URL=None,
            SUPABASE_URL="https://example.supabase.co",
            SUPABASE_DB_PASSWORD=None,
            SUPABASE_SERVICE_KEY="not-a-database-password",
            LANGGRAPH_CHECKPOINTER="postgres",
            IS_PRODUCTION=True,
        ),
    )


def test_api_key_is_never_used_as_database_password():
    with pytest.raises(ValueError, match="Configure DATABASE_URL"):
        checkpointer._build_postgres_url()


def test_database_password_is_url_encoded_and_uses_direct_port():
    password = "p@ss:/?# word"
    checkpointer.settings.SUPABASE_DB_PASSWORD = password
    parsed = urlsplit(checkpointer._build_postgres_url())
    assert unquote(parsed.password) == password
    assert parsed.hostname == "db.example.supabase.co"
    assert parsed.port == 5432 and parsed.query == "sslmode=require"


def test_explicit_dsn_is_used_for_private_or_pooler_deployments():
    dsn = "postgresql://tenant:password@pooler.internal:5432/agent?sslmode=require"
    checkpointer.settings.DATABASE_URL = dsn
    assert checkpointer._build_postgres_url() == dsn


@pytest.mark.parametrize("dsn", ["https://api.example/key", "postgresql:///database"])
def test_invalid_dsn_fails_before_opening_a_pool(dsn):
    checkpointer.settings.DATABASE_URL = dsn
    with pytest.raises(ValueError, match="DATABASE_URL"):
        checkpointer._build_postgres_url()


@pytest.mark.asyncio
async def test_setup_opens_pool_before_migrations_and_only_then_reports_persistence(
    monkeypatch,
):
    order = []

    async def opened(**kwargs):
        assert kwargs == {"wait": True, "timeout": 10}
        assert not checkpointer.is_checkpointer_persistent()
        order.append("open")

    async def setup():
        assert order == ["open"]
        assert not checkpointer.is_checkpointer_persistent()
        order.append("setup")

    saver = SimpleNamespace(
        conn=SimpleNamespace(open=AsyncMock(side_effect=opened)), setup=setup
    )
    monkeypatch.setattr(checkpointer, "get_checkpointer", lambda: saver)
    assert await checkpointer.setup_checkpointer() is saver
    assert order == ["open", "setup"]
    assert checkpointer.is_checkpointer_persistent()


@pytest.mark.asyncio
async def test_setup_failure_closes_pool_and_revokes_persistent_status(monkeypatch):
    pool = SimpleNamespace(open=AsyncMock(), close=AsyncMock())
    saver = SimpleNamespace(
        conn=pool, setup=AsyncMock(side_effect=RuntimeError("migration failed"))
    )
    monkeypatch.setattr(checkpointer, "_checkpointer_instance", saver)
    with pytest.raises(RuntimeError, match="migration failed"):
        await checkpointer.setup_checkpointer()
    pool.close.assert_awaited_once()
    assert not checkpointer.is_checkpointer_persistent()
    assert checkpointer._checkpointer_instance is None


@pytest.mark.parametrize(
    "factory", ["_create_memory_checkpointer", "_create_postgres_checkpointer"]
)
def test_configured_encryption_never_silently_downgrades(monkeypatch, factory):
    monkeypatch.setattr(
        checkpointer,
        "_build_encrypted_serde",
        MagicMock(side_effect=RuntimeError("invalid encryption")),
    )
    with pytest.raises(RuntimeError, match="invalid encryption"):
        getattr(checkpointer, factory)()


@pytest.mark.asyncio
async def test_postgres_pool_has_required_driver_options(monkeypatch):
    import langgraph.checkpoint.postgres.aio as saver_module
    import psycopg_pool
    from psycopg.rows import dict_row

    checkpointer.settings.DATABASE_URL = (
        "postgresql://test:password@db.internal:5432/test"
    )
    pool = MagicMock()
    factory = MagicMock(return_value=pool)
    monkeypatch.setattr(psycopg_pool, "AsyncConnectionPool", factory)
    monkeypatch.setattr(saver_module, "AsyncPostgresSaver", MagicMock())
    monkeypatch.setattr(checkpointer, "_build_encrypted_serde", lambda: None)
    checkpointer._create_postgres_checkpointer()
    assert factory.call_args.kwargs["open"] is False
    assert factory.call_args.kwargs["kwargs"] == {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
    }
