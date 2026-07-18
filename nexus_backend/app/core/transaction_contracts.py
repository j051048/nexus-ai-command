"""Machine-readable contracts for cross-table business transactions.

The catalog is intentionally small: only operations whose partial completion
would corrupt an enterprise workflow belong here. CI verifies each contract
against its migration and application caller.
"""

from dataclasses import dataclass
from enum import StrEnum


class ReplayStrategy(StrEnum):
    IDEMPOTENCY_KEY = "idempotency_key"
    TERMINAL_STATE_GUARD = "terminal_state_guard"


@dataclass(frozen=True)
class TransactionEntrypoint:
    path: str
    required_tokens: tuple[str, ...]


@dataclass(frozen=True)
class TransactionContract:
    code: str
    domain: str
    rpc_name: str
    migration: str
    caller: str
    security_mode: str
    replay_strategy: ReplayStrategy
    idempotency_parameter: str | None
    required_sql_tokens: tuple[str, ...]
    required_caller_tokens: tuple[str, ...]
    entrypoints: tuple[TransactionEntrypoint, ...]


TRANSACTION_CONTRACTS: tuple[TransactionContract, ...] = (
    TransactionContract(
        code="membership.direct-access",
        domain="admin_trust",
        rpc_name="set_subscription_access_atomic",
        migration=(
            "supabase/migrations/" "20260718_membership_atomic_access_hardening.sql"
        ),
        caller="nexus_backend/app/services/super_admin_service.py",
        security_mode="SECURITY DEFINER",
        replay_strategy=ReplayStrategy.IDEMPOTENCY_KEY,
        idempotency_parameter="p_change_id",
        required_sql_tokens=(
            "ON CONFLICT (org_id)",
            "pg_advisory_xact_lock",
            "subscription_access_versions",
            "Idempotency key was reused with a different payload",
        ),
        required_caller_tokens=(
            '"set_subscription_access_atomic"',
            '"p_change_id"',
            'idempotency_scope="change-plan"',
            'idempotency_scope="manage-trial"',
        ),
        entrypoints=(
            TransactionEntrypoint(
                path="nexus_backend/app/routers/super_admin.py",
                required_tokens=(
                    'alias="X-Idempotency-Key"',
                    "idempotency_key=_request_idempotency_key",
                ),
            ),
        ),
    ),
    TransactionContract(
        code="membership.request-decision",
        domain="admin_trust",
        rpc_name="resolve_subscription_access_request",
        migration="supabase/migrations/20260718_subscription_request_atomicity.sql",
        caller="nexus_backend/app/services/super_admin_service.py",
        security_mode="SECURITY DEFINER",
        replay_strategy=ReplayStrategy.TERMINAL_STATE_GUARD,
        idempotency_parameter=None,
        required_sql_tokens=(
            "FOR UPDATE",
            "pg_advisory_xact_lock",
            "request_row.status <> 'pending'",
            "subscription_access_versions",
            "UPDATE public.organizations",
            "'replayed', TRUE",
        ),
        required_caller_tokens=(
            '"resolve_subscription_access_request"',
            'result_data.get("replayed")',
        ),
        entrypoints=(
            TransactionEntrypoint(
                path="nexus_backend/app/routers/super_admin.py",
                required_tokens=("/subscription-requests/{request_id}/decision",),
            ),
        ),
    ),
    TransactionContract(
        code="operations.inventory-adjustment",
        domain="operations",
        rpc_name="adjust_inventory_atomic",
        migration="supabase/migrations/20260718_inventory_adjustment_idempotency.sql",
        caller="nexus_backend/app/services/inventory_service.py",
        security_mode="SECURITY INVOKER",
        replay_strategy=ReplayStrategy.IDEMPOTENCY_KEY,
        idempotency_parameter="p_idempotency_key",
        required_sql_tokens=(
            "FOR UPDATE",
            "pg_advisory_xact_lock",
            "uq_inventory_transactions_org_idempotency",
            "v_transaction.metadata",
            "inventory idempotency key reused with different payload",
            "'replayed', TRUE",
        ),
        required_caller_tokens=(
            '"adjust_inventory_atomic"',
            '"p_idempotency_key"',
        ),
        entrypoints=(
            TransactionEntrypoint(
                path="nexus_backend/app/routers/inventory.py",
                required_tokens=(
                    'req.headers.get("X-Idempotency-Key")',
                    "idempotency_key=",
                ),
            ),
            TransactionEntrypoint(
                path="nexus_backend/app/agent/node_execute.py",
                required_tokens=('"idempotency_key":',),
            ),
        ),
    ),
)
