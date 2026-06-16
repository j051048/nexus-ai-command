from types import SimpleNamespace

import pytest

from app.services.plugin_marketplace_service import PluginMarketplaceService


class AsyncQuery:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.executed = False
        self.operations: list[tuple[str, object]] = []

    def select(self, value: str) -> "AsyncQuery":
        self.operations.append(("select", value))
        return self

    def eq(self, key: str, value: object) -> "AsyncQuery":
        self.operations.append(("eq", (key, value)))
        return self

    def upsert(self, value: dict, on_conflict: str | None = None) -> "AsyncQuery":
        self.operations.append(("upsert", (value, on_conflict)))
        return self

    def delete(self) -> "AsyncQuery":
        self.operations.append(("delete", None))
        return self

    def update(self, value: dict) -> "AsyncQuery":
        self.operations.append(("update", value))
        return self

    async def execute(self) -> SimpleNamespace:
        self.executed = True
        return SimpleNamespace(data=self.rows)


class AsyncDB:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self.rows = rows or []
        self.queries: list[AsyncQuery] = []

    def table(self, name: str) -> AsyncQuery:
        query = AsyncQuery(self.rows)
        query.operations.append(("table", name))
        self.queries.append(query)
        return query


@pytest.mark.asyncio
async def test_list_plugins_awaits_async_execute() -> None:
    service = PluginMarketplaceService()
    db = AsyncDB(
        [
            {
                "plugin_id": "plugin_kingdee",
                "is_active": True,
                "config": {"api_url": "https://kingdee.example.com", "api_key": "secret"},
                "updated_at": "2026-06-16T00:00:00Z",
            }
        ]
    )

    plugins = await service.list_plugins(org_id="org-1", db=db)

    kingdee = next(plugin for plugin in plugins if plugin["id"] == "plugin_kingdee")
    assert kingdee["installed"] is True
    assert kingdee["connection_status"] == "configured"
    assert db.queries[0].executed is True


@pytest.mark.asyncio
async def test_get_installed_plugins_awaits_async_execute() -> None:
    service = PluginMarketplaceService()
    db = AsyncDB(
        [
            {
                "plugin_id": "plugin_email_digest",
                "is_active": True,
                "config": {"recipients": "ops@example.com"},
                "installed_at": "2026-06-16T00:00:00Z",
                "updated_at": "2026-06-16T00:00:00Z",
            }
        ]
    )

    installed = await service.get_installed_plugins("org-1", db=db)

    assert [plugin["id"] for plugin in installed] == ["plugin_email_digest"]
    assert installed[0]["connection_status"] == "ready"
    assert db.queries[0].executed is True


@pytest.mark.asyncio
async def test_plugin_mutations_await_async_execute() -> None:
    service = PluginMarketplaceService()
    db = AsyncDB()

    await service.install_plugin(
        "org-1",
        "plugin_email_digest",
        {"recipients": "ops@example.com"},
        db=db,
    )
    await service.update_plugin_config(
        "org-1",
        "plugin_email_digest",
        {"recipients": "owner@example.com"},
        db=db,
    )
    await service.uninstall_plugin("org-1", "plugin_email_digest", db=db)

    assert [query.executed for query in db.queries] == [True, True, True]
