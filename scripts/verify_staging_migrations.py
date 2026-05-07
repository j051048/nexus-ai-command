"""Verify that critical staging database migrations are present and protected.

The script is intentionally read-only. It exits 0 when no database URL is
configured, so CI can keep the job wired before staging secrets are added.
Use --require-db to make a missing database URL fail the run.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Iterable


CRITICAL_TABLES = {
    "agent_runs": {
        "columns": {
            "id",
            "run_id",
            "thread_id",
            "trace_id",
            "organization_id",
            "status",
            "metadata",
            "final_response",
            "started_at",
            "updated_at",
        },
        "policies": {"agent_runs_org_select", "agent_runs_service_write"},
    },
    "agent_tool_calls": {
        "columns": {
            "agent_run_id",
            "run_id",
            "organization_id",
            "tool_name",
            "tool_args",
            "error_type",
            "duration_ms",
        },
        "policies": {
            "agent_tool_calls_org_select",
            "agent_tool_calls_service_write",
        },
    },
    "agent_events": {
        "columns": {
            "agent_run_id",
            "run_id",
            "organization_id",
            "event_type",
            "node_name",
            "payload",
        },
        "policies": {"agent_events_org_select", "agent_events_service_write"},
    },
    "webhook_subscriptions": {
        "columns": {"organization_id", "url", "secret_hash", "is_active"},
        "policies": {
            "webhook_subscriptions_org_select",
            "webhook_subscriptions_org_insert",
            "webhook_subscriptions_org_update",
            "webhook_subscriptions_org_delete",
        },
    },
    "webhook_delivery_log": {
        "columns": {"organization_id", "subscription_id", "response_code", "response_body"},
        "policies": {
            "webhook_delivery_log_org_select",
            "webhook_delivery_log_service_insert",
        },
    },
    "vmd_reports": {
        "columns": {"organization_id", "report_type", "report_data"},
        "policies": {
            "vmd_reports_org_select",
            "vmd_reports_org_insert",
            "vmd_reports_org_update",
        },
    },
}


@dataclass
class Failure:
    table: str
    reason: str


def _env_database_url() -> str | None:
    return (
        os.getenv("STAGING_DATABASE_URL")
        or os.getenv("SUPABASE_DB_URL")
        or os.getenv("DATABASE_URL")
    )


def _fetch_set(cur, query: str, params: Iterable[object]) -> set[str]:
    cur.execute(query, tuple(params))
    return {str(row[0]) for row in cur.fetchall()}


def verify(database_url: str) -> list[Failure]:
    try:
        import psycopg
    except ImportError as exc:
        return [Failure("environment", f"psycopg is not installed: {exc}")]

    failures: list[Failure] = []
    with psycopg.connect(database_url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            for table, expected in CRITICAL_TABLES.items():
                cur.execute("select to_regclass(%s)", (f"public.{table}",))
                if cur.fetchone()[0] is None:
                    failures.append(Failure(table, "table is missing"))
                    continue

                columns = _fetch_set(
                    cur,
                    """
                    select column_name
                    from information_schema.columns
                    where table_schema = 'public' and table_name = %s
                    """,
                    (table,),
                )
                missing_columns = sorted(expected["columns"] - columns)
                if missing_columns:
                    failures.append(
                        Failure(table, f"missing columns: {', '.join(missing_columns)}")
                    )

                cur.execute(
                    """
                    select c.relrowsecurity
                    from pg_class c
                    join pg_namespace n on n.oid = c.relnamespace
                    where n.nspname = 'public' and c.relname = %s
                    """,
                    (table,),
                )
                row = cur.fetchone()
                if not row or row[0] is not True:
                    failures.append(Failure(table, "row level security is not enabled"))

                expected_policies = expected["policies"]
                if expected_policies:
                    policies = _fetch_set(
                        cur,
                        """
                        select policyname
                        from pg_policies
                        where schemaname = 'public' and tablename = %s
                        """,
                        (table,),
                    )
                    missing_policies = sorted(expected_policies - policies)
                    if missing_policies:
                        failures.append(
                            Failure(
                                table,
                                f"missing policies: {', '.join(missing_policies)}",
                            )
                        )

    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-db", action="store_true")
    args = parser.parse_args()

    database_url = _env_database_url()
    if not database_url:
        message = "STAGING_DATABASE_URL/SUPABASE_DB_URL/DATABASE_URL is not set"
        if args.require_db:
            print(f"ERROR: {message}", file=sys.stderr)
            return 1
        print(f"SKIP: {message}")
        return 0

    failures = verify(database_url)
    if failures:
        print("Staging migration verification failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure.table}: {failure.reason}", file=sys.stderr)
        return 1

    print("OK: critical staging migrations and RLS policies verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
