"""Bounded read-only probes; never expose connection strings or database rows."""

import asyncio
import os

REQUIRED_MIGRATIONS = {
    "20260909_001_artifact_stage_checkpoints.sql",
    "20260910_001_artifact_stage_checkpoint_policy.sql",
    "20260911_001_business_event_receipts.sql",
}


async def probe_deployment_dependencies() -> list[dict]:
    from app.core.database import supabase

    async def database():
        if supabase is None:
            return False
        result = (
            await supabase.table("migration_history")
            .select("name")
            .in_("name", sorted(REQUIRED_MIGRATIONS))
            .execute()
        )
        return {row["name"] for row in result.data or []} >= REQUIRED_MIGRATIONS

    async def redis():
        import redis.asyncio as aioredis

        url = os.getenv("REDIS_URL")
        if not url:
            return False
        client = aioredis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            return bool(await client.ping())
        finally:
            await client.aclose()

    async def checkpoint():
        from app.agent.checkpointer import get_checkpointer, is_checkpointer_persistent

        saver = get_checkpointer()
        if not is_checkpointer_persistent():
            return False
        await saver.aget_tuple(
            {
                "configurable": {
                    "thread_id": "nexus-readiness-probe",
                    "checkpoint_ns": "",
                }
            }
        )
        return True

    checks = []
    for name, probe in (
        ("database_migrations", database),
        ("redis_connectivity", redis),
        ("checkpoint_read", checkpoint),
    ):
        try:
            ok = await asyncio.wait_for(probe(), timeout=3)
        except (
            Exception
        ) as exc:  # broad-except: dependency health boundary; never return secrets
            checks.append(
                {
                    "name": name,
                    "ok": False,
                    "severity": "critical",
                    "message": type(exc).__name__,
                }
            )
        else:
            checks.append(
                {
                    "name": name,
                    "ok": ok,
                    "severity": "critical",
                    "message": "read_only_probe",
                }
            )
    return checks
