"""Governance operations for the platform super-admin console."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.services.event_bus import Event, EventType, event_bus

logger = logging.getLogger(__name__)

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "platform_owner": {"*"},
    "billing_operator": {
        "view_platform",
        "manage_memberships",
        "manage_quotas",
        "manage_commercial",
    },
    "support_operator": {"view_platform", "manage_quotas", "manage_organizations"},
    "security_auditor": {"view_platform", "view_audit"},
    "finance_reviewer": {
        "view_platform",
        "manage_memberships",
        "manage_commercial",
    },
}

VALID_PLANS = {"free", "starter", "professional", "enterprise"}
VALID_PAYMENT_STATUSES = {
    "pending",
    "partial",
    "paid",
    "overdue",
    "waived",
    "refunded",
}
VALID_INVOICE_STATUSES = {"none", "requested", "issued", "cancelled"}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


class SuperAdminGovernanceService:
    def _client(self):
        from app.core.database import supabase

        if not supabase:
            raise RuntimeError("Database service is unavailable")
        return supabase

    async def get_admin_context(self, user_id: str) -> dict[str, Any]:
        client = self._client()
        result = (
            await client.table("platform_admin_assignments")
            .select("user_id, admin_role, permissions, active")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        assignment = (result.data or [None])[0]
        if not assignment:
            role = "platform_owner"
            permissions = {"*"}
        else:
            role = assignment["admin_role"]
            permissions = set(ROLE_PERMISSIONS.get(role, set()))
            permissions.update(assignment.get("permissions") or [])
            if not assignment.get("active", True):
                permissions = set()
        return {
            "user_id": user_id,
            "admin_role": role,
            "permissions": sorted(permissions),
            "active": bool(permissions),
        }

    async def assert_permission(self, user_id: str, permission: str) -> None:
        context = await self.get_admin_context(user_id)
        permissions = set(context["permissions"])
        if "*" not in permissions and permission not in permissions:
            raise PermissionError(f"Missing platform permission: {permission}")

    async def list_admin_assignments(self) -> list[dict[str, Any]]:
        client = self._client()
        result = (
            await client.table("platform_admin_assignments")
            .select("*")
            .order("created_at", desc=False)
            .execute()
        )
        assignments = result.data or []
        user_ids = [item["user_id"] for item in assignments]
        user_map: dict[str, dict[str, Any]] = {}
        if user_ids:
            users = (
                await client.table("users")
                .select("id, full_name, email, status")
                .in_("id", user_ids)
                .execute()
            )
            user_map = {str(item["id"]): item for item in (users.data or [])}
        return [
            {**item, "user": user_map.get(str(item["user_id"]))} for item in assignments
        ]

    async def set_admin_assignment(
        self,
        user_id: str,
        admin_role: str,
        permissions: list[str],
        active: bool,
        actor_user_id: str,
    ) -> dict[str, Any]:
        if admin_role not in ROLE_PERMISSIONS:
            raise ValueError("Invalid platform admin role")
        if user_id == actor_user_id and (admin_role != "platform_owner" or not active):
            raise ValueError("Platform owners cannot remove their own owner access")

        client = self._client()
        now = datetime.now(UTC).isoformat()
        payload = {
            "user_id": user_id,
            "admin_role": admin_role,
            "permissions": sorted(set(permissions)),
            "active": active,
            "created_by": actor_user_id,
            "updated_at": now,
        }
        result = (
            await client.table("platform_admin_assignments").upsert(payload).execute()
        )
        await self._audit(
            client,
            "admin_set_platform_role",
            actor_user_id,
            "platform",
            {"target_user_id": user_id, **payload},
        )
        return (result.data or [payload])[0]

    async def list_access_changes(
        self, org_id: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        client = self._client()
        query = client.table("subscription_access_versions").select("*")
        if org_id:
            query = query.eq("org_id", org_id)
        if status:
            query = query.eq("change_status", status)
        result = await query.order("created_at", desc=True).limit(limit).execute()
        return result.data or []

    async def schedule_access_change(
        self,
        org_id: str,
        plan: str,
        expires_at: str | None,
        effective_at: str | None,
        reason: str,
        admin_user_id: str,
        commercial_record_id: str | None = None,
    ) -> dict[str, Any]:
        if plan not in VALID_PLANS:
            raise ValueError("Invalid plan")
        if len(reason.strip()) < 2:
            raise ValueError("A reason is required")
        expiry = _parse_datetime(expires_at)
        effective = _parse_datetime(effective_at) or datetime.now(UTC)
        now = datetime.now(UTC)
        if expiry and expiry <= effective:
            raise ValueError("Expiry must be later than the effective time")

        client = self._client()
        change_id = str(uuid.uuid4())
        next_snapshot = {
            "plan": plan,
            "status": "active" if plan != "free" else "inactive",
            "current_period_end": expiry.isoformat() if expiry else None,
            "access_source": "admin_override",
        }
        payload = {
            "id": change_id,
            "org_id": org_id,
            "commercial_record_id": commercial_record_id,
            "change_kind": "scheduled" if effective > now else "direct",
            "change_status": "scheduled",
            "next_snapshot": next_snapshot,
            "reason": reason,
            "effective_at": effective.isoformat(),
            "created_by": admin_user_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        result = (
            await client.table("subscription_access_versions").insert(payload).execute()
        )
        if not result.data:
            raise RuntimeError("Failed to create access change")

        if effective <= now:
            applied = await client.rpc(
                "apply_subscription_access_change",
                {"p_change_id": change_id, "p_applied_by": admin_user_id},
            ).execute()
            await self._after_entitlement_change(
                org_id, "applied", change_id, admin_user_id
            )
            return self._rpc_dict(applied.data)

        await self._publish_event(
            Event(
                type=EventType.SUBSCRIPTION_ACCESS_SCHEDULED.value,
                payload={
                    "org_id": org_id,
                    "change_id": change_id,
                    "effective_at": effective.isoformat(),
                },
                user_id=admin_user_id,
            )
        )
        await self._audit(
            client,
            "admin_schedule_subscription_access",
            admin_user_id,
            org_id,
            {
                "change_id": change_id,
                "effective_at": effective.isoformat(),
                "reason": reason,
            },
        )
        return result.data[0]

    async def cancel_access_change(
        self, change_id: str, reason: str, admin_user_id: str
    ) -> dict[str, Any]:
        if len(reason.strip()) < 2:
            raise ValueError("A cancellation reason is required")
        client = self._client()
        result = (
            await client.table("subscription_access_versions")
            .update(
                {
                    "change_status": "cancelled",
                    "reason": reason,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", change_id)
            .eq("change_status", "scheduled")
            .execute()
        )
        if not result.data:
            raise ValueError("Scheduled access change not found")
        item = result.data[0]
        await self._audit(
            client,
            "admin_cancel_subscription_change",
            admin_user_id,
            str(item["org_id"]),
            {"change_id": change_id, "reason": reason},
        )
        return item

    async def rollback_access_change(
        self, change_id: str, reason: str, admin_user_id: str
    ) -> dict[str, Any]:
        client = self._client()
        result = await client.rpc(
            "rollback_subscription_access_change",
            {
                "p_change_id": change_id,
                "p_admin_user_id": admin_user_id,
                "p_reason": reason,
            },
        ).execute()
        payload = self._rpc_dict(result.data)
        org_id = str(payload["org_id"])
        await self._after_entitlement_change(
            org_id, "rolled_back", change_id, admin_user_id
        )
        await self._audit(
            client,
            "admin_rollback_subscription_access",
            admin_user_id,
            org_id,
            {"change_id": change_id, "reason": reason},
        )
        return payload

    async def list_commercial_records(
        self, org_id: str | None = None, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        client = self._client()
        query = client.table("subscription_commercial_records").select("*")
        if org_id:
            query = query.eq("org_id", org_id)
        if status:
            query = query.eq("payment_status", status)
        result = await query.order("created_at", desc=True).limit(limit).execute()
        return result.data or []

    async def upsert_commercial_record(
        self, payload: dict[str, Any], admin_user_id: str
    ) -> dict[str, Any]:
        if payload.get("payment_status", "pending") not in VALID_PAYMENT_STATUSES:
            raise ValueError("Invalid payment status")
        if payload.get("invoice_status", "none") not in VALID_INVOICE_STATUSES:
            raise ValueError("Invalid invoice status")
        if not payload.get("org_id") or not payload.get("order_number"):
            raise ValueError("Organization and order number are required")

        client = self._client()
        now = datetime.now(UTC).isoformat()
        record = {
            **payload,
            "id": payload.get("id") or str(uuid.uuid4()),
            "created_by": payload.get("created_by") or admin_user_id,
            "updated_at": now,
        }
        result = (
            await client.table("subscription_commercial_records")
            .upsert(record)
            .execute()
        )
        await self._audit(
            client,
            "admin_upsert_commercial_record",
            admin_user_id,
            str(payload["org_id"]),
            {
                "record_id": record["id"],
                "order_number": record["order_number"],
                "payment_status": record.get("payment_status", "pending"),
            },
        )
        return (result.data or [record])[0]

    async def apply_due_access_changes(self) -> int:
        client = self._client()
        due = (
            await client.table("subscription_access_versions")
            .select("id, org_id")
            .eq("change_status", "scheduled")
            .lte("effective_at", datetime.now(UTC).isoformat())
            .execute()
        )
        result = await client.rpc("apply_due_subscription_access_changes", {}).execute()
        count = int(result.data or 0)
        for item in due.data or []:
            await self._after_entitlement_change(
                str(item["org_id"]), "applied", str(item["id"]), "system"
            )
        return count

    async def _after_entitlement_change(
        self, org_id: str, status: str, change_id: str, user_id: str
    ) -> None:
        from app.services.billing_service import billing_service

        billing_service.invalidate_subscription(org_id)
        await self._publish_event(
            Event(
                type=EventType.SUBSCRIPTION_ACCESS_CHANGED.value,
                payload={
                    "org_id": org_id,
                    "status": status,
                    "change_id": change_id,
                },
                user_id=user_id,
            )
        )

    async def _publish_event(self, event: Event) -> None:
        try:
            await event_bus.publish(event)
        except Exception as exc:
            logger.warning(
                "Failed to publish super-admin event type=%s: %s", event.type, exc
            )

    async def _audit(
        self,
        client,
        action: str,
        user_id: str,
        org_id: str,
        details: dict[str, Any],
    ) -> None:
        await client.table("audit_logs").insert(
            {
                "id": str(uuid.uuid4()),
                "action": action,
                "user_id": user_id,
                "organization_id": org_id,
                "details": details,
                "created_at": datetime.now(UTC).isoformat(),
            }
        ).execute()

    @staticmethod
    def _rpc_dict(data: Any) -> dict[str, Any]:
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict):
            raise RuntimeError("Subscription operation returned no data")
        return data


super_admin_governance_service = SuperAdminGovernanceService()
