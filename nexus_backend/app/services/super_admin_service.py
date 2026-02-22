"""
超级管理员服务 - 跨组织管理

提供平台级的组织管理、统计、健康检查和全局审计能力。
使用全局 supabase client（service key），因为需要跨组织访问，不受 RLS 限制。
"""

import logging
import os
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


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
        self, page: int = 1, limit: int = 20, search: str | None = None, status: str | None = None
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

            result = await query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

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
            org_result = await (
                client.table("organizations")
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
            from datetime import timedelta

            thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).isoformat()
            usage_result = await (
                client.table("ai_usage_logs")
                .select("id", count="exact")
                .eq("organization_id", org_id)
                .gte("created_at", thirty_days_ago)
                .execute()
            )
            ai_calls_30d = len(usage_result.data) if usage_result.data else 0

            return {
                **org_data,
                "user_count": user_count,
                "ai_calls_30d": ai_calls_30d,
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
                .update({
                    "status": "suspended",
                    "suspended_reason": reason,
                    "suspended_at": datetime.now(UTC).isoformat(),
                })
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
                .update({
                    "status": "active",
                    "suspended_reason": None,
                    "suspended_at": None,
                })
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
            org_result = await client.table("organizations").select("id", count="exact").execute()
            total_orgs = len(org_result.data) if org_result.data else 0

            # 总用户数
            user_result = await client.table("users").select("id", count="exact").execute()
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
                client.table("ai_usage_logs")
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
                "provider": "openai" if os.getenv("OPENAI_API_KEY") else (
                    "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "none"
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

            result = await (
                query.order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )

            return result.data or []

        except Exception as e:
            logger.error(f"获取全局审计日志失败: {e}")
            raise


super_admin_service = SuperAdminService()
