"""Bounded pagination with explicit completeness for operational summaries."""

from collections.abc import Callable
from typing import Any


async def collect_bounded_rows(
    query_factory: Callable[[], Any], *, cap: int = 5000, page_size: int = 500
) -> tuple[list[dict], bool]:
    rows: list[dict] = []
    while len(rows) < cap:
        size = min(page_size, cap - len(rows))
        result = await query_factory().range(len(rows), len(rows) + size - 1).execute()
        page = result.data or []
        rows.extend(page)
        if len(page) < size:
            return rows, True
    probe = await query_factory().range(cap, cap).execute()
    return rows, not bool(probe.data)
