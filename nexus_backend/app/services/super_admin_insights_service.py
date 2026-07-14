"""Cross-tenant operational insights for the super-admin console."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.super_admin_service import super_admin_service


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


class SuperAdminInsightsService:
    def _client(self):
        from app.core.database import supabase

        if not supabase:
            raise RuntimeError("Database service is unavailable")
        return supabase

    async def get_organization_360(self, org_id: str) -> dict[str, Any]:
        client = self._client()
        detail = await super_admin_service.get_organization_detail(org_id)
        if not detail:
            return {}

        thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).date().isoformat()
        users = (
            await client.table("users")
            .select("id, email, full_name, role, status, last_active_at, created_at")
            .eq("organization_id", org_id)
            .order("last_active_at", desc=True)
            .limit(50)
            .execute()
        )
        usage = (
            await client.table("user_token_usage")
            .select("date, total_tokens, estimated_cost_usd, request_count")
            .eq("org_id", org_id)
            .gte("date", thirty_days_ago)
            .execute()
        )
        requests = (
            await client.table("subscription_access_requests")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        versions = (
            await client.table("subscription_access_versions")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        )
        commercial = (
            await client.table("subscription_commercial_records")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        )
        audit = (
            await client.table("audit_logs")
            .select("id, action, user_id, details, created_at")
            .eq("organization_id", org_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )

        usage_rows = usage.data or []
        user_rows = users.data or []
        active_after = datetime.now(UTC) - timedelta(days=30)
        active_users = sum(
            1
            for user in user_rows
            if (
                _parse_datetime(user.get("last_active_at"))
                or datetime.min.replace(tzinfo=UTC)
            )
            >= active_after
        )
        return {
            **detail,
            "users": user_rows,
            "active_users_30d": active_users,
            "usage_30d": {
                "requests": sum(
                    int(row.get("request_count") or 0) for row in usage_rows
                ),
                "tokens": sum(int(row.get("total_tokens") or 0) for row in usage_rows),
                "cost_usd": round(
                    sum(
                        float(row.get("estimated_cost_usd") or 0) for row in usage_rows
                    ),
                    6,
                ),
            },
            "access_requests": requests.data or [],
            "access_versions": versions.data or [],
            "commercial_records": commercial.data or [],
            "audit_timeline": audit.data or [],
        }

    async def list_operational_exceptions(self) -> list[dict[str, Any]]:
        client = self._client()
        now = datetime.now(UTC)
        organizations = (
            await client.table("organizations")
            .select("id, name, status, subscription_status, plan")
            .execute()
        )
        subscriptions = await client.table("subscriptions").select("*").execute()
        requests = (
            await client.table("subscription_access_requests")
            .select("id, org_id, status, priority, due_at, created_at")
            .eq("status", "pending")
            .execute()
        )
        quotas = await client.table("tenant_quotas").select("org_id").execute()
        commercial = (
            await client.table("subscription_commercial_records")
            .select("id, org_id, order_number, payment_status, due_at")
            .in_("payment_status", ["pending", "partial", "overdue"])
            .execute()
        )

        org_map = {str(item["id"]): item for item in (organizations.data or [])}
        subscription_map = {
            str(item["org_id"]): item for item in (subscriptions.data or [])
        }
        quota_orgs = {str(item["org_id"]) for item in (quotas.data or [])}
        exceptions: list[dict[str, Any]] = []

        def add(
            key: str,
            org_id: str,
            severity: str,
            title: str,
            detail: str,
            occurred_at: str | None,
            action: str,
        ) -> None:
            org = org_map.get(org_id, {})
            exceptions.append(
                {
                    "id": key,
                    "org_id": org_id,
                    "organization_name": org.get("name", org_id),
                    "severity": severity,
                    "title": title,
                    "detail": detail,
                    "occurred_at": occurred_at,
                    "recommended_action": action,
                }
            )

        for org_id, org in org_map.items():
            subscription = subscription_map.get(org_id)
            if not subscription:
                add(
                    f"missing-subscription:{org_id}",
                    org_id,
                    "medium",
                    "会员状态未配置",
                    "企业存在但没有统一会员记录。",
                    None,
                    "补齐会员状态",
                )
            else:
                expiry = _parse_datetime(subscription.get("current_period_end"))
                if expiry and expiry <= now and subscription.get("status") == "active":
                    add(
                        f"expired-active:{org_id}",
                        org_id,
                        "critical",
                        "到期状态不一致",
                        "会员已到期但仍标记为生效。",
                        subscription.get("current_period_end"),
                        "立即核对并降级或续期",
                    )
                elif expiry and now < expiry <= now + timedelta(days=14):
                    add(
                        f"expiring:{org_id}",
                        org_id,
                        "high",
                        "会员即将到期",
                        f"将在 {expiry.date().isoformat()} 到期。",
                        subscription.get("current_period_end"),
                        "联系客户确认续期",
                    )
                if (
                    org.get("status") == "suspended"
                    and subscription.get("status") == "active"
                ):
                    add(
                        f"suspended-active:{org_id}",
                        org_id,
                        "high",
                        "企业停用但权益仍生效",
                        "组织状态与会员状态不一致。",
                        None,
                        "核对停用原因和权益状态",
                    )
            if org_id not in quota_orgs:
                add(
                    f"missing-quota:{org_id}",
                    org_id,
                    "medium",
                    "配额未配置",
                    "企业没有独立的 Token、API 或存储配额。",
                    None,
                    "设置默认配额",
                )

        for request in requests.data or []:
            due_at = _parse_datetime(request.get("due_at"))
            if due_at and due_at < now:
                org_id = str(request["org_id"])
                add(
                    f"request-overdue:{request['id']}",
                    org_id,
                    "high" if request.get("priority") != "urgent" else "critical",
                    "会员申请处理超时",
                    "申请等待时间已超过运营 SLA。",
                    request.get("due_at"),
                    "优先完成审核",
                )

        for record in commercial.data or []:
            due_at = _parse_datetime(record.get("due_at"))
            if record.get("payment_status") == "overdue" or (due_at and due_at < now):
                org_id = str(record["org_id"])
                add(
                    f"payment-overdue:{record['id']}",
                    org_id,
                    "high",
                    "商业订单逾期",
                    f"订单 {record['order_number']} 尚未完成回款。",
                    record.get("due_at"),
                    "核对回款或放行依据",
                )

        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        return sorted(
            exceptions,
            key=lambda item: (
                severity_rank.get(item["severity"], 9),
                item.get("occurred_at") or "9999",
            ),
        )

    async def get_operational_analytics(self) -> dict[str, Any]:
        client = self._client()
        now = datetime.now(UTC)
        since = (now - timedelta(days=30)).isoformat()
        organizations = await client.table("organizations").select("id, name").execute()
        subscriptions = await client.table("subscriptions").select("*").execute()
        requests = (
            await client.table("subscription_access_requests")
            .select("status, created_at, reviewed_at")
            .gte("created_at", since)
            .execute()
        )
        commercial = (
            await client.table("subscription_commercial_records").select("*").execute()
        )
        usage = (
            await client.table("user_token_usage")
            .select("org_id, total_tokens, estimated_cost_usd, request_count")
            .gte("date", (now - timedelta(days=30)).date().isoformat())
            .execute()
        )

        plan_distribution: dict[str, int] = defaultdict(int)
        expiry_buckets = {"7_days": 0, "30_days": 0, "90_days": 0}
        for subscription in subscriptions.data or []:
            plan_distribution[str(subscription.get("plan") or "free")] += 1
            expiry = _parse_datetime(subscription.get("current_period_end"))
            if not expiry or expiry <= now:
                continue
            days = (expiry - now).days
            if days <= 7:
                expiry_buckets["7_days"] += 1
            if days <= 30:
                expiry_buckets["30_days"] += 1
            if days <= 90:
                expiry_buckets["90_days"] += 1

        request_counts: dict[str, int] = defaultdict(int)
        review_seconds: list[float] = []
        for request in requests.data or []:
            request_counts[str(request.get("status") or "unknown")] += 1
            created = _parse_datetime(request.get("created_at"))
            reviewed = _parse_datetime(request.get("reviewed_at"))
            if created and reviewed:
                review_seconds.append((reviewed - created).total_seconds())

        commercial_rows = commercial.data or []
        usage_by_org: dict[str, dict[str, float]] = defaultdict(
            lambda: {"cost_usd": 0.0, "tokens": 0.0, "requests": 0.0}
        )
        for row in usage.data or []:
            org_id = str(row.get("org_id") or "unknown")
            usage_by_org[org_id]["cost_usd"] += float(
                row.get("estimated_cost_usd") or 0
            )
            usage_by_org[org_id]["tokens"] += float(row.get("total_tokens") or 0)
            usage_by_org[org_id]["requests"] += float(row.get("request_count") or 0)
        org_names = {
            str(item["id"]): item["name"] for item in (organizations.data or [])
        }
        top_cost_organizations = sorted(
            [
                {
                    "org_id": org_id,
                    "organization_name": org_names.get(org_id, org_id),
                    **values,
                }
                for org_id, values in usage_by_org.items()
            ],
            key=lambda item: item["cost_usd"],
            reverse=True,
        )[:10]

        return {
            "plan_distribution": dict(plan_distribution),
            "expiring": expiry_buckets,
            "requests_30d": dict(request_counts),
            "average_review_hours": round(
                (
                    (sum(review_seconds) / len(review_seconds) / 3600)
                    if review_seconds
                    else 0
                ),
                2,
            ),
            "commercial": {
                "collected_cents": sum(
                    int(item.get("amount_cents") or 0)
                    - int(item.get("discount_cents") or 0)
                    for item in commercial_rows
                    if item.get("payment_status") == "paid"
                ),
                "outstanding_cents": sum(
                    int(item.get("amount_cents") or 0)
                    - int(item.get("discount_cents") or 0)
                    for item in commercial_rows
                    if item.get("payment_status") in {"pending", "partial", "overdue"}
                ),
                "overdue_orders": sum(
                    1
                    for item in commercial_rows
                    if item.get("payment_status") == "overdue"
                ),
            },
            "top_cost_organizations": top_cost_organizations,
            "generated_at": now.isoformat(),
        }


super_admin_insights_service = SuperAdminInsightsService()
