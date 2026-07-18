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

from postgrest.exceptions import APIError

from app.domains.admin_trust.membership import (
    VALID_PLANS,
)
from app.domains.admin_trust.membership import (
    access_state as _access_state,
)
from app.domains.admin_trust.membership import (
    parse_datetime as _parse_datetime,
)
from app.services.event_bus import Event, EventType, event_bus

logger = logging.getLogger(__name__)

VALID_TRIAL_ACTIONS = {"start", "extend"}
VALID_ACCESS_DECISIONS = {"approved", "rejected"}


def canonical_subscription_map(
    subscriptions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Return one authoritative subscription per organization.

    Historical deployments allowed duplicate rows. Until the convergence
    migration has run everywhere, prefer a currently valid entitlement and
    then the most recently updated record.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for subscription in subscriptions:
        org_id = str(subscription.get("org_id") or "")
        if org_id:
            grouped.setdefault(org_id, []).append(subscription)

    def priority(subscription: dict[str, Any]) -> tuple[int, str]:
        timestamp = str(
            subscription.get("approved_at")
            or subscription.get("updated_at")
            or subscription.get("created_at")
            or ""
        )
        return (1 if _access_state(subscription) == "active" else 0, timestamp)

    return {org_id: max(rows, key=priority) for org_id, rows in grouped.items() if rows}


def _api_error_code(exc: APIError) -> str:
    """Extract a PostgREST error code without depending on SDK internals."""
    code = getattr(exc, "code", None)
    if code:
        return str(code)
    if exc.args and isinstance(exc.args[0], dict):
        return str(exc.args[0].get("code") or "")
    return ""


def _rpc_payload(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    raise RuntimeError("Membership transaction returned an invalid payload")


def _durable_change_id(scope: str, org_id: str, idempotency_key: str | None) -> str:
    """Map an HTTP idempotency key to the UUID used by the database ledger."""
    if idempotency_key is None:
        return str(uuid.uuid4())
    normalized = idempotency_key.strip()
    if not normalized or len(normalized) > 128:
        raise ValueError("Invalid idempotency key")
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"nexus:membership:{scope}:{org_id}:{normalized}",
        )
    )


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
            "id, name, slug, created_at, plan, tier, payment_status"
        )
        count_query = client.table("organizations").select("id", count="exact")

        if search:
            query = query.ilike("name", f"%{search}%")
            count_query = count_query.ilike("name", f"%{search}%")
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
            subscription_map = canonical_subscription_map(subscriptions.data or [])
            users = (
                await client.table("users")
                .select("id, organization_id")
                .in_("organization_id", org_ids)
                .execute()
            )
            user_counts: dict[str, int] = {}
            for user in users.data or []:
                user_org_id = str(user.get("organization_id") or "")
                user_counts[user_org_id] = user_counts.get(user_org_id, 0) + 1
        else:
            user_counts = {}

        enriched = []
        for org in organizations:
            subscription = subscription_map.get(str(org.get("id")))
            access_state = _access_state(subscription)
            enriched.append(
                {
                    **org,
                    # Organizations do not have a lifecycle status column in the
                    # canonical schema. Membership state belongs to subscriptions.
                    "status": "active",
                    "subscription": subscription,
                    "access_state": access_state,
                    "is_member": access_state == "active",
                    "user_count": user_counts.get(str(org.get("id")), 0),
                }
            )

        if status:
            enriched = [item for item in enriched if item["access_state"] == status]

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

        subscription_result = (
            await client.table("subscriptions")
            .select("*")
            .eq("org_id", org_id)
            .execute()
        )
        subscription = canonical_subscription_map(subscription_result.data or []).get(
            org_id
        )
        quotas = await self._maybe_first(
            client.table("tenant_quotas").select("*").eq("org_id", org_id).limit(1)
        )

        return {
            **org_data,
            "status": "active",
            "user_count": user_count,
            "ai_calls_30d": ai_calls_30d,
            "subscription": subscription,
            "quotas": quotas,
            "access_state": _access_state(subscription),
            "is_member": _access_state(subscription) == "active",
        }

    async def suspend_organization(
        self, org_id: str, reason: str, admin_user_id: str | None = None
    ) -> bool:
        client = self._get_global_client()
        result = (
            await client.table("subscriptions")
            .update({"status": "suspended", "notes": reason})
            .eq("org_id", org_id)
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
            await client.table("subscriptions")
            .update({"status": "active"})
            .eq("org_id", org_id)
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
            await client.table("organizations").select("id", count="exact").execute()
        )
        user_result = await client.table("users").select("id", count="exact").execute()

        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        usage_result = (
            await client.table("user_token_usage")
            .select("request_count, user_id")
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
        monthly_active_users = len(
            {
                str(row["user_id"])
                for row in (usage_result.data or [])
                if row.get("user_id")
            }
        )

        orgs = org_result.data or []
        subscriptions = canonical_subscription_map(
            subscription_result.data or []
        ).values()
        return {
            "total_organizations": (
                org_result.count if org_result.count is not None else len(orgs)
            ),
            "active_organizations": len(orgs),
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
            query = query.eq("actor_user_id", filters["user_id"])
        if filters.get("org_id"):
            query = query.eq("org_id", filters["org_id"])
        if filters.get("date_from"):
            query = query.gte("timestamp", filters["date_from"])
        if filters.get("date_to"):
            query = query.lte("timestamp", filters["date_to"])

        result = (
            await query.order("timestamp", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return [
            {
                **item,
                "user_id": item.get("actor_user_id"),
                "details": item.get("details_json") or {},
                "created_at": item.get("timestamp"),
            }
            for item in (result.data or [])
        ]

    async def admin_change_plan(
        self,
        org_id: str,
        plan: str,
        reason: str,
        admin_user_id: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if plan not in VALID_PLANS:
            raise ValueError(f"Invalid plan: {plan}")
        if not reason.strip():
            raise ValueError("A reason is required for plan changes")

        client = self._get_global_client()
        current = await self._maybe_first(
            client.table("subscriptions")
            .select("current_period_end")
            .eq("org_id", org_id)
            .limit(1)
        )
        return await self.admin_set_access(
            org_id=org_id,
            plan=plan,
            expires_at=(current or {}).get("current_period_end"),
            reason=reason,
            admin_user_id=admin_user_id,
            idempotency_key=idempotency_key,
            idempotency_scope="change-plan",
        )

    async def admin_set_access(
        self,
        org_id: str,
        plan: str,
        expires_at: str | None,
        reason: str,
        admin_user_id: str,
        source: str = "admin_override",
        idempotency_key: str | None = None,
        idempotency_scope: str = "set-access",
        status_override: str | None = None,
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
        status = status_override or ("active" if plan != "free" else "inactive")
        if status not in {"active", "inactive", "trialing"}:
            raise ValueError("Invalid membership status")
        change_id = _durable_change_id(idempotency_scope, org_id, idempotency_key)
        expiry_value = parsed_expiry.isoformat() if parsed_expiry else None
        replayed = False
        try:
            transaction = await client.rpc(
                "set_subscription_access_atomic",
                {
                    "p_change_id": change_id,
                    "p_org_id": org_id,
                    "p_plan": plan,
                    "p_status": status,
                    "p_current_period_end": expiry_value,
                    "p_access_source": source,
                    "p_admin_user_id": admin_user_id,
                    "p_reason": reason,
                },
            ).execute()
            transaction_payload = _rpc_payload(transaction.data)
            subscription_payload = transaction_payload.get("subscription") or {}
            change_id = str(transaction_payload.get("change_id") or change_id)
            replayed = bool(transaction_payload.get("replayed"))
        except APIError as exc:
            if _api_error_code(exc) != "PGRST202":
                raise
            logger.warning(
                "Atomic membership RPC is not available; using compatibility path"
            )
            subscription_payload = await self._legacy_set_access(
                client=client,
                org_id=org_id,
                plan=plan,
                status=status,
                expires_at=expiry_value,
                source=source,
                reason=reason,
                admin_user_id=admin_user_id,
                change_id=change_id,
                now=now,
            )
        self._invalidate_billing_cache(org_id)
        if not replayed:
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
                "expires_at": subscription_payload.get(
                    "current_period_end", expiry_value
                ),
                "source": source,
                "reason": reason,
                "replayed": replayed,
            },
        )
        return {
            "org_id": org_id,
            "plan": str(subscription_payload.get("plan") or plan),
            "status": str(subscription_payload.get("status") or status),
            "current_period_end": subscription_payload.get(
                "current_period_end", expiry_value
            ),
            "access_source": str(subscription_payload.get("access_source") or source),
            "change_id": change_id,
            "replayed": replayed,
        }

    async def _legacy_set_access(
        self,
        *,
        client,
        org_id: str,
        plan: str,
        status: str,
        expires_at: str | None,
        source: str,
        reason: str,
        admin_user_id: str,
        change_id: str,
        now: str,
    ) -> dict[str, Any]:
        """Compatibility path used only while the atomic RPC is being deployed."""
        previous_snapshot = await self._maybe_first(
            client.table("subscriptions").select("*").eq("org_id", org_id).limit(1)
        )
        payload = {
            "org_id": org_id,
            "plan": plan,
            "status": status,
            "current_period_end": expires_at,
            "access_source": source,
            "approved_by": admin_user_id,
            "approved_at": now,
            "notes": reason,
            "updated_at": now,
        }
        result = (
            await client.table("subscriptions")
            .upsert(payload, on_conflict="org_id")
            .execute()
        )
        if not result.data:
            raise RuntimeError("Failed to update subscription access")
        await client.table("organizations").update({"plan": plan, "tier": plan}).eq(
            "id", org_id
        ).execute()
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
                    "current_period_end": expires_at,
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
        return payload

    async def admin_adjust_access_days(
        self,
        org_id: str,
        days: int,
        reason: str,
        admin_user_id: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Extend or shorten one organization's membership from its current end."""
        if days == 0 or days < -3650 or days > 3650:
            raise ValueError("Adjustment days must be between -3650 and 3650")
        client = self._get_global_client()
        current = await self._maybe_first(
            client.table("subscriptions").select("*").eq("org_id", org_id).limit(1)
        )
        state = _access_state(current)
        if days < 0 and state != "active":
            raise ValueError("Only an active membership can be shortened")

        now = datetime.now(UTC)
        current_end = _parse_datetime(
            current.get("current_period_end") if current else None
        )
        if state == "active" and not current_end:
            raise ValueError("长期有效会员无法增减天数，请先设置明确到期日")
        if days > 0:
            base = current_end if current_end and current_end > now else now
            new_end = base + timedelta(days=days)
        else:
            assert current_end is not None
            new_end = current_end + timedelta(days=days)

        if new_end <= now:
            result = await self.admin_set_access(
                org_id,
                "free",
                None,
                reason,
                admin_user_id,
                idempotency_key=idempotency_key,
                idempotency_scope="adjust-access",
            )
        else:
            current_plan = str((current or {}).get("plan") or "enterprise")
            plan = (
                current_plan if current_plan in VALID_PLANS - {"free"} else "enterprise"
            )
            result = await self.admin_set_access(
                org_id,
                plan,
                new_end.isoformat(),
                reason,
                admin_user_id,
                idempotency_key=idempotency_key,
                idempotency_scope="adjust-access",
            )
        result["adjusted_days"] = days
        return result

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
        idempotency_key: str | None = None,
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
        result = await self.admin_set_access(
            org_id=org_id,
            plan=plan,
            expires_at=period_end.isoformat(),
            reason=reason,
            admin_user_id=admin_user_id,
            source="admin_override",
            idempotency_key=idempotency_key,
            idempotency_scope="manage-trial",
            status_override="trialing",
        )
        result.update(
            {
                "action": action,
                "trial_days": days,
                "trial_end": period_end.isoformat(),
            }
        )
        return result

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
            change_id = str(result_data["change_id"])
            self._invalidate_billing_cache(org_id)
            if not result_data.get("replayed"):
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
                        "actor_user_id": admin_user_id,
                        "org_id": org_id,
                        "organization_id": org_id,
                        "target_id": org_id,
                        "target_table": "organizations",
                        "details_json": details,
                        "status": "success",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                .execute()
            )
        except Exception as exc:
            logger.warning("Failed to write super admin audit log: %s", exc)


super_admin_service = SuperAdminService()
