import base64
import time

import pytest

from app.core.model_pricing import estimate_cost, resolve_model_price
from app.core.tool_rbac import check_tool_access
from app.services.enterprise_sso_service import EnterpriseSSOError, EnterpriseSSOService


def test_model_pricing_exact_before_prefix():
    assert resolve_model_price("gpt-4o") == (2.50, 10.00)
    assert resolve_model_price("gpt-4o-2024-08-06") == (2.50, 10.00)
    assert estimate_cost(1_000_000, 1_000_000, "unknown-model") == 20.0


def test_tool_rbac_blocks_unsafe_all_tool_for_non_privileged_role():
    allowed, reason = check_tool_access(
        tool_name="delete_customer",
        user_role="employee",
        tool_required_role="all",
    )
    assert not allowed
    assert "delete_customer" in reason


def test_tool_rbac_allows_safe_read_all_tool_for_non_privileged_role():
    allowed, reason = check_tool_access(
        tool_name="list_customers",
        user_role="employee",
        tool_required_role="all",
    )
    assert allowed
    assert reason == ""


@pytest.mark.parametrize(
    ("tool_name", "user_role", "required_role", "expected"),
    [
        ("create_customer", "viewer", "all", False),
        ("approve_payment", "employee", "finance", False),
        ("create_invoice", "finance", "finance", True),
        ("change_salary", "manager", "all", False),
        ("delete_customer", "admin", "admin", True),
    ],
)
def test_tool_rbac_core_permission_matrix(tool_name, user_role, required_role, expected):
    allowed, reason = check_tool_access(
        tool_name=tool_name,
        user_role=user_role,
        tool_required_role=required_role,
    )
    assert allowed is expected
    if not expected:
        assert reason


def test_enterprise_sso_state_rejects_tamper():
    service = EnterpriseSSOService(state_secret="secret")
    state = service.sign_state({"org_id": "org-1", "provider_code": "okta"})
    payload = service.verify_state(state)
    assert payload["org_id"] == "org-1"

    raw, sig = state.split(".", 1)
    with pytest.raises(EnterpriseSSOError):
        service.verify_state(f"{raw}.{sig[:-2]}xx")


def test_enterprise_sso_state_rejects_expired(monkeypatch):
    service = EnterpriseSSOService(state_secret="secret")
    service.state_ttl_seconds = 1
    monkeypatch.setattr(time, "time", lambda: 1000)
    state = service.sign_state({"org_id": "org-1", "provider_code": "okta"})
    monkeypatch.setattr(time, "time", lambda: 1005)
    with pytest.raises(EnterpriseSSOError):
        service.verify_state(state)


def test_saml_unsigned_rejected_by_default(monkeypatch):
    monkeypatch.delenv("SSO_ALLOW_UNSIGNED_SAML", raising=False)
    saml = """
    <samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
      <saml:Assertion>
        <saml:Subject><saml:NameID>user@example.com</saml:NameID></saml:Subject>
      </saml:Assertion>
    </samlp:Response>
    """.encode()
    with pytest.raises(EnterpriseSSOError):
        EnterpriseSSOService(state_secret="secret").parse_saml_response(
            base64.b64encode(saml).decode()
        )
