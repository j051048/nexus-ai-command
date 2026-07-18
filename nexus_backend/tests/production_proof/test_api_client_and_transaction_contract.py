from __future__ import annotations

from pathlib import Path

from app.core.transaction_contracts import TRANSACTION_CONTRACTS, ReplayStrategy

ROOT = Path(__file__).resolve().parents[3]


def test_frontend_api_clients_have_single_default_transport():
    """Frontend API calls must use one single default transport.

    ``httpClient`` owns auth, tenant, CSRF, idempotency and error handling.
    ``aiClient`` may wrap that transport for AI ergonomics, but it must not
    create another axios instance with divergent defaults.
    """
    http_client = ROOT / "src" / "lib" / "httpClient.ts"
    assert http_client.exists()
    content = http_client.read_text(encoding="utf-8", errors="replace")
    assert "axios.create" in content or "fetch(" in content

    ai_client = ROOT / "src" / "api" / "aiClient.ts"
    assert ai_client.exists()
    ai_content = ai_client.read_text(encoding="utf-8", errors="replace")
    assert (
        "httpClient" in ai_content
    ), "aiClient must delegate to httpClient instead of creating a second transport"
    assert "httpClient.request" in ai_content
    assert "axios.create" not in ai_content


def test_complex_business_operations_have_transaction_rpc_contract():
    assert len(TRANSACTION_CONTRACTS) >= 3
    assert {contract.domain for contract in TRANSACTION_CONTRACTS} >= {
        "admin_trust",
        "operations",
    }
    for contract in TRANSACTION_CONTRACTS:
        migration = ROOT / contract.migration
        caller = ROOT / contract.caller
        assert migration.exists(), contract.code
        assert caller.exists(), contract.code
        sql = migration.read_text(encoding="utf-8", errors="replace")
        source = caller.read_text(encoding="utf-8", errors="replace")
        assert f"FUNCTION public.{contract.rpc_name}" in sql
        assert contract.security_mode in sql
        if contract.replay_strategy == ReplayStrategy.IDEMPOTENCY_KEY:
            assert contract.idempotency_parameter in sql
            assert contract.idempotency_parameter in source


def test_transaction_and_domain_governance_are_executable_ci_gates():
    transaction_gate = (ROOT / "scripts" / "check_transaction_contracts.py").read_text(
        encoding="utf-8", errors="replace"
    )
    domain_gate = (ROOT / "scripts" / "check_domain_registry.py").read_text(
        encoding="utf-8", errors="replace"
    )
    workflow = (ROOT / ".github" / "workflows" / "test-full.yml").read_text(
        encoding="utf-8", errors="replace"
    )

    assert "TRANSACTION_CONTRACTS_OK" in transaction_gate
    assert "DOMAIN_REGISTRY_OK" in domain_gate
    assert "python scripts/check_transaction_contracts.py" in workflow
    assert "python scripts/check_domain_registry.py" in workflow


def test_mini_supabase_client_has_org_scope_and_rpc_injection():
    content = (ROOT / "nexus_backend" / "app" / "core" / "database.py").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "OrgFilteredClient" in content
    assert '"organization_id"' in content
    assert '"p_org_id"' in content
