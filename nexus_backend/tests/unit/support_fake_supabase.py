"""In-memory stand-in for the PostgREST query builder used by unit tests.

It supports exactly the chain shapes the backup and retention sweeps use, and
it deliberately models one detail real PostgREST has: an ``update`` whose
filters match no row returns an empty representation rather than raising. That
is what makes the schedule claim a real compare-and-set in the tests.
"""

from __future__ import annotations

import uuid
from typing import Any


class FakeResponse:
    def __init__(self, data: Any) -> None:
        self.data = data

    def __bool__(self) -> bool:
        return bool(self.data)


def _matches(row: dict, filters: list[tuple[str, str, Any, bool]]) -> bool:
    for column, operator, value, negate in filters:
        actual = row.get(column)
        if operator == "eq":
            hit = actual == value
        elif operator == "in":
            hit = actual in value
        elif operator == "is":
            hit = (actual is None) if value == "null" else actual == value
        elif operator == "lt":
            hit = actual is not None and str(actual) < str(value)
        elif operator == "lte":
            hit = actual is not None and str(actual) <= str(value)
        elif operator == "gte":
            hit = actual is not None and str(actual) >= str(value)
        else:  # pragma: no cover - unknown operator is a test bug
            raise AssertionError(f"unsupported operator {operator}")
        if negate:
            hit = not hit
        if not hit:
            return False
    return True


class FakeQuery:
    def __init__(self, client: FakeSupabaseClient, table_name: str) -> None:
        self._client = client
        self._table_name = table_name
        self._filters: list[tuple[str, str, Any, bool]] = []
        self._operation = "select"
        self._payload: Any = None
        self._on_conflict: str | None = None
        self._single = False
        self._limit: int | None = None
        self._order: tuple[str, bool] | None = None
        self._negate_next = False

    @property
    def not_(self) -> FakeQuery:
        self._negate_next = True
        return self

    def _filter(self, operator: str, column: str, value: Any) -> FakeQuery:
        self._filters.append((column, operator, value, self._negate_next))
        self._negate_next = False
        return self

    def select(self, *_columns: str) -> FakeQuery:
        self._operation = "select"
        return self

    def insert(self, payload: Any) -> FakeQuery:
        self._operation = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict) -> FakeQuery:
        self._operation = "update"
        self._payload = payload
        return self

    def upsert(self, payload: Any, on_conflict: str | None = None) -> FakeQuery:
        self._operation = "upsert"
        self._payload = payload
        self._on_conflict = on_conflict
        return self

    def delete(self) -> FakeQuery:
        self._operation = "delete"
        return self

    def eq(self, column: str, value: Any) -> FakeQuery:
        return self._filter("eq", column, value)

    def in_(self, column: str, value: Any) -> FakeQuery:
        return self._filter("in", column, value)

    def is_(self, column: str, value: Any) -> FakeQuery:
        return self._filter("is", column, value)

    def lt(self, column: str, value: Any) -> FakeQuery:
        return self._filter("lt", column, value)

    def lte(self, column: str, value: Any) -> FakeQuery:
        return self._filter("lte", column, value)

    def gte(self, column: str, value: Any) -> FakeQuery:
        return self._filter("gte", column, value)

    def order(self, column: str, desc: bool = False) -> FakeQuery:
        self._order = (column, desc)
        return self

    def limit(self, count: int) -> FakeQuery:
        self._limit = count
        return self

    def single(self) -> FakeQuery:
        self._single = True
        return self

    def maybe_single(self) -> FakeQuery:
        self._single = True
        return self

    async def execute(self) -> FakeResponse:
        rows = self._client.tables.setdefault(self._table_name, [])
        matched = [row for row in rows if _matches(row, self._filters)]

        if self._operation == "select":
            selected = matched
            if self._order:
                column, desc = self._order
                selected = sorted(
                    selected, key=lambda row: str(row.get(column)), reverse=desc
                )
            if self._limit is not None:
                selected = selected[: self._limit]
            if self._single:
                return FakeResponse(selected[0] if selected else None)
            return FakeResponse(selected)

        if self._operation == "insert":
            inserted = self._normalize(self._payload)
            rows.extend(inserted)
            self._client.writes.append((self._table_name, "insert", inserted))
            return FakeResponse(inserted)

        if self._operation == "update":
            for row in matched:
                row.update(self._payload)
            self._client.writes.append((self._table_name, "update", list(matched)))
            return FakeResponse(matched)

        if self._operation == "upsert":
            upserted: list[dict] = []
            for candidate in self._normalize(self._payload):
                key = self._on_conflict or "id"
                existing = next(
                    (row for row in rows if row.get(key) == candidate.get(key)), None
                )
                if existing:
                    existing.update(candidate)
                    upserted.append(existing)
                else:
                    rows.append(candidate)
                    upserted.append(candidate)
            self._client.writes.append((self._table_name, "upsert", upserted))
            return FakeResponse(upserted)

        removed = list(matched)
        for row in removed:
            rows.remove(row)
        self._client.writes.append((self._table_name, "delete", removed))
        return FakeResponse(removed)

    def _normalize(self, payload: Any) -> list[dict]:
        entries = payload if isinstance(payload, list) else [payload]
        normalized = []
        for entry in entries:
            row = dict(entry)
            row.setdefault("id", str(uuid.uuid4()))
            normalized.append(row)
        return normalized


class FakeSupabaseClient:
    """Minimal in-memory database for backup and retention sweeps."""

    def __init__(self, tables: dict[str, list[dict]] | None = None) -> None:
        self.tables: dict[str, list[dict]] = {
            name: [dict(row) for row in rows]
            for name, rows in (tables or {}).items()
        }
        self.writes: list[tuple[str, str, list[dict]]] = []

    def table(self, name: str) -> FakeQuery:
        return FakeQuery(self, name)

    def rows(self, name: str) -> list[dict]:
        return self.tables.setdefault(name, [])
