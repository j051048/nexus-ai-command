"""Behavioral tests for the human review gate on artifact learning candidates.

The gate matters because a learning candidate is the only path from an
LLM-generated draft into the golden-template library.  These tests pin the
transition rules, not the implementation details.
"""

import pytest

from app.services.artifact_feedback_loop import (
    list_learning_candidates,
    review_learning_candidate,
)


class _Query:
    def __init__(self, rows):
        self._rows = rows
        self.filters = []
        self.mode = "select"
        self.payload = None

    def select(self, *columns):
        self.mode = "select"
        return self

    def update(self, payload):
        self.mode = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, list(values)))
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, count):
        return self

    async def execute(self):
        if self.mode == "update":
            return _Result([self.payload] if self._rows else [])
        return _Result(list(self._rows))


class _Result:
    def __init__(self, data):
        self.data = data


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.last_query = None

    def table(self, name):
        assert name == "artifact_feedback_events", name
        self.last_query = _Query(self.rows)
        return self.last_query


@pytest.mark.asyncio
async def test_review_approves_candidate_with_reviewer_audit_trail():
    db = _FakeDb(rows=[{"id": "evt-1"}])

    result = await review_learning_candidate(
        db,
        organization_id="org-1",
        event_id="evt-1",
        status="approved",
        reviewer_id="admin-1",
        note="模板值得沉淀",
    )

    assert result["ok"] is True
    assert result["learning_status"] == "approved"
    assert result["auto_apply"] is False
    payload = db.last_query.payload
    assert payload["learning_status"] == "approved"
    assert payload["reviewed_by"] == "admin-1"
    assert payload["review_note"] == "模板值得沉淀"
    assert payload["reviewed_at"]
    # The write is tenant-scoped and only applies to still-open candidates.
    assert ("eq", "organization_id", "org-1") in db.last_query.filters
    assert ("in", "learning_status", ["recorded", "review_candidate"]) in (
        db.last_query.filters
    )


@pytest.mark.asyncio
async def test_review_rejects_unknown_decision_without_writing():
    db = _FakeDb(rows=[{"id": "evt-1"}])

    result = await review_learning_candidate(
        db,
        organization_id="org-1",
        event_id="evt-1",
        status="review_candidate",
        reviewer_id="admin-1",
    )

    assert result["ok"] is False
    assert result["error"] == "invalid_review_status"
    assert db.last_query is None, "an invalid decision must not touch the database"


@pytest.mark.asyncio
async def test_review_reports_already_reviewed_candidate():
    db = _FakeDb(rows=[])

    result = await review_learning_candidate(
        db,
        organization_id="org-1",
        event_id="evt-closed",
        status="approved",
        reviewer_id="admin-2",
    )

    assert result["ok"] is False
    assert result["error"] == "candidate_not_found_or_already_reviewed"
    assert result["auto_apply"] is False


@pytest.mark.asyncio
async def test_list_learning_candidates_defaults_to_open_queue():
    db = _FakeDb(rows=[{"id": "evt-1"}, {"id": "evt-2"}])

    result = await list_learning_candidates(db, organization_id="org-1")

    assert result["available"] is True
    assert result["statuses"] == ["recorded", "review_candidate"]
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_list_learning_candidates_rejects_unknown_status():
    db = _FakeDb(rows=[])

    result = await list_learning_candidates(
        db, organization_id="org-1", status="whatever"
    )

    assert result["available"] is False
    assert result["error"] == "unsupported_status"
    assert "approved" in result["allowed"]
