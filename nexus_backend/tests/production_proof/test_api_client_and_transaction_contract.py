from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_frontend_api_clients_have_single_default_transport():
    http_client = ROOT / "src" / "lib" / "httpClient.ts"
    assert http_client.exists()
    content = http_client.read_text(encoding="utf-8", errors="replace")
    assert "axios.create" in content or "fetch(" in content

    ai_client = ROOT / "src" / "api" / "aiClient.ts"
    assert ai_client.exists()
    ai_content = ai_client.read_text(encoding="utf-8", errors="replace")
    assert "httpClient" in ai_content, "aiClient must delegate to httpClient instead of creating a second transport"
    assert "httpClient.request" in ai_content


def test_complex_business_operations_have_transaction_rpc_contract():
    migration_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (ROOT / "supabase" / "migrations").glob("*.sql")
    )
    assert "SECURITY DEFINER" in migration_text
    assert "approval" in migration_text.lower()


def test_mini_supabase_client_has_org_scope_and_rpc_injection():
    content = (ROOT / "nexus_backend" / "app" / "core" / "database.py").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "OrgFilteredClient" in content
    assert '"organization_id"' in content
    assert '"p_org_id"' in content
