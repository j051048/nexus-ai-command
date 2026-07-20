"""Conservative runtime migration runner.

The canonical migration source is ``supabase/migrations`` at repository root.
Production deployments should normally use ``supabase db push``.  Runtime
execution is retained only for explicitly enabled private deployments and
fails closed when an already-applied migration has been modified.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = REPOSITORY_ROOT / "supabase" / "migrations"
MIGRATIONS_DIRS = [MIGRATIONS_DIR]
MIGRATION_PATTERN = re.compile(r"^(\d{8}[^/]*)\.sql$")
AUTO_MIGRATE = os.environ.get("AUTO_MIGRATE", "false").lower() in {
    "true",
    "1",
    "yes",
}


def migration_checksum(path: Path) -> str:
    """Return the immutable SHA-256 checksum stored with a migration."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def migration_files() -> list[Path]:
    """Return executable migrations in deterministic order."""
    if not MIGRATIONS_DIR.exists():
        raise RuntimeError(
            f"Canonical migration directory is missing: {MIGRATIONS_DIR}"
        )
    files = [
        path
        for path in MIGRATIONS_DIR.iterdir()
        if path.is_file() and MIGRATION_PATTERN.match(path.name)
    ]
    return sorted(files, key=lambda path: path.name)


async def _ensure_migration_table() -> bool:
    from app.core.database import supabase

    if not supabase:
        return False
    try:
        await supabase.rpc(
            "exec_sql",
            {
                "query": """
                CREATE TABLE IF NOT EXISTS public.migration_history (
                    id BIGSERIAL PRIMARY KEY,
                    migration_name TEXT NOT NULL UNIQUE,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    checksum TEXT NOT NULL DEFAULT ''
                );
                """
            },
        ).execute()
        return True
    except Exception:
        try:
            await supabase.table("migration_history").select("id").limit(1).execute()
            return True
        except Exception as exc:
            logger.warning("[MigrationRunner] migration_history unavailable: %s", exc)
            return False


async def _get_applied_migrations() -> dict[str, str]:
    from app.core.database import supabase

    if not supabase:
        return {}
    try:
        result = (
            await supabase.table("migration_history")
            .select("migration_name,checksum")
            .execute()
        )
        return {
            str(row["migration_name"]): str(row.get("checksum") or "")
            for row in (result.data or [])
        }
    except Exception as exc:
        logger.warning("[MigrationRunner] cannot read migration history: %s", exc)
        return {}


async def _record_migration(name: str, checksum: str) -> None:
    from app.core.database import supabase

    if not supabase:
        raise RuntimeError("Database client is unavailable")
    await (
        supabase.table("migration_history")
        .insert({"migration_name": name, "checksum": checksum})
        .execute()
    )


def validate_applied_checksums(applied: dict[str, str]) -> None:
    """Reject drift for migrations recorded by the runtime runner."""
    paths = {path.name: path for path in migration_files()}
    drifted: list[str] = []
    for name, recorded_checksum in applied.items():
        path = paths.get(name)
        if path and recorded_checksum and migration_checksum(path) != recorded_checksum:
            drifted.append(name)
    if drifted:
        raise RuntimeError(
            "Applied migration checksum drift detected: " + ", ".join(sorted(drifted))
        )


def _get_pending_migrations(
    applied: dict[str, str] | set[str],
) -> list[tuple[str, Path]]:
    applied_names = set(applied)
    return [
        (path.name, path)
        for path in migration_files()
        if path.name not in applied_names
    ]


async def run_migrations() -> list[str]:
    """Apply pending migrations only when ``AUTO_MIGRATE`` is explicitly enabled."""
    from app.core.database import supabase

    enabled = os.environ.get("AUTO_MIGRATE", "false").lower() in {
        "true",
        "1",
        "yes",
    }
    if not enabled:
        logger.info("[MigrationRunner] disabled; use supabase db push in deployments")
        return []
    if not supabase:
        raise RuntimeError("AUTO_MIGRATE is enabled but the database is unavailable")
    if not await _ensure_migration_table():
        raise RuntimeError(
            "AUTO_MIGRATE is enabled but migration_history is unavailable"
        )

    applied = await _get_applied_migrations()
    validate_applied_checksums(applied)
    pending = _get_pending_migrations(applied)
    if not pending:
        logger.info("[MigrationRunner] schema is current")
        return []

    applied_names: list[str] = []
    for name, path in pending:
        checksum = migration_checksum(path)
        logger.info("[MigrationRunner] applying %s", name)
        sql = path.read_text(encoding="utf-8")
        await supabase.rpc("exec_sql", {"query": sql}).execute()
        await _record_migration(name, checksum)
        applied_names.append(name)
    return applied_names
