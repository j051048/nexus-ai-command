from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.artifact_generation_job_service import _claim_job, artifact_job_health


class _RpcDb:
    def __init__(self):
        self.name = None
        self.payload = None

    def rpc(self, name, payload):
        self.name = name
        self.payload = payload
        return self

    async def execute(self):
        return SimpleNamespace(
            data=[
                {
                    "id": self.payload["p_job_id"],
                    "lease_token": "lease-1",
                    "status": "running",
                }
            ]
        )


class _HealthDb:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name):
        return self

    def select(self, *_columns):
        return self

    def eq(self, *_args):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _limit):
        return self

    async def execute(self):
        return SimpleNamespace(data=self.rows)


@pytest.mark.asyncio
async def test_claim_job_uses_atomic_rpc_with_bounded_lease():
    db = _RpcDb()
    row = await _claim_job(db, "job-1")

    assert db.name == "claim_artifact_generation_job"
    assert db.payload["p_job_id"] == "job-1"
    assert 30 <= db.payload["p_lease_seconds"] <= 900
    assert row["lease_token"] == "lease-1"


@pytest.mark.asyncio
async def test_job_health_marks_only_expired_running_leases_stale():
    now = datetime.now(UTC)
    health = await artifact_job_health(
        _HealthDb(
            [
                {
                    "status": "running",
                    "lease_expires_at": (now - timedelta(seconds=1)).isoformat(),
                    "recovery_count": 2,
                },
                {
                    "status": "running",
                    "lease_expires_at": (now + timedelta(minutes=1)).isoformat(),
                    "recovery_count": 0,
                },
                {"status": "completed", "recovery_count": 1},
            ]
        ),
        organization_id="org-1",
    )

    assert health["stale_running"] == 1
    assert health["recoveries"] == 3
    assert health["healthy"] is False


def test_migration_recovery_is_atomic_and_lease_scoped():
    root = Path(__file__).resolve().parents[3]
    sql = (root / "supabase/migrations/20260810_003_operational_closure.sql").read_text(
        encoding="utf-8"
    )

    assert "claim_artifact_generation_job" in sql
    assert "job.status = 'queued'" in sql
    assert "job.lease_expires_at < now()" in sql
    assert "recover_stale_artifact_generation_jobs" in sql
    assert "job.recovery_count + 1" in sql
