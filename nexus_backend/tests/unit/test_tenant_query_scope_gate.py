"""Contract tests for the unscoped service-role table access gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_tenant_query_scope import (
    BASELINE_PATH,
    GLOBAL_TABLES,
    analyze_source,
    scan,
)


UNSCOPED_SOURCE = """
async def handler(db, customer_id):
    return (
        db.table("crm_customers")
        .select("*")
        .eq("id", customer_id)
        .execute()
    )
"""

SCOPED_SOURCE = """
async def handler(db, org_id):
    return (
        db.table("crm_customers")
        .select("*")
        .eq("organization_id", org_id)
        .execute()
    )
"""

REPO_SCOPED_SOURCE = """
async def handler(org_id):
    return (
        supabase.get_org_filtered_client(org_id)
        .table("crm_customers")
        .select("*")
        .execute()
    )
"""


def test_detects_unscoped_table_access():
    count, samples = analyze_source(UNSCOPED_SOURCE)
    assert count == 1
    assert samples and "crm_customers" in samples[0]


def test_accepts_explicit_organization_filter():
    count, _ = analyze_source(SCOPED_SOURCE)
    assert count == 0


def test_accepts_org_filtered_client():
    count, _ = analyze_source(REPO_SCOPED_SOURCE)
    assert count == 0


def test_skips_platform_level_tables():
    source = """
async def handler(db):
    return db.table("organizations").select("*").execute()
"""
    assert "organizations" in GLOBAL_TABLES
    count, _ = analyze_source(source)
    assert count == 0


def test_baseline_is_committed_and_covers_current_tree():
    assert BASELINE_PATH.exists(), "tenant query scope baseline must be committed"
    baseline = json.loads(Path(BASELINE_PATH).read_text(encoding="utf-8"))
    current = scan()
    allowed = baseline["files"]

    assert set(current) <= set(allowed), "new files with unscoped access must be fixed, not baselined"
    for name, value in current.items():
        assert value <= allowed[name], f"{name} exceeded its unscoped-access baseline"
