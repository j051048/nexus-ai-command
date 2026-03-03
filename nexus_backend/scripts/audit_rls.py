"""
RLS Audit Script — checks all tables for Row Level Security policy coverage.

Usage:
    python -m scripts.audit_rls

Checks:
1. Which tables have RLS enabled vs disabled
2. Tables with organization_id column but no RLS
3. Known gaps that need attention
"""

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)

KNOWN_GAPS = [
    "webhook_delivery_log",
    "vmd_reports",
    "vmd_sub_task",
]


async def audit_rls():
    """Run the RLS audit against the connected Supabase/PostgreSQL database."""
    try:
        from app.core.database import supabase

        if not supabase:
            print("ERROR: No database connection available. Set SUPABASE_URL and SUPABASE_SERVICE_KEY.")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        sys.exit(1)

    print("=" * 60)
    print("  RLS Audit Report")
    print("=" * 60)

    # 1. Get all tables and their RLS status
    rls_query = """
    SELECT
        schemaname,
        tablename,
        rowsecurity
    FROM pg_tables
    WHERE schemaname = 'public'
    ORDER BY tablename;
    """

    try:
        result = await supabase.rpc("exec_sql", {"query": rls_query}).execute()
        tables = result.data if result.data else []
    except Exception:
        # Fallback: use information_schema
        result = await supabase.table("information_schema.tables").select(
            "table_name"
        ).eq("table_schema", "public").execute()
        tables = [{"tablename": r["table_name"], "rowsecurity": None} for r in (result.data or [])]

    rls_enabled = []
    rls_disabled = []

    for t in tables:
        name = t.get("tablename", "")
        if t.get("rowsecurity"):
            rls_enabled.append(name)
        else:
            rls_disabled.append(name)

    print(f"\n  Tables with RLS ENABLED ({len(rls_enabled)}):")
    for name in rls_enabled:
        print(f"    ✅ {name}")

    print(f"\n  Tables with RLS DISABLED ({len(rls_disabled)}):")
    for name in rls_disabled:
        marker = "⚠️ " if name in KNOWN_GAPS else "  "
        print(f"    {marker}{name}")

    # 2. Check tables with org_id but no RLS
    print("\n" + "-" * 60)
    print("  Tables with organization_id but NO RLS:")
    print("-" * 60)

    org_id_query = """
    SELECT table_name
    FROM information_schema.columns
    WHERE column_name = 'organization_id'
      AND table_schema = 'public'
    ORDER BY table_name;
    """

    try:
        result = await supabase.rpc("exec_sql", {"query": org_id_query}).execute()
        org_tables = [r.get("table_name", "") for r in (result.data or [])]
    except Exception:
        org_tables = []
        print("    (Could not query information_schema — check DB permissions)")

    issues = []
    for name in org_tables:
        if name not in rls_enabled:
            issues.append(name)
            known = " [KNOWN GAP]" if name in KNOWN_GAPS else ""
            print(f"    ❌ {name}{known}")

    if not issues:
        print("    ✅ All org_id tables have RLS enabled!")

    # 3. Summary
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    total = len(rls_enabled) + len(rls_disabled)
    print(f"    Total tables: {total}")
    print(f"    RLS enabled:  {len(rls_enabled)}")
    print(f"    RLS disabled: {len(rls_disabled)}")
    print(f"    Org_id without RLS: {len(issues)}")
    print(f"    Known gaps: {', '.join(KNOWN_GAPS)}")

    if issues:
        print(f"\n  ⚠️  ACTION NEEDED: {len(issues)} table(s) need RLS policies")
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(audit_rls())
    sys.exit(exit_code)
