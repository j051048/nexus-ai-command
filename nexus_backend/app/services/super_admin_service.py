"""Platform super-admin service.

This service intentionally uses the global Supabase service client because the
platform console needs cross-tenant visibility. Keep all callers protected by a
strict `super_admin` dependency and write audit logs for every mutating action.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.event_bus import Event, EventType, event_bus

logger = logging.getLogger(__name__)

VALID_PLANS = {"free", "starter", "professional", "enterprise"}
VALID_TRIAL_ACTIONS = {"start", "extend"}
VALID_ACCESS_DECISIONS = {"approved", "rejected"}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def _access_state(subscription: dict[str, Any] | None) -> str:
    if not subscription:
        return "unconfigured"
    expires_at = _parse_datetime(subscription.get("current_period_end"))
    if expires_at and expires_at <= datetime.now(UTC):
        return "expired"
    if subscription.get("status") in {"past_due", "suspended", "cancelled"}:
        return str(subscription.get("status"))
    if subscription.get("plan") == "free":
        return "free"
    return "active"


class SuperAdminService:
    """Cross-tenant management for the platform operator console."""

    def _get_global_client(self):
        from app.core.database import supabase

        if not supabase:
            raise RuntimeError("Database service is unavailable")
        return supabase

    async def list_organizations(
        self,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        client = self._get_global_client()
        offset = (page - 1) * limit

        query = client.table("organizations").select(
            "id, name, slug, created_at, status, plan, subscription_status"
        )
        count_query = client.table("organizations").select("id", count="exact")

        if search:
            query = query.ilike("name", f"%{search}%")
            count_query = count_query.ilike("name", f"%{search}%")
        if status:
            query = query.eq("status", status)
            count_query = count_query.eq("status", status)

        result = (
            await query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        count_result = await count_query.execute()
        total = count_result.count
        if total is None:
            total = len(count_result.data or [])

        organizations = result.data or []
        org_ids = [str(org["id"]) for org in organizations if org.get("id")]
        subscription_map: dict[str, dict[str, Any]] = {}
        if org_ids:
            subscriptions = (
                await client.table("subscriptions")
                .select(
                    "org_id, plan, status, current_period_end, access_source, approved_at"
                )
                .in_("org_id", org_ids)
                .execute()
            )
            subscription_map = {
                str(item["org_id"]): item for item in (subscriptions.data or [])
            }

        enriched = []
        for org in organizations:
            subscription = subscription_map.get(str(org.get("id")))
            enriched.append(
                {
                    **org,
                    "subscription": subscription,
                    "access_state": _access_state(subscription),
                }
            )

        return {
            "organizations": enriched,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0,
        }

    async def get_organization_detail(self, org_id: str) -> dict[str, Any]:
        client = self._get_global_client()

        org_result = (
            await client.table("organizations")
            .select("*")
            .eq("id", org_id)
            .maybe_single()
            .execute()
        )
        if not org_result.data:
            return {}

        org_data = org_result.data
        users_result = (
            await client.table("users")
            .select("id", count="exact")
            .eq("organization_id", org_id)
            .execute()
        )
        user_count = users_result.count
        if user_count is None:
            user_count = len(users_result.data or [])

        thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).date().isoformat()
        usage_result = (
            await client.table("user_token_usage")
            .select("request_count")
            .eq("org_id", org_id)
            .gte("date", thirty_days_ago)
            .execute()
        )
        ai_calls_30d = sum(
            row.get("request_count", 0) for row in (usage_result.data or [])
        )

        subscription = await self._maybe_first(
            client.table("subscriptions").select("*").eq("org_id", org_id).limit(1)
        )
        quotas = await self._maybe_first(
            client.table("tenant_quotas").select("*").eq("org_id", org_id).limit(1)
        )

        return {
            **org_data,
            "user_count": user_count,
            "ai_calls_30d": ai_calls_30d,
            "subscription": subscription,
            "quotas": quotas,
        }

    async def suspend_organization(
        self, org_id: str, reason: str, admin_user_id: str | None = None
    ) -> bool:
        client = self._get_global_client()
        result = (
            await client.table("organizations")
            .update(
                {
                    "status": "suspended",
                    "suspended_reason": reason,
                    "suspended_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", org_id)
            .execute()
        )
        if result.data:
            if admin_user_id:
                await self._write_audit_log(
                    client,
                    "admin_suspend_organization",
                    admin_user_id,
                    org_id,
                    {"reason": reason},
                )
            logger.info("Super admin suspended organization %s", org_id)
            return True
        return False

    async def unsuspend_organization(
        self, org_id: str, admin_user_id: str | None = None
    ) -> bool:
        client = self._get_global_client()
        result = (
            await client.table("organizations")
            .update(
                {
                    "status": "active",
                    "suspended_reason": None,
                    "suspended_at": None,
                }
            )
            .eq("id", org_id)
            .execute()
        )
        if result.data:
            if admin_user_id:
                await self._write_audit_log(
                    client,
                    "admin_unsuspend_organization",
                    admin_user_id,
                    org_id,
                    {},
                )
            logger.info("Super admin restored organization %s", org_id)
            return True
        return False

    async def get_platform_stats(self) -> dict[str, Any]:
        client = self._get_global_client()

        org_result = (
            await client.table("organizations")
            .select("id, status", count="exact")
            .execute()
        )
        user_result = (
            await client.table("users")
            .select("id, last_active_at", count="exact")
            .execute()
        )

        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        usage_result = (
            await client.table("user_token_usage")
            .select("request_count")
            .gte("date", thirty_days_ago.date().isoformat())
            .execute()
        )
        subscription_result = (
            await client.table("subscriptions")
            .select("org_id, plan, status, current_period_end")
            .execute()
        )
        pending_access_result = (
            await client.table("subscription_access_requests")
            .select("id", count="exact")
            .eq("status", "pending")
            .execute()
        )

        users = user_result.data or []
        monthly_active_users = 0
        for user in users:
            last_active = user.get("last_active_at")
            if not last_active:
                continue
            try:
                active_at = datetime.fromisoformat(
                    str(last_active).replace("Z", "+00:00")
                )
                if active_at >= thirty_days_ago:
                    monthly_active_users += 1
            except ValueError:
                continue

        orgs = org_result.data or []
        subscriptions = subscription_result.data or []
        return {
            "total_organizations": (
                org_result.count if org_result.count is not None else len(orgs)
            ),
            "active_organizations": sum(
                1 for org in orgs if org.get("status") == "active"
            ),
            "total_users": (
                user_result.count if user_result.count is not None else len(users)
            ),
            "monthly_active_users": monthly_active_users,
            "total_ai_calls_30d": sum(
                row.get("request_count", 0) for row in (usage_result.data or [])
            ),
            "paid_organizations": sum(
                1
                for subscription in subscriptions
                if _access_state(subscription) == "active"
            ),
            "pending_access_requests": (
                pending_access_result.count
                if pending_access_result.count is not None
                else len(pending_access_result.data or [])
            ),
            "updated_at": datetime.now(UTC).isoformat(),
        }

    async def get_system_health(self) -> dict[str, Any]:
        client = self._get_global_client()
        services: dict[str, dict[str, str]] = {}

        try:
            await client.table("organizations").select("id").limit(1).execute()
            services["database"] = {"status": "healthy", "provider": "supabase"}
        except Exception as exc:
            services["database"] = {"status": "unhealthy", "error": str(exc)}

        try:
            from app.services.cache_service import cache_service

            await cache_service.get("super_admin_health_probe")
            services["cache"] = {"status": "healthy", "provider": "redis"}
        except Exception as exc:
            services["cache"] = {"status": "degraded", "error": str(exc)}

        try:
            from app.core.config import settings

            services["ai"] = {
                "status": (
                    "healthy"
                    if getattr(settings, "OPENAI_API_KEY", None)
                    else "unconfigured"
                ),
                "provider": getattr(settings, "AI_PROVIDER", "openai"),
            }
        except Exception as exc:
            services["ai"] = {"status": "degraded", "error": str(exc)}

        overall = "healthy"
        if any(service["status"] == "unhealthy" for service in services.values()):
            overall = "unhealthy"
        elif any(
            service["status"] in {"degraded", "unconfigured"}
            for service in services.values()
        ):
            overall = "degraded"

        return {
            "overall": overall,
            "services": services,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    async def list_audit_logs_global(
        self,
        filters: dict | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        client = self._get_global_client()
        filters = filters or {}
        query = client.table("audit_logs").select("*")

        if filters.get("action"):
            query = query.eq("action", filters["action"])
        if filters.get("user_id"):
            query = query.eq("user_id", filters["user_id"])
        if filters.get("org_id"):
            query = query.eq("organization_id", filters["org_id"])
        if filters.get("date_from"):
            query = query.gte("created_at", filters["date_from"])
        if filters.get("date_to"):
            query = query.lte("created_at", filters["date_to"])

        result = (
            await query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data or []

    async def admin_change_plan(
        self, org_id: str, plan: str, reason: str, admin_user_id: str
    ) -> dict[str, Any]:
        if plan not in VALID_PLANS:
            raise ValueError(f"Invalid plan: {plan}")
        if not reason.strip():
            raise ValueError("A reason is required for plan changes")

        client = self._get_global_client()
        await client.table("organizations").update({"tier": plan, "plan": plan}).eq(
            "id", org_id
        ).execute()
        await client.table("subscriptions").upsert(
            {
                "org_id": org_id,
                "plan": plan,
                "status": "active",
                "access_source": "admin_override",
                "approved_by": admin_user_id,
                "approved_at": datetime.now(UTC).isoformat(),
                "notes": reason,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).execute()
        self._invalidate_billing_cache(org_id)
        await self._write_audit_log(
            client,
            "admin_change_plan",
            admin_user_id,
            org_id,
            {"new_plan": plan, "reason": reason},
        )
        return {"org_id": org_id, "plan": plan, "status": "active"}

    async def admin_set_access(
        self,
        org_id: str,
        plan: str,
        expires_at: str | None,
        reason: str,
        admin_user_id: str,
        source: str = "admin_override",
    ) -> dict[str, Any]:
        """Grant or update membership access using an exact expiry date."""
        if plan not in VALID_PLANS:
            raise ValueError(f"Invalid plan: {plan}")
        if not reason.strip():
            raise ValueError("A reason is required for access changes")

        parsed_expiry = _parse_datetime(expires_at)
        if expires_at and not parsed_expiry:
            raise ValueError("Invalid expiry date")
        if parsed_expiry and parsed_expiry <= datetime.now(UTC):
            raise ValueError("Expiry date must be in the future")

        client = self._get_global_client()
        now = datetime.now(UTC).isoformat()
        status = "active" if plan != "free" else "inactive"
        previous_snapshot = await self._maybe_first(
            client.table("subscriptions").select("*").eq("org_id", org_id).limit(1)
        )
        payload = {
            "org_id": org_id,
            "plan": plan,
            "status": status,
            "current_period_end": parsed_expiry.isoformat() if parsed_expiry else None,
            "access_source": source,
            "approved_by": admin_user_id,
            "approved_at": now,
            "notes": reason,
            "updated_at": now,
        }
        result = await client.table("subscriptions").upsert(payload).execute()
        if not result.data:
            raise RuntimeError("Failed to update subscription access")

        await client.table("organizations").update(
            {
                "plan": plan,
                "tier": plan,
                "subscription_status": status,
            }
        ).eq("id", org_id).execute()
        change_id = str(uuid.uuid4())
        await client.table("subscription_access_versions").insert(
            {
                "id": change_id,
                "org_id": org_id,
                "change_kind": "direct",
                "change_status": "applied",
                "previous_snapshot": previous_snapshot,
                "next_snapshot": {
                    "plan": plan,
                    "status": status,
                    "current_period_end": payload["current_period_end"],
                    "access_source": source,
                },
                "reason": reason,
                "effective_at": now,
                "applied_at": now,
                "created_by": admin_user_id,
                "applied_by": admin_user_id,
                "created_at": now,
                "updated_at": now,
            }
        ).execute()
        self._invalidate_billing_cache(org_id)
        await self._publish_entitlement_change(
            org_id, change_id, "applied", admin_user_id
        )
        await self._write_audit_log(
            client,
            "admin_set_subscription_access",
            admin_user_id,
            org_id,
            {
                "plan": plan,
                "expires_at": payload["current_period_end"],
                "source": source,
                "reason": reason,
            },
        )
        return {
            "org_id": org_id,
            "plan": plan,
            "status": status,
            "current_period_end": payload["current_period_end"],
            "access_source": source,
            "change_id": change_id,
        }

    async def admin_update_quotas(
        self, org_id: str, quotas: dict, reason: str, admin_user_id: str
    ) -> dict[str, Any]:
        if not quotas:
            raise ValueError("At least one quota value is required")
        if not reason.strip():
            raise ValueError("A reason is required for quota changes")

        client = self._get_global_client()
        payload = {
            **quotas,
            "org_id": org_id,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        await client.table("tenant_quotas").upsert(payload).execute()
        await self._write_audit_log(
            client,
            "admin_update_quotas",
            admin_user_id,
            org_id,
            {"quotas": quotas, "reason": reason},
        )
        return {"org_id": org_id, "quotas": quotas}

    async def admin_manage_trial(
        self,
        org_id: str,
        action: str,
        days: int,
        plan: str,
        reason: str,
        admin_user_id: str,
    ) -> dict[str, Any]:
        if action not in VALID_TRIAL_ACTIONS:
            raise ValueError(f"Invalid trial action: {action}")
        if plan not in VALID_PLANS:
            raise ValueError(f"Invalid plan: {plan}")
        if days < 1 or days > 365:
            raise ValueError("Trial days must be between 1 and 365")
        if not reason.strip():
            raise ValueError("A reason is required for trial changes")

        client = self._get_global_client()
        now = datetime.now(UTC)
        base_date = now
        if action == "extend":
            current = await self._maybe_first(
                client.table("subscriptions")
                .select("current_period_end")
                .eq("org_id", org_id)
                .limit(1)
            )
            current_end = _parse_datetime(
                current.get("current_period_end") if current else None
            )
            if current_end and current_end > now:
                base_date = current_end
        period_end = base_date + timedelta(days=days)
        await client.table("subscriptions").upsert(
            {
                "org_id": org_id,
                "plan": plan,
                "status": "trialing",
                "current_period_end": period_end.isoformat(),
                "access_source": "admin_override",
                "approved_by": admin_user_id,
                "approved_at": now.isoformat(),
                "notes": reason,
                "updated_at": now.isoformat(),
            }
        ).execute()
        await client.table("organizations").update(
            {
                "plan": plan,
                "tier": plan,
                "subscription_status": "trialing",
            }
        ).eq("id", org_id).execute()
        self._invalidate_billing_cache(org_id)
        await self._write_audit_log(
            client,
            "admin_manage_trial",
            admin_user_id,
            org_id,
            {"action": action, "plan": plan, "days": days, "reason": reason},
        )
        return {
            "org_id": org_id,
            "action": action,
            "plan": plan,
            "trial_days": days,
            "trial_end": period_end.isoformat(),
        }

    async def list_subscription_requests(
        self, status: str = "pending", limit: int = 100
    ) -> list[dict[str, Any]]:
        client = self._get_global_client()
        query = client.table("subscription_access_requests").select("*")
        if status != "all":
            query = query.eq("status", status)
        result = await query.order("created_at", desc=True).limit(limit).execute()
        requests = result.data or []
        org_ids = list({str(item["org_id"]) for item in requests if item.get("org_id")})
        organization_map: dict[str, dict[str, Any]] = {}
        if org_ids:
            organizations = (
                await client.table("organizations")
                .select("id, name, slug")
                .in_("id", org_ids)
                .execute()
            )
            organization_map = {
                str(item["id"]): item for item in (organizations.data or [])
            }
        return [
            {
                **item,
                "organization": organization_map.get(str(item.get("org_id"))),
                "waiting_seconds": max(
                    0,
                    int(
                        (
                            datetime.now(UTC)
                            - (
                                _parse_datetime(item.get("created_at"))
                                or datetime.now(UTC)
                            )
                        ).total_seconds()
                    ),
                ),
                "is_overdue": bool(
                    _parse_datetime(item.get("due_at"))
                    and _parse_datetime(item.get("due_at")) <= datetime.now(UTC)
                ),
            }
            for item in requests
        ]

    async def decide_subscription_request(
        self,
        request_id: str,
        decision: str,
        reason: str,
        admin_user_id: str,
        plan: str | None = None,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        if decision not in VALID_ACCESS_DECISIONS:
            raise ValueError(f"Invalid decision: {decision}")
        if not reason.strip():
            raise ValueError("A review reason is required")

        client = self._get_global_client()
        request_record = await self._maybe_first(
            client.table("subscription_access_requests")
            .select("org_id")
            .eq("id", request_id)
            .limit(1)
        )
        previous_snapshot = None
        if request_record:
            previous_snapshot = await self._maybe_first(
                client.table("subscriptions")
                .select("*")
                .eq("org_id", request_record["org_id"])
                .limit(1)
            )
        rpc_result = await client.rpc(
            "resolve_subscription_access_request",
            {
                "p_request_id": request_id,
                "p_decision": decision,
                "p_reviewed_by": admin_user_id,
                "p_reason": reason,
                "p_plan": plan,
                "p_expires_at": expires_at,
            },
        ).execute()
        result_data = rpc_result.data
        if isinstance(result_data, list):
            result_data = result_data[0] if result_data else None
        if not isinstance(result_data, dict):
            raise RuntimeError("Subscription decision transaction returned no data")

        org_id = str(result_data["org_id"])
        if decision == "approved":
            await client.table("organizations").update(
                {
                    "plan": result_data["plan"],
                    "tier": result_data["plan"],
                    "subscription_status": "active",
                }
            ).eq("id", org_id).execute()
            change_id = str(uuid.uuid4())
            now = datetime.now(UTC).isoformat()
            await client.table("subscription_access_versions").insert(
                {
                    "id": change_id,
                    "org_id": org_id,
                    "request_id": request_id,
                    "change_kind": "request",
                    "change_status": "applied",
                    "previous_snapshot": previous_snapshot,
                    "next_snapshot": {
                        "plan": result_data["plan"],
                        "status": "active",
                        "current_period_end": result_data.get("current_period_end"),
                        "access_source": "admin_approved",
                    },
                    "reason": reason,
                    "effective_at": now,
                    "applied_at": now,
                    "created_by": admin_user_id,
                    "applied_by": admin_user_id,
                    "created_at": now,
                    "updated_at": now,
                }
            ).execute()
            result_data["change_id"] = change_id
            self._invalidate_billing_cache(org_id)
            await self._publish_entitlement_change(
                org_id, change_id, "applied", admin_user_id
            )

        await self._write_audit_log(
            client,
            "admin_decide_subscription_request",
            admin_user_id,
            org_id,
            {
                "request_id": request_id,
                "decision": decision,
                "plan": result_data.get("plan"),
                "expires_at": result_data.get("current_period_end"),
                "reason": reason,
            },
        )
        return result_data

    @staticmethod
    def _invalidate_billing_cache(org_id: str) -> None:
        from app.services.billing_service import billing_service

        billing_service.invalidate_subscription(org_id)

    async def _publish_entitlement_change(
        self, org_id: str, change_id: str, status: str, user_id: str
    ) -> None:
        try:
            await event_bus.publish(
                Event(
                    type=EventType.SUBSCRIPTION_ACCESS_CHANGED.value,
                    payload={
                        "org_id": org_id,
                        "change_id": change_id,
                        "status": status,
                    },
                    user_id=user_id,
                )
            )
        except Exception as exc:
            logger.warning("Failed to publish entitlement change: %s", exc)

    async def _maybe_first(self, query) -> dict[str, Any] | None:
        try:
            result = await query.execute()
            return (result.data or [None])[0]
        except Exception:
            return None

    async def _write_audit_log(
        self,
        client,
        action: str,
        admin_user_id: str,
        org_id: str,
        details: dict[str, Any],
    ) -> None:
        try:
            await (
                client.table("audit_logs")
                .insert(
                    {
                        "id": str(uuid.uuid4()),
                        "action": action,
                        "user_id": admin_user_id,
                        "organization_id": org_id,
                        "details": details,
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                )
                .execute()
            )
        except Exception as exc:
            logger.warning("Failed to write super admin audit log: %s", exc)


super_admin_service = SuperAdminService()
