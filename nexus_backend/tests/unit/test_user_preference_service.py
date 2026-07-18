from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.user_preference_service import (
    UserPreferenceService,
    _cache,
)


class _AsyncQuery:
    def __init__(self, responses):
        self.execute = AsyncMock(side_effect=responses)

    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: self


@pytest.fixture(autouse=True)
def clear_preference_cache():
    _cache.clear()
    yield
    _cache.clear()


def _mock_database(*responses):
    query = _AsyncQuery(list(responses))
    database = MagicMock()
    database.table.return_value = query
    return database, query


@pytest.mark.asyncio
async def test_record_feedback_awaits_database_write():
    database, query = _mock_database(SimpleNamespace(data=[]))

    with patch("app.core.database.supabase", database):
        await UserPreferenceService().record_feedback(
            "user-1", "task_reminder", "clicked"
        )

    query.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_preferences_awaits_settings_and_statistics_queries():
    database, query = _mock_database(
        SimpleNamespace(data=[{"active_hours_start": 8, "active_hours_end": 17}]),
        SimpleNamespace(data=[]),
    )

    with patch("app.core.database.supabase", database):
        preferences = await UserPreferenceService().get_user_preferences("user-1")

    assert preferences["active_hours"] == [8, 17]
    assert query.execute.await_count == 2


@pytest.mark.asyncio
async def test_update_settings_awaits_upsert_before_reloading():
    database, query = _mock_database(
        SimpleNamespace(data=[]),
        SimpleNamespace(data=[{"daily_notification_limit": 3}]),
        SimpleNamespace(data=[]),
    )

    with patch("app.core.database.supabase", database):
        preferences = await UserPreferenceService().update_settings(
            "user-1", {"daily_notification_limit": 3}
        )

    assert preferences["daily_limit"] == 3
    assert query.execute.await_count == 3
