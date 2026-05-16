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

logger = logging.getLogger(__name__)

VALID_PLANS = {"free", "starter", "professional", "enterprise"}
VALID_TRIAL_ACTIONS = {"start", "extend"}


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

        result = await query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        count_result = await count_query.execute()
        total = count_result.count
        if total is None:
            total = len(count_result.data or [])

        return {
            "organizations": result.data or [],
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
        ai_calls_30d = sum(row.get("request_count", 0) for row in (usage_result.data or []))

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

        org_result = await client.table("organizations").select("id, status", count="exact").execute()
        user_result = await client.table("users").select("id, last_active_at", count="exact").execute()

        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        usage_result = (
            await client.table("user_token_usage")
            .select("request_count")
            .gte("date", thirty_days_ago.date().isoformat())
            .execute()
        )

        users = user_result.data or []
        monthly_active_users = 0
        for user in users:
            last_active = user.get("last_active_at")
            if not last_active:
                continue
            try:
                active_at = datetime.fromisoformat(str(last_active).replace("Z", "+00:00"))
                if active_at >= thirty_days_ago:
                    monthly_active_users += 1
            except ValueError:
                continue

        orgs = org_result.data or []
        return {
            "total_organizations": org_result.count if org_result.count is not None else len(orgs),
            "active_organizations": sum(1 for org in orgs if org.get("status") == "active"),
            "total_users": user_result.count if user_result.count is not None else len(users),
            "monthly_active_users": monthly_active_users,
            "total_ai_calls_30d": sum(row.get("request_count", 0) for row in (usage_result.data or [])),
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
                "status": "healthy" if getattr(settings, "OPENAI_API_KEY", None) else "unconfigured",
                "provider": getattr(settings, "AI_PROVIDER", "openai"),
            }
        except Exception as exc:
            services["ai"] = {"status": "degraded", "error": str(exc)}

        overall = "healthy"
        if any(service["status"] == "unhealthy" for service in services.values()):
            overall = "unhealthy"
        elif any(service["status"] in {"degraded", "unconfigured"} for service in services.values()):
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

        result = await query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        return result.data or []

    async def admin_change_plan(
        self, org_id: str, plan: str, reason: str, admin_user_id: str
    ) -> dict[str, Any]:
        if plan not in VALID_PLANS:
            raise ValueError(f"Invalid plan: {plan}")
        if not reason.strip():
            raise ValueError("A reason is required for plan changes")

        client = self._get_global_client()
        await client.table("organizations").update({"tier": plan, "plan": plan}).eq("id", org_id).execute()
        await client.table("subscriptions").upsert({"org_id": org_id, "plan": plan, "status": "active"}).execute()
        await self._write_audit_log(
            client,
            "admin_change_plan",
            admin_user_id,
            org_id,
            {"new_plan": plan, "reason": reason},
        )
        return {"org_id": org_id, "plan": plan, "status": "active"}

    async def admin_update_quotas(
        self, org_id: str, quotas: dict, reason: str, admin_user_id: str
    ) -> dict[str, Any]:
        if not quotas:
            raise ValueError("At least one quota value is required")
        if not reason.strip():
            raise ValueError("A reason is required for quota changes")

        client = self._get_global_client()
        payload = {**quotas, "org_id": org_id, "updated_at": datetime.now(UTC).isoformat()}
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
        period_end = now + timedelta(days=days)
        await client.table("subscriptions").upsert(
            {
                "org_id": org_id,
                "plan": plan,
                "status": "trialing",
                "trial_start": now.isoformat(),
                "trial_end": period_end.isoformat(),
                "current_period_end": period_end.isoformat(),
            }
        ).execute()
        await client.table("organizations").update(
            {
                "plan": plan,
                "tier": plan,
                "subscription_status": "trialing",
            }
        ).eq("id", org_id).execute()
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
