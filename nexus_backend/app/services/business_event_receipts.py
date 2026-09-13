"""Durable at-most-once admission for legacy non-transactional business handlers.

An interrupted handler is ambiguous: it must be reconciled, never blindly retried.
This is a consumer receipt, not a replacement for a transactional producer outbox.
"""

from typing import Any

GUARDED_HANDLERS = frozenset(
    {
        "calculate_deal_bonus",
        "auto_create_contract_from_deal",
        "auto_create_invoice_from_contract",
        "update_sales_metrics_on_payment",
    }
)


async def dispatch_business_event(handler: Any, event: Any) -> None:
    if (
        handler.__module__ != "app.services.event_bus"
        or handler.__name__ not in GUARDED_HANDLERS
    ):
        await handler(event)
        return

    from app.core.database import supabase

    org_id = event.tenant_id()
    actor_id = event.user_id or event.payload.get("user_id")
    if not supabase or not org_id or not actor_id:
        raise ValueError("Business event requires a tenant, actor and durable database")
    if event.user_id and event.payload.get("user_id") not in (None, event.user_id):
        raise ValueError("Business event actor mismatch")
    actor = await (
        supabase.table("users")
        .select("id,status")
        .eq("id", actor_id)
        .eq("organization_id", org_id)
        .maybe_single()
        .execute()
    )
    if not actor.data or actor.data.get("status") in {
        "inactive",
        "disabled",
        "deleted",
        "suspended",
    }:
        raise PermissionError("Business event actor no longer has access")

    event.organization_id = org_id
    event.payload = {**event.payload, "org_id": org_id, "user_id": actor_id}
    params = {
        "p_organization_id": org_id,
        "p_event_id": event.id,
        "p_handler": handler.__name__,
        "p_actor_id": actor_id,
        "p_payload": event.to_dict(),
    }
    result = await supabase.rpc("claim_business_event_receipt", params).execute()
    receipt = result.data or {}
    if not receipt.get("claimed"):
        return
    # All legacy handlers now receive the canonical identity, including old payload readers.
    try:
        await handler(event)
    except Exception:
        await (
            supabase.table("business_event_receipts")
            .update({"status": "needs_attention"})
            .eq("organization_id", org_id)
            .eq("event_id", event.id)
            .eq("handler", handler.__name__)
            .eq("status", "processing")
            .execute()
        )
        raise
    await (
        supabase.table("business_event_receipts")
        .update({"status": "completed"})
        .eq("organization_id", org_id)
        .eq("event_id", event.id)
        .eq("handler", handler.__name__)
        .eq("status", "processing")
        .execute()
    )
