"""
Item 27: Safe query helper — replace select("*") with explicit field lists.

Provides field whitelist constants for security-sensitive tables to prevent
accidental exposure of internal columns. For non-sensitive tables, select("*")
is still acceptable but should be gradually migrated.

Usage:
    from app.core.safe_query import USERS_FIELDS, APPROVAL_FIELDS
    result = await db.table("users").select(USERS_FIELDS).eq("id", uid).execute()
"""

# ── Users table: never expose raw password hashes or internal flags ──
USERS_FIELDS = (
    "id, email, full_name, role, organization_id, avatar_url, "
    "phone, position, department, status, created_at, updated_at"
)

USERS_FIELDS_MINIMAL = "id, email, full_name, role, organization_id, avatar_url"

# ── Approval table ──
APPROVAL_FIELDS = (
    "id, tenant_id, type, title, description, amount, currency, "
    "status, priority, submitted_by, submitted_at, approved_by, approved_at, "
    "rejected_by, rejected_at, rejection_reason, current_step, metadata, "
    "created_at, updated_at"
)

# ── Sales leads / CRM ──
SALES_LEADS_FIELDS = (
    "id, tenant_id, company_name, contact_name, contact_phone, contact_email, "
    "stage, priority, expected_amount, source, assigned_to, "
    "last_contacted_at, next_follow_up, notes, tags, created_at, updated_at"
)

# ── Contracts ──
CONTRACT_FIELDS = (
    "id, tenant_id, title, contract_number, type, status, "
    "party_a, party_b, amount, currency, start_date, end_date, "
    "signed_at, signed_by, created_at, updated_at"
)

# ── API Keys: NEVER return the raw key ──
API_KEY_FIELDS = (
    "id, tenant_id, name, prefix, permissions, status, "
    "last_used_at, expires_at, created_at"
)

# ── LLM Model Config ──
LLM_MODEL_FIELDS = (
    "id, tenant_id, model_name, provider, display_name, description, "
    "capabilities, status, is_deleted, priority, max_tokens, "
    "temperature, pricing_input, pricing_output, created_at, updated_at"
)

# ── Documents / Knowledge Base ──
DOCUMENT_FIELDS = (
    "id, tenant_id, title, file_name, file_type, file_size, "
    "status, category, tags, uploaded_by, created_at, updated_at"
)

# ── Billing / Payments ──
BILLING_FIELDS = (
    "id, tenant_id, plan_id, plan_name, status, "
    "current_period_start, current_period_end, "
    "stripe_subscription_id, created_at, updated_at"
)


def fields_for_table(table_name: str) -> str:
    """Return the recommended field list for a table, or '*' if not mapped."""
    _TABLE_MAP = {
        "users": USERS_FIELDS,
        "approval_requests": APPROVAL_FIELDS,
        "sales_leads": SALES_LEADS_FIELDS,
        "contracts": CONTRACT_FIELDS,
        "api_keys": API_KEY_FIELDS,
        "llm_model_config": LLM_MODEL_FIELDS,
        "documents": DOCUMENT_FIELDS,
    }
    return _TABLE_MAP.get(table_name, "*")
