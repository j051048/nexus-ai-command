"""Read metadata only; generate the frontend table contract reproducibly offline."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "docs/handbook/generated/database-schema.json"
OUTPUT = ROOT / "src/integrations/supabase/database-tables.ts"
TABLES = """users organizations sales_targets projects sales_leads ai_settings
sales_metrics departments notifications document_embeddings oa_tasks finance_invoices
approval_requests documents chat_messages project_timeline
oa_leave_requests oa_meeting_bookings hr_attendance hr_salary_records
hr_performance_reviews hr_job_positions hr_candidates finance_budgets contracts
audit_logs dashboard_configs qa_pairs contract_events customers badges assets
certificates user_scheduled_tasks""".split()


def refresh(env_file: str) -> dict:
    import httpx
    from dotenv import dotenv_values

    env = dotenv_values(env_file)
    url = (env.get("SUPABASE_URL") or "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_KEY") or env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url.startswith("https://") or not key:
        raise ValueError("HTTPS Supabase URL and service credential are required")
    with httpx.Client(
        timeout=20, headers={"apikey": key, "Authorization": f"Bearer {key}"}
    ) as client:
        response = client.get(
            f"{url}/rest/v1/", headers={"Accept": "application/openapi+json"}
        )
        response.raise_for_status()
        definitions = response.json()["definitions"]
        missing = set(TABLES) - definitions.keys()
        if missing:
            raise ValueError(f"Missing tables: {sorted(missing)}")
    return {
        "tables": {table: definitions[table] for table in TABLES},
    }


def ts_type(prop: dict) -> str:
    if "enum" in prop:
        return " | ".join(
            json.dumps(value, ensure_ascii=True) for value in prop["enum"]
        )
    if prop.get("format") in ("json", "jsonb"):
        return "Json"
    kind = prop.get("type")
    if kind in ("integer", "number"):
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "string":
        return "string"
    if kind == "array":
        return f"Array<{ts_type(prop['items'])}>"
    if kind == "object":
        return "Json"
    raise ValueError(f"Unsupported column type: {prop}")


def render(snapshot: dict) -> str:
    lines = [
        "// Generated from read-only database metadata. Do not edit by hand.",
        "// Run: python scripts/generate_supabase_contract.py",
        "import type { Json } from './types';",
        "",
        "// Column contract only: OpenAPI does not expose FK constraint names.",
        "// Relation joins must use separately verified contracts or backend APIs.",
        "type Table<Row, Required extends keyof Row> = {",
        "  Row: Row;",
        "  Insert: Pick<Row, Required> & Partial<Row>;",
        "  Update: Partial<Row>;",
        "  Relationships: [];",
        "};",
        "",
        "export type DatabaseTables = {",
    ]
    for table, definition in snapshot["tables"].items():
        required = set(definition.get("required", []))
        insert_required = []
        lines.append(f"  {table}: Table<{{")
        for name, prop in definition["properties"].items():
            value = ts_type(prop)
            if name not in required:
                value += " | null"
            elif "default" not in prop and not prop.get("readOnly"):
                insert_required.append(json.dumps(name))
            lines.append(f"    {name}: {value};")
        lines.append("  }, " + (" | ".join(insert_required) or "never") + ">;")
    lines += ["};", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="Read metadata from configured server"
    )
    parser.add_argument("--env", default="nexus_backend/.env")
    parser.add_argument(
        "--check", action="store_true", help="Offline deterministic contract check"
    )
    args = parser.parse_args()
    if args.refresh and args.check:
        parser.error("--check is offline; do not combine it with --refresh")
    snapshot = (
        refresh(args.env)
        if args.refresh
        else json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    )
    output = render(snapshot)
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != output:
            print("DATABASE_CONTRACT_STALE")
            return 1
        print("DATABASE_CONTRACT_OK")
        return 0
    if args.refresh:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(
            json.dumps(snapshot, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
        )
    OUTPUT.write_text(output, encoding="utf-8")
    print(
        f'Generated contract for {len(snapshot["tables"])} tables; no database writes performed'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
