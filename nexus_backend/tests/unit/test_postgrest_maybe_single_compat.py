"""The maybe_single() shim must restore the pre-0.16 postgrest contract.

Regression context: with supabase 2.11 / postgrest 0.19 an unmatched
maybe_single() returns ``None``, so ``result.data`` raised
``AttributeError: 'NoneType' object has no attribute 'data'`` in every
optional-config read path (system config, tenant AI policy, and ~150 others).
"""

import pytest
from postgrest._async.request_builder import (
    AsyncMaybeSingleRequestBuilder,
    AsyncSingleRequestBuilder,
)
from postgrest._sync.request_builder import (
    SyncMaybeSingleRequestBuilder,
    SyncSingleRequestBuilder,
)
from postgrest.exceptions import APIError

from app.core import postgrest_compat


def _install() -> None:
    postgrest_compat._INSTALLED = False
    assert postgrest_compat.install_maybe_single_compat() is True
    assert postgrest_compat.install_maybe_single_compat() is True


def _sync_builder() -> SyncMaybeSingleRequestBuilder:
    return object.__new__(SyncMaybeSingleRequestBuilder)


def test_zero_rows_yields_a_falsy_response_instead_of_none(monkeypatch):
    monkeypatch.setattr(SyncSingleRequestBuilder, "execute", lambda self: None)
    _install()

    response = SyncMaybeSingleRequestBuilder.execute(_sync_builder())

    assert response is not None
    assert response.data is None
    assert bool(response) is False
    # The three legacy read patterns must all keep working.
    assert (response.data if response else None) is None
    assert (response.data or [None])[0] is None
    assert not response.data


def test_zero_row_api_error_is_normalised(monkeypatch):
    def _raise(self):
        raise APIError(
            {
                "message": "Missing response",
                "code": "204",
                "hint": "check traceback",
                "details": "Postgrest couldn't retrieve response",
            }
        )

    monkeypatch.setattr(SyncSingleRequestBuilder, "execute", _raise)
    _install()

    response = SyncMaybeSingleRequestBuilder.execute(_sync_builder())

    assert response.data is None
    assert not response


def test_generic_api_errors_still_propagate(monkeypatch):
    def _raise(self):
        raise APIError(
            {
                "message": "permission denied",
                "code": "42501",
                "hint": "row level security",
                "details": "insufficient privilege",
            }
        )

    monkeypatch.setattr(SyncSingleRequestBuilder, "execute", _raise)
    _install()

    with pytest.raises(APIError):
        SyncMaybeSingleRequestBuilder.execute(_sync_builder())


def test_matched_row_passes_through_untouched(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(SyncSingleRequestBuilder, "execute", lambda self: sentinel)
    _install()

    assert SyncMaybeSingleRequestBuilder.execute(_sync_builder()) is sentinel


def test_real_errors_keep_their_code_instead_of_becoming_a_fake_204(monkeypatch):
    """postgrest's own maybe_single() masks every APIError as code 204.

    That masking is why production lost the real error category and only saw
    "'NoneType' object has no attribute 'data'".  The shim must not inherit it.
    """

    def _raise(self):
        raise APIError(
            {
                "message": "permission denied for table artifacts",
                "code": "42501",
                "hint": "row level security",
                "details": "insufficient privilege",
            }
        )

    monkeypatch.setattr(SyncSingleRequestBuilder, "execute", _raise)
    _install()

    with pytest.raises(APIError) as captured:
        SyncMaybeSingleRequestBuilder.execute(_sync_builder())

    assert captured.value.code == "42501"


@pytest.mark.asyncio
async def test_async_zero_rows_yields_a_falsy_response(monkeypatch):
    async def _none(self):
        return None

    monkeypatch.setattr(AsyncSingleRequestBuilder, "execute", _none)
    _install()

    builder = object.__new__(AsyncMaybeSingleRequestBuilder)
    response = await AsyncMaybeSingleRequestBuilder.execute(builder)

    assert response is not None
    assert response.data is None
    assert not response


@pytest.mark.asyncio
async def test_async_matched_row_passes_through_untouched(monkeypatch):
    sentinel = object()

    async def _row(self):
        return sentinel

    monkeypatch.setattr(AsyncSingleRequestBuilder, "execute", _row)
    _install()

    builder = object.__new__(AsyncMaybeSingleRequestBuilder)
    assert await AsyncMaybeSingleRequestBuilder.execute(builder) is sentinel


def test_is_no_row_error_recognises_both_signals():
    assert postgrest_compat.is_no_row_error(
        APIError({"message": "x", "code": "PGRST116", "details": "", "hint": ""})
    )
    assert postgrest_compat.is_no_row_error(
        APIError(
            {
                "message": "JSON object requested, multiple (or no) rows returned",
                "code": "PGRST999",
                "details": "The result contains 0 rows",
                "hint": "",
            }
        )
    )
    assert not postgrest_compat.is_no_row_error(
        APIError({"message": "boom", "code": "500", "details": "", "hint": ""})
    )


def test_database_module_installs_the_shim_on_import():
    from postgrest._sync.request_builder import SyncMaybeSingleRequestBuilder

    import app.core.database  # noqa: F401  (import installs the shim)

    assert getattr(
        SyncMaybeSingleRequestBuilder.execute, "_nexus_maybe_single_compat", False
    )
