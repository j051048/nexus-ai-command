"""
超级管理员服务 - 跨组织管理

提供平台级的组织管理、统计、健康检查和全局审计能力。
使用全局 supabase client（service key），因为需要跨组织访问，不受 RLS 限制。
"""

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

VALID_PLANS = {"free", "starter", "professional", "enterprise"}


class SuperAdminService:
    """超级管理员服务 - 跨组织管理"""

    def _get_global_client(self):
        """获取全局 supabase client（service key，不受 RLS 限制）"""
        from app.core.database import supabase

        if not supabase:
            raise RuntimeError("数据库服务不可用")
        return supabase

    # ============== 组织管理 ==============

    async def list_organizations(
        self,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        status: str | None = None,
    ) -> dict:
        """
        列出所有组织

        Args:
            page: 页码
            limit: 每页数量
            search: 搜索关键词（组织名称）
            status: 状态筛选 (active/suspended)

        Returns:
            包含组织列表和分页信息的字典
        """
        client = self._get_global_client()
        offset = (page - 1) * limit

        try:
            query = client.table("organizations").select(
                "id, name, created_at, status, plan, subscription_status"
            )

            if search:
                query = query.ilike("name", f"%{search}%")

            if status:
                query = query.eq("status", status)

            result = (
                await query.order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )

            # 获取总数
            count_query = client.table("organizations").select("id", count="exact")
            if search:
                count_query = count_query.ilike("name", f"%{search}%")
            if status:
                count_query = count_query.eq("status", status)
            count_result = await count_query.execute()

            total = len(count_result.data) if count_result.data else 0

            return {
                "organizations": result.data or [],
                "total": total,
                "page": page,
                "limit": limit,
                "total_pages": (total + limit - 1) // limit if total > 0 else 0,
            }

        except Exception as e:
            logger.error(f"获取组织列表失败: {e}")
            raise

    async def get_organization_detail(self, org_id: str) -> dict:
        """
        组织详情（含用户数、订阅状态、用量）

        Args:
            org_id: 组织 ID

        Returns:
            组织详情字典
        """
        client = self._get_global_client()

        try:
            # 获取组织基本信息
            org_result = (
                await client.table("organizations")
                .select("*")
                .eq("id", org_id)
                .single()
                .execute()
            )

            if not org_result.data:
                return {}

            org_data = org_result.data

            # 获取用户数
            users_result = await (
                client.table("users")
                .select("id", count="exact")
                .eq("organization_id", org_id)
                .execute()
            )
            user_count = len(users_result.data) if users_result.data else 0

            # 获取近30天 AI 调用量
            thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).isoformat()
            usage_result = await (
                client.table("api_usage_logs")
                .select("id", count="exact")
                .eq("organization_id", org_id)
                .gte("created_at", thirty_days_ago)
                .execute()
            )
            ai_calls_30d = len(usage_result.data) if usage_result.data else 0

            # 获取订阅信息
            subscription = None
            try:
                sub_result = await (
                    client.table("subscriptions")
                    .select("*")
                    .eq("org_id", org_id)
                    .limit(1)
                    .execute()
                )
                if sub_result.data:
                    subscription = sub_result.data[0]
            except Exception:
                pass

            # 获取配额信息
            quotas = None
            try:
                quota_result = await (
                    client.table("tenant_quotas")
                    .select("*")
                    .eq("org_id", org_id)
                    .limit(1)
                    .execute()
                )
                if quota_result.data:
                    quotas = quota_result.data[0]
            except Exception:
                pass

            return {
                **org_data,
                "user_count": user_count,
                "ai_calls_30d": ai_calls_30d,
                "subscription": subscription,
                "quotas": quotas,
            }

        except Exception as e:
            logger.error(f"获取组织详情失败: {e}")
            raise

    async def suspend_organization(self, org_id: str, reason: str) -> bool:
        """
        暂停组织

        Args:
            org_id: 组织 ID
            reason: 暂停原因

        Returns:
            是否成功
        """
        client = self._get_global_client()

        try:
            result = await (
                client.table("organizations")
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
                logger.info(f"组织 {org_id} 已暂停，原因: {reason}")
                return True
            return False

        except Exception as e:
            logger.error(f"暂停组织失败: {e}")
            raise

    async def unsuspend_organization(self, org_id: str) -> bool:
        """
        恢复组织

        Args:
            org_id: 组织 ID

        Returns:
            是否成功
        """
        client = self._get_global_client()

        try:
            result = await (
                client.table("organizations")
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
                logger.info(f"组织 {org_id} 已恢复")
                return True
            return False

        except Exception as e:
            logger.error(f"恢复组织失败: {e}")
            raise

    # ============== 平台统计 ==============

    async def get_platform_stats(self) -> dict:
        """
        平台级统计

        Returns:
            包含总组织数、总用户数、MAU、总 AI 调用量的字典
        """
        client = self._get_global_client()

        try:
            # 总组织数
            org_result = (
                await client.table("organizations")
                .select("id", count="exact")
                .execute()
            )
            total_orgs = len(org_result.data) if org_result.data else 0

            # 总用户数
            user_result = (
                await client.table("users").select("id", count="exact").execute()
            )
            total_users = len(user_result.data) if user_result.data else 0

            # MAU（30天内有活动的用户数）
            from datetime import timedelta

            thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).isoformat()
            mau_result = await (
                client.table("users")
                .select("id", count="exact")
                .gte("last_active_at", thirty_days_ago)
                .execute()
            )
            mau = len(mau_result.data) if mau_result.data else 0

            # 总 AI 调用量（30天）
            ai_result = await (
                client.table("api_usage_logs")
                .select("id", count="exact")
                .gte("created_at", thirty_days_ago)
                .execute()
            )
            total_ai_calls = len(ai_result.data) if ai_result.data else 0

            # 活跃组织数
            active_orgs_result = await (
                client.table("organizations")
                .select("id", count="exact")
                .eq("status", "active")
                .execute()
            )
            active_orgs = len(active_orgs_result.data) if active_orgs_result.data else 0

            return {
                "total_organizations": total_orgs,
                "active_organizations": active_orgs,
                "total_users": total_users,
                "monthly_active_users": mau,
                "total_ai_calls_30d": total_ai_calls,
                "updated_at": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.error(f"获取平台统计失败: {e}")
            raise

    # ============== 系统健康检查 ==============

    async def get_system_health(self) -> dict:
        """
        系统健康检查: DB、缓存、AI 服务、队列

        Returns:
            各子系统健康状态
        """
        health = {
            "overall": "healthy",
            "services": {},
            "checked_at": datetime.now(UTC).isoformat(),
        }

        # 数据库健康检查
        try:
            client = self._get_global_client()
            await client.table("organizations").select("id").limit(1).execute()
            health["services"]["database"] = {
                "status": "healthy",
                "latency_ms": None,
            }
        except Exception as e:
            health["services"]["database"] = {
                "status": "unhealthy",
                "error": str(e),
            }
            health["overall"] = "degraded"

        # 缓存健康检查
        try:
            from app.services.cache_service import cache_service

            await cache_service.set("_health_check", "ok", ttl=10)
            cached = await cache_service.get("_health_check")
            health["services"]["cache"] = {
                "status": "healthy" if cached == "ok" else "degraded",
            }
        except Exception as e:
            health["services"]["cache"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        # AI 服务检查
        try:
            ai_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
            health["services"]["ai"] = {
                "status": "healthy" if ai_key else "unconfigured",
                "provider": (
                    "openai"
                    if os.getenv("OPENAI_API_KEY")
                    else ("anthropic" if os.getenv("ANTHROPIC_API_KEY") else "none")
                ),
            }
        except Exception as e:
            health["services"]["ai"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        # Celery 队列检查
        try:
            celery_broker = os.getenv("CELERY_BROKER_URL")
            health["services"]["queue"] = {
                "status": "healthy" if celery_broker else "unconfigured",
            }
        except Exception as e:
            health["services"]["queue"] = {
                "status": "unhealthy",
                "error": str(e),
            }

        # 如果任何关键服务不健康，整体状态降级
        for _name, svc in health["services"].items():
            if svc.get("status") == "unhealthy":
                health["overall"] = "unhealthy"
                break
            elif svc.get("status") in ("degraded", "unconfigured"):
                if health["overall"] == "healthy":
                    health["overall"] = "degraded"

        return health

    # ============== 全局审计日志 ==============

    async def list_audit_logs_global(
        self,
        filters: dict | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """
        全局审计日志

        Args:
            filters: 筛选条件 (action, user_id, org_id, date_from, date_to)
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            审计日志列表
        """
        client = self._get_global_client()
        filters = filters or {}

        try:
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

        except Exception as e:
            logger.error(f"获取全局审计日志失败: {e}")
            raise


    async def _write_audit_log(
        self, client, action: str, admin_user_id: str, org_id: str, details: dict
    ):
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
        except Exception as e:
            logger.warning(f"写入审计日志失败: {e}")

    async def admin_change_plan(
        self, org_id: str, plan: str, reason: str, admin_user_id: str
    ) -> dict:
        if plan not in VALID_PLANS:
            raise ValueError(f"无效的计划: {plan}，可选: {', '.join(VALID_PLANS)}")

        client = self._get_global_client()

        try:
            await (
                client.table("organizations")
                .update({"tier": plan, "plan": plan})
                .eq("id", org_id)
                .execute()
            )

            await (
                client.table("subscriptions")
                .upsert({"org_id": org_id, "plan": plan, "status": "active"})
                .execute()
            )

            await self._write_audit_log(
                client,
                "admin_change_plan",
                admin_user_id,
                org_id,
                {"new_plan": plan, "reason": reason},
            )

            logger.info(f"管理员 {admin_user_id} 将组织 {org_id} 计划变更为 {plan}")
            return {"org_id": org_id, "plan": plan, "status": "active"}

        except Exception as e:
            logger.error(f"变更订阅计划失败: {e}")
            raise

    async def admin_update_quotas(
        self, org_id: str, quotas: dict, reason: str, admin_user_id: str
    ) -> dict:
        if not quotas:
            raise ValueError("至少需要提供一个配额字段")

        client = self._get_global_client()

        try:
            update_data = {"org_id": org_id, **quotas}
            await (
                client.table("tenant_quotas")
                .upsert(update_data)
                .execute()
            )

            await self._write_audit_log(
                client,
                "admin_update_quotas",
                admin_user_id,
                org_id,
                {"quotas": quotas, "reason": reason},
            )

            logger.info(f"管理员 {admin_user_id} 更新组织 {org_id} 配额: {quotas}")
            return {"org_id": org_id, "quotas": quotas}

        except Exception as e:
            logger.error(f"更新配额失败: {e}")
            raise

    async def admin_manage_trial(
        self,
        org_id: str,
        action: str,
        days: int,
        plan: str,
        reason: str,
        admin_user_id: str,
    ) -> dict:
        if action not in ("start", "extend"):
            raise ValueError("action 必须为 start 或 extend")
        if plan not in VALID_PLANS or plan == "free":
            raise ValueError(f"试用计划不能为 free，可选: starter, professional, enterprise")
        if days < 1 or days > 365:
            raise ValueError("试用天数必须在 1-365 之间")

        client = self._get_global_client()

        try:
            now = datetime.now(UTC)

            if action == "start":
                period_end = (now + timedelta(days=days)).isoformat()
            else:
                sub_result = await (
                    client.table("subscriptions")
                    .select("current_period_end")
                    .eq("org_id", org_id)
                    .limit(1)
                    .execute()
                )
                base = now
                if sub_result.data and sub_result.data[0].get("current_period_end"):
                    existing_end = datetime.fromisoformat(
                        sub_result.data[0]["current_period_end"]
                    )
                    if existing_end > now:
                        base = existing_end
                period_end = (base + timedelta(days=days)).isoformat()

            await (
                client.table("subscriptions")
                .upsert(
                    {
                        "org_id": org_id,
                        "plan": plan,
                        "status": "trialing",
                        "current_period_end": period_end,
                    }
                )
                .execute()
            )

            await (
                client.table("organizations")
                .update({"tier": plan, "plan": plan})
                .eq("id", org_id)
                .execute()
            )

            await self._write_audit_log(
                client,
                "admin_manage_trial",
                admin_user_id,
                org_id,
                {"action": action, "plan": plan, "days": days, "period_end": period_end, "reason": reason},
            )

            logger.info(
                f"管理员 {admin_user_id} 为组织 {org_id} {action}试用: plan={plan}, days={days}"
            )
            return {
                "org_id": org_id,
                "action": action,
                "plan": plan,
                "trial_days": days,
                "period_end": period_end,
            }

        except Exception as e:
            logger.error(f"管理试用期失败: {e}")
            raise


super_admin_service = SuperAdminService()
