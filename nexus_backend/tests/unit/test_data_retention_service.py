"""Retention enforcement: the machinery behind the compliance API's claims."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.routers.compliance import data_retention_policy
from app.services import data_retention_service as retention
from tests.unit.support_fake_supabase import FakeSupabaseClient

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


class _Settings:
    DATA_RETENTION_ENFORCEMENT_ENABLED = True
    DATA_RETENTION_AUDIT_LOG_DAYS = 365
    DATA_RETENTION_CHAT_MESSAGE_DAYS = 90
    DATA_RETENTION_TOKEN_USAGE_DAYS = 180
    DATA_RETENTION_BATCH_SIZE = 500


@pytest.fixture
def retention_settings(monkeypatch):
    settings = _Settings()
    monkeypatch.setattr(retention, "settings", settings)
    # Keep the audit trail out of the assertion surface and off the network.
    monkeypatch.setattr(
        "app.services.audit_logger.audit_logger._enabled", False, raising=False
    )
    return settings


ORG_A = "org-a"
ORG_B = "org-b"


def _rows(
    table: str,
    days_old: int,
    count: int,
    time_column: str,
    org_column: str = "org_id",
    organization_id: str = ORG_A,
):
    stamp = (NOW - timedelta(days=days_old)).isoformat()
    return [
        {
            "id": f"{table}-{days_old}-{index}",
            time_column: stamp,
            org_column: organization_id,
        }
        for index in range(count)
    ]


def _client_with_history() -> FakeSupabaseClient:
    return FakeSupabaseClient(
        {
            "organizations": [{"id": ORG_A}, {"id": ORG_B}],
            "audit_logs": _rows("audit", 400, 2, "timestamp")
            + _rows("audit-fresh", 10, 1, "timestamp")
            + _rows("audit-b", 400, 1, "timestamp", organization_id=ORG_B),
            "chat_messages": _rows(
                "chat", 120, 2, "created_at", org_column="organization_id"
            )
            + _rows("chat-fresh", 5, 1, "created_at", org_column="organization_id")
            + _rows(
                "chat-b",
                120,
                1,
                "created_at",
                org_column="organization_id",
                organization_id=ORG_B,
            ),
            "user_token_usage": _rows("usage", 200, 2, "created_at")
            + _rows("usage-fresh", 5, 1, "created_at")
            + _rows("usage-b", 200, 1, "created_at", organization_id=ORG_B),
        }
    )


async def test_enforcement_disabled_leaves_data_untouched(monkeypatch) -> None:
    class _Disabled(_Settings):
        DATA_RETENTION_ENFORCEMENT_ENABLED = False

    settings = _Disabled()
    monkeypatch.setattr(retention, "settings", settings)
    client = _client_with_history()

    result = await retention.enforce_data_retention(client, now=NOW)

    assert result == {"enabled": False, "runs": []}
    assert len(client.rows("audit_logs")) == 4
    assert client.writes == []


async def test_enforcement_deletes_only_rows_past_the_window(retention_settings) -> None:
    client = _client_with_history()

    result = await retention.enforce_data_retention(client, now=NOW)

    assert result["enabled"] is True
    # Two organizations each contribute one expired row per policy.
    assert result["deleted_rows"] == 9
    assert [row["id"] for row in client.rows("audit_logs")] == ["audit-fresh-10-0"]
    assert [row["id"] for row in client.rows("chat_messages")] == ["chat-fresh-5-0"]
    assert [row["id"] for row in client.rows("user_token_usage")] == ["usage-fresh-5-0"]

    runs = {row["data_type"]: row for row in client.rows("data_retention_runs")}
    assert set(runs) == {"audit_logs", "chat_history", "token_usage"}
    assert runs["audit_logs"]["deleted_rows"] == 3
    assert runs["audit_logs"]["retention_days"] == 365
    assert runs["chat_history"]["cutoff"] == (NOW - timedelta(days=90)).isoformat()
    assert all(row["status"] == "completed" for row in runs.values())


async def test_enforcement_is_scoped_per_organization(retention_settings) -> None:
    client = _client_with_history()

    await retention.enforce_data_retention(client, now=NOW)

    org_columns = {
        "audit_logs": "org_id",
        "chat_messages": "organization_id",
        "user_token_usage": "org_id",
    }
    deletes = [entry for entry in client.writes if entry[1] == "delete"]
    assert deletes
    # Every delete batch carries exactly one organization id, so a malformed
    # row in one tenant cannot widen the blast radius to the others.
    for table, _operation, rows in deletes:
        assert len({row[org_columns[table]] for row in rows}) == 1


async def test_enforcement_is_bounded_by_batch_size(retention_settings) -> None:
    retention_settings.DATA_RETENTION_BATCH_SIZE = 2
    client = FakeSupabaseClient(
        {
            "organizations": [{"id": ORG_A}],
            "audit_logs": _rows("audit", 400, 5, "timestamp"),
            "chat_messages": [],
            "user_token_usage": [],
        }
    )

    result = await retention.enforce_data_retention(client, now=NOW)

    assert result["deleted_rows"] == 5
    assert client.rows("audit_logs") == []
    deletes = [entry for entry in client.writes if entry[1] == "delete"]
    # 2 + 2 + 1: three batches, then the loop stops on a short batch.
    assert [len(entry[2]) for entry in deletes] == [2, 2, 1]


async def test_one_failing_table_does_not_abort_the_others(
    retention_settings, monkeypatch
) -> None:
    client = _client_with_history()
    original = retention._delete_org_batch

    async def _flaky(db, policy, organization_id, cutoff, batch_size):
        if policy.data_type == "chat_history":
            raise RuntimeError("relation does not exist")
        return await original(db, policy, organization_id, cutoff, batch_size)

    monkeypatch.setattr(retention, "_delete_org_batch", _flaky)

    result = await retention.enforce_data_retention(client, now=NOW)

    runs = {row["data_type"]: row for row in client.rows("data_retention_runs")}
    assert runs["chat_history"]["status"] == "failed"
    assert "relation does not exist" in runs["chat_history"]["error_message"]
    assert runs["audit_logs"]["status"] == "completed"
    assert result["deleted_rows"] == 6


async def test_policy_snapshot_reports_whether_windows_are_enforced(monkeypatch) -> None:
    class _Off(_Settings):
        DATA_RETENTION_ENFORCEMENT_ENABLED = False

    disabled = retention.policy_snapshot(_Off())

    assert {policy["data_type"] for policy in disabled} == {
        "audit_logs",
        "chat_history",
        "token_usage",
    }
    assert all(policy["enforced"] is False for policy in disabled)
    assert {policy["retention_days"] for policy in disabled} == {365, 90, 180}

    enabled = retention.policy_snapshot(_Settings())
    assert all(policy["enforced"] is True for policy in enabled)


async def test_compliance_endpoint_reports_real_enforcement_state(
    retention_settings, monkeypatch
) -> None:
    async def _no_runs(limit: int = 5):
        return []

    monkeypatch.setattr(retention, "last_retention_runs", _no_runs, raising=False)

    payload = await data_retention_policy(req=None, user_id="user-1")

    data = payload["data"]
    assert data["enforcement_enabled"] is True
    assert data["last_runs"] == []
    documents = next(p for p in data["policies"] if p["data_type"] == "documents")
    # Documents are kept until deleted, so they must not claim enforcement.
    assert documents["enforced"] is False
    assert all(
        "enforced" in policy for policy in data["policies"] if policy["data_type"] != "documents"
    )
