"""The backup sweeps: due schedules, expiry, and integrity verification.

These lock the behaviour that was missing before: ``backup_schedules`` is
actually executed, a losing worker does not double-run an organization, a
failed organization is recorded instead of taking the batch down, and expired
backups release both their row and their off-site object.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services import backup_lifecycle
from app.services.backup_service import backup_service
from app.services.backup_storage import (
    BackupStorageUnavailableError,
    build_backup_storage,
    canonical_payload,
    checksum_for,
)
from tests.unit.support_fake_supabase import FakeSupabaseClient

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


class _FilesystemSettings:
    BACKUP_STORAGE_BACKEND = "filesystem"
    BACKUP_STORAGE_PATH = "/tmp/nexus-backup-tests"
    BACKUP_RETENTION_DAYS = 30
    BACKUP_VERIFY_AFTER_WRITE = True
    BACKUP_SCHEDULE_BATCH_LIMIT = 10


def _schedule_row(**overrides) -> dict:
    row = {
        "id": "sched-1",
        "organization_id": "org-1",
        "frequency": "daily",
        "tables": ["customers"],
        "is_active": True,
        "next_backup_at": (NOW - timedelta(minutes=5)).isoformat(),
        "last_status": None,
        "last_error": None,
    }
    row.update(overrides)
    return row


def _client_with(*rows: dict) -> FakeSupabaseClient:
    client = FakeSupabaseClient({"backup_schedules": list(rows)})
    client.tables["customers"] = [{"id": "c1", "organization_id": "org-1"}]
    return client


@pytest.fixture
def filesystem_settings(tmp_path, monkeypatch):
    settings = _FilesystemSettings()
    settings.BACKUP_STORAGE_PATH = str(tmp_path)
    monkeypatch.setattr(backup_lifecycle, "settings", settings)
    monkeypatch.setattr("app.services.backup_service.settings", settings)
    return settings


async def test_due_schedule_creates_backup_and_reschedules(
    filesystem_settings, tmp_path
) -> None:
    client = _client_with(_schedule_row())

    counters = await backup_lifecycle.run_due_backup_schedules(client, now=NOW)

    assert counters == {"due": 1, "completed": 1, "failed": 0, "skipped": 0}
    records = client.rows("backup_records")
    assert len(records) == 1
    record = records[0]
    assert record["backup_type"] == "auto"
    assert record["storage_backend"] == "filesystem"
    assert record["storage_ref"].startswith(str(tmp_path))
    # External backends must not duplicate the payload inside the database.
    assert record["data"] == {}
    assert record["verified_at"]

    schedule = client.rows("backup_schedules")[0]
    assert schedule["last_status"] == "completed"
    assert schedule["last_backup_id"] == record["id"]
    assert schedule["claimed_at"] is None
    assert schedule["next_backup_at"] == (NOW + timedelta(days=1)).isoformat()


async def test_schedule_claim_is_a_compare_and_set() -> None:
    client = _client_with(_schedule_row())
    snapshot = dict(client.rows("backup_schedules")[0])

    first = await backup_lifecycle._claim_schedule(client, snapshot, NOW)
    second = await backup_lifecycle._claim_schedule(client, snapshot, NOW)

    assert first == (NOW + timedelta(days=1)).isoformat()
    # The second worker still holds the pre-claim snapshot, so its update
    # matches no row and it must not run the same organization twice.
    assert second is None


async def test_weekly_and_monthly_frequencies_reschedule_correctly() -> None:
    weekly = await backup_lifecycle._claim_schedule(
        _client_with(_schedule_row(frequency="weekly")),
        _schedule_row(frequency="weekly"),
        NOW,
    )
    monthly = await backup_lifecycle._claim_schedule(
        _client_with(_schedule_row(frequency="monthly")),
        _schedule_row(frequency="monthly"),
        NOW,
    )

    assert weekly == (NOW + timedelta(weeks=1)).isoformat()
    assert monthly == (NOW + timedelta(days=30)).isoformat()


async def test_inactive_or_future_schedules_are_ignored() -> None:
    client = _client_with(
        _schedule_row(id="inactive", is_active=False),
        _schedule_row(id="future", next_backup_at=(NOW + timedelta(days=1)).isoformat()),
    )

    counters = await backup_lifecycle.run_due_backup_schedules(client, now=NOW)

    assert counters == {"due": 0, "completed": 0, "failed": 0, "skipped": 0}
    assert client.rows("backup_records") == []


async def test_one_failing_organization_does_not_stop_the_batch(
    filesystem_settings, monkeypatch
) -> None:
    client = _client_with(
        _schedule_row(id="sched-1", organization_id="org-1"),
        _schedule_row(id="sched-2", organization_id="org-2"),
    )
    original = backup_service.create_backup

    async def _flaky(org_id, **kwargs):
        if org_id == "org-1":
            raise BackupStorageUnavailableError("bucket unreachable")
        return await original(org_id=org_id, **kwargs)

    monkeypatch.setattr(backup_service, "create_backup", _flaky)

    counters = await backup_lifecycle.run_due_backup_schedules(client, now=NOW)

    assert counters == {"due": 2, "completed": 1, "failed": 1, "skipped": 0}
    failed = next(r for r in client.rows("backup_schedules") if r["id"] == "sched-1")
    assert failed["last_status"] == "failed"
    assert "bucket unreachable" in failed["last_error"]
    succeeded = next(r for r in client.rows("backup_schedules") if r["id"] == "sched-2")
    assert succeeded["last_status"] == "completed"


async def test_expiry_deletes_rows_and_off_site_objects(
    filesystem_settings, tmp_path
) -> None:
    payload = canonical_payload({"customers": [{"id": "c1"}]})
    checksum = checksum_for(payload)
    storage = build_backup_storage(filesystem_settings)
    expired_ref = storage.store(
        org_id="org-1", label="auto", payload=payload, checksum=checksum
    )
    kept_ref = storage.store(
        org_id="org-1", label="auto", payload=payload, checksum=checksum
    )

    client = FakeSupabaseClient(
        {
            "backup_records": [
                {
                    "id": "expired",
                    "organization_id": "org-1",
                    "storage_backend": "filesystem",
                    "storage_ref": expired_ref,
                    "expires_at": (NOW - timedelta(days=1)).isoformat(),
                },
                {
                    "id": "kept",
                    "organization_id": "org-1",
                    "storage_backend": "filesystem",
                    "storage_ref": kept_ref,
                    "expires_at": (NOW + timedelta(days=10)).isoformat(),
                },
                {
                    "id": "no-expiry",
                    "organization_id": "org-1",
                    "storage_backend": "database",
                    "storage_ref": None,
                    "expires_at": None,
                },
            ]
        }
    )

    result = await backup_lifecycle.expire_expired_backups(client, now=NOW)

    assert result == {"expired": 1, "checked": 1}
    remaining = {row["id"] for row in client.rows("backup_records")}
    assert remaining == {"kept", "no-expiry"}
    # The object behind "kept" is still referenced, so it must survive; the
    # expired record's object is gone with its row.
    assert storage.load(kept_ref) == payload
    assert not Path(expired_ref).exists()


async def test_expiry_keeps_rows_when_object_deletion_fails(
    filesystem_settings, monkeypatch
) -> None:
    client = FakeSupabaseClient(
        {
            "backup_records": [
                {
                    "id": "expired",
                    "organization_id": "org-1",
                    "storage_backend": "filesystem",
                    "storage_ref": "/tmp/gone.json",
                    "expires_at": (NOW - timedelta(days=1)).isoformat(),
                }
            ]
        }
    )

    class _FailingStorage:
        backend = "filesystem"

        def delete(self, ref):
            raise BackupStorageUnavailableError("bucket offline")

    monkeypatch.setattr(
        "app.services.backup_service.build_backup_storage",
        lambda _settings: _FailingStorage(),
    )

    result = await backup_lifecycle.expire_expired_backups(client, now=NOW)

    assert result["expired"] == 1
    assert client.rows("backup_records") == []


async def test_verification_covers_database_backend_rows(filesystem_settings) -> None:
    payload = {"customers": [{"id": "c1"}]}
    client = FakeSupabaseClient(
        {
            "backup_records": [
                {
                    "id": "legacy",
                    "organization_id": "org-1",
                    "backup_type": "manual",
                    "tables_included": ["customers"],
                    "data": payload,
                    "checksum": None,
                    "storage_backend": "database",
                    "storage_ref": None,
                }
            ]
        }
    )

    outcome = await backup_service.verify_backup("legacy", db=client)

    assert outcome["verified"] is True
    assert outcome["method"] == "structure"
    assert outcome["row_counts"] == {"customers": 1}
    assert client.rows("backup_records")[0]["verified_at"] == outcome["verified_at"]


async def test_verification_detects_a_tampered_off_site_payload(
    filesystem_settings, tmp_path
) -> None:
    good = canonical_payload({"customers": [{"id": "c1"}]})
    ref = tmp_path / "org-1" / "payload.json"
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_bytes(canonical_payload({"customers": [{"id": "tampered"}]}))

    client = FakeSupabaseClient(
        {
            "backup_records": [
                {
                    "id": "external",
                    "organization_id": "org-1",
                    "tables_included": ["customers"],
                    "data": {},
                    "checksum": checksum_for(good),
                    "storage_backend": "filesystem",
                    "storage_ref": str(ref),
                }
            ]
        }
    )

    outcome = await backup_service.verify_backup("external", db=client)

    assert outcome["verified"] is False
    assert "checksum" in outcome["reason"]
    assert client.rows("backup_records")[0].get("verified_at") is None
