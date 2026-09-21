"""Compatibility shim for postgrest ``maybe_single()``.

``supabase==2.11.0`` pins ``postgrest>=0.19,<0.20``.  Since postgrest-py 0.16
``maybe_single().execute()`` returns ``None`` when the query matched zero rows
and raises ``APIError(code="204")`` when the response was empty for any other
reason.  The application was written against the older contract, where the call
always returned a response object whose ``.data`` was ``None``.

The result is that every unguarded ``result.data`` read crashes on the *no
row* path.  In production this surfaces as::

    ERROR [app.services.system_config_service:94] 获取配置失败:
        'NoneType' object has no attribute 'data'
    WARNING [app.services.ai_execution_policy_service:481]
        AI execution policy unavailable; using safe defaults org=...

for any tenant that never saved a custom policy - i.e. almost all of them.
There are roughly 150 ``maybe_single()`` call sites, so the fix belongs here
rather than in each caller.

Contract restored by this shim:

* zero rows -> :class:`MaybeSingleResponse`, a *falsy* object whose ``.data``
  is ``None``.  Both ``if result:`` and ``if result.data:`` stay meaningful,
  and ``return result.data if result else None`` keeps working;
* a matched row -> the untouched postgrest response;
* every other ``APIError`` still propagates with its original code.

The last point matters: postgrest's own ``maybe_single()`` swallows *any*
``APIError`` from the underlying single-row request and replaces it with a
synthetic ``code="204"`` "Missing response" error.  That erases the real error
category (RLS denial, 5xx, bad column) for roughly 150 call sites.  The shim
therefore calls the single-row builder directly and keeps only the genuine
no-row signals, instead of wrapping the masking implementation.

The shim is installed once, on import, for both the sync and async builders.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# PostgREST signals "no rows" either by returning nothing or by raising an
# APIError carrying one of these codes.
_NO_ROW_CODES = {"204", "PGRST116"}

_INSTALLED = False


class MaybeSingleResponse:
    """Minimal stand-in for a postgrest response that matched no row.

    It deliberately evaluates falsy when there is no data, because call sites
    use both ``if result:`` and ``if result.data:``.  A real postgrest
    response object is always truthy, so returning one here would resurrect
    the ``None["key"]`` crashes this shim exists to prevent.
    """

    __slots__ = ("count", "data")

    def __init__(self, data: Any = None) -> None:
        self.data = data
        self.count = None

    def __bool__(self) -> bool:
        return bool(self.data)

    def __len__(self) -> int:
        return len(self.data) if hasattr(self.data, "__len__") else 0

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "MaybeSingleResponse(data=None)"


def is_no_row_error(error: BaseException) -> bool:
    """Return True when an ``APIError`` only means 'the query matched no row'."""
    code = str(getattr(error, "code", "") or "")
    if code in _NO_ROW_CODES:
        return True
    details = str(getattr(error, "details", "") or "")
    message = str(getattr(error, "message", "") or "")
    return "0 rows" in details or "0 rows" in message


def _empty_response() -> MaybeSingleResponse:
    return MaybeSingleResponse()


def _build_execute(builder_cls: Any, single_cls: Any, api_error_cls: Any) -> Any:
    """Return a replacement ``execute`` for a sync maybe-single builder."""

    def execute(self: Any) -> Any:
        try:
            result = single_cls.execute(self)
        except api_error_cls as error:
            if is_no_row_error(error):
                return _empty_response()
            raise
        if not result:
            return _empty_response()
        return result

    return execute


def _build_aexecute(builder_cls: Any, single_cls: Any, api_error_cls: Any) -> Any:
    """Return a replacement ``execute`` for an async maybe-single builder."""

    async def execute(self: Any) -> Any:
        try:
            result = await single_cls.execute(self)
        except api_error_cls as error:
            if is_no_row_error(error):
                return _empty_response()
            raise
        if not result:
            return _empty_response()
        return result

    return execute


def _install_one(builder_cls: Any, replacement: Any) -> bool:
    original = builder_cls.execute
    if getattr(original, "_nexus_maybe_single_compat", False):
        return False
    replacement._nexus_maybe_single_compat = True
    replacement.__doc__ = original.__doc__
    builder_cls.execute = replacement
    return True


def install_maybe_single_compat() -> bool:
    """Patch both request builders.  Idempotent; returns True when installed."""
    global _INSTALLED
    if _INSTALLED:
        return True
    try:
        from postgrest._async.request_builder import (
            AsyncMaybeSingleRequestBuilder,
            AsyncSingleRequestBuilder,
        )
        from postgrest._sync.request_builder import (
            SyncMaybeSingleRequestBuilder,
            SyncSingleRequestBuilder,
        )
        from postgrest.exceptions import APIError
    except ImportError:  # pragma: no cover - postgrest is a hard dependency
        logger.debug("[PostgrestCompat] postgrest is unavailable; no shim needed")
        return False

    patched = _install_one(
        AsyncMaybeSingleRequestBuilder,
        _build_aexecute(
            AsyncMaybeSingleRequestBuilder, AsyncSingleRequestBuilder, APIError
        ),
    )
    patched |= _install_one(
        SyncMaybeSingleRequestBuilder,
        _build_execute(
            SyncMaybeSingleRequestBuilder, SyncSingleRequestBuilder, APIError
        ),
    )
    _INSTALLED = True
    if patched:
        logger.debug(
            "[PostgrestCompat] maybe_single() now returns an empty response "
            "instead of None when no row matches"
        )
    return True
