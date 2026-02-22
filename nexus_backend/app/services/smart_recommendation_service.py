"""
P2 Enhancement: Smart Recommendation Service

Implements proactive suggestions and intelligent recommendations.
Fixes Issue #3: Missing proactive suggestions and smart recommendations.

Phase 4.4: Connected to real database for context-aware recommendations.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    """Types of recommendations."""
    CONTENT = "content"
    ACTION = "action"
    RESOURCE = "resource"
    LEARNING = "learning"
    OPTIMIZATION = "optimization"
    ALERT = "alert"


class Priority(Enum):
    """Recommendation priority levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Recommendation:
    """A single recommendation."""
    id: str
    type: RecommendationType
    title: str
    description: str
    priority: Priority
    confidence: float
    action_url: str | None = None
    action_label: str | None = None
    expires_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class SmartRecommendationService:
    """
    P2 Enhancement: Intelligent recommendations and proactive suggestions.

    Phase 4.4: Now queries real database for context-aware business recommendations.

    Features:
    - Context-aware recommendations from real business data
    - Pending approvals, stale leads, budget alerts, contract expiry
    - Time-based recommendations (weekly planning, monthly review)
    - User behavior analysis via conversation_memories
    - Learning from feedback
    """

    def __init__(self):
        self._feedback_history: dict[str, list] = {}
        self._recommendation_counter = 0

    def _generate_id(self) -> str:
        """Generate unique recommendation ID."""
        import uuid
        return f"rec_{uuid.uuid4().hex[:8]}"

    async def get_recommendations(
        self,
        user_id: str,
        context: dict[str, Any] = None,
        limit: int = 5,
        db: Any = None,
    ) -> list[Recommendation]:
        """
        Get personalized recommendations for a user based on real business data.

        Args:
            user_id: User identifier
            context: Current context (page, role, org_id, etc.)
            limit: Maximum recommendations to return

        Returns:
            List of Recommendation objects
        """
        ctx = context or {}
        recommendations: list[Recommendation] = []
        client = db or supabase

        if not client:
            return recommendations

        org_id = ctx.get("org_id")
        user_role = ctx.get("role", "employee")

        # Gather recommendations from real data sources (in parallel-safe way)
        try:
            recs = await self._get_approval_recommendations(
                user_id, user_role, org_id, client
            )
            recommendations.extend(recs)
        except Exception as e:
            logger.debug(f"Approval recommendations failed: {e}")

        try:
            recs = await self._get_lead_recommendations(
                user_id, user_role, org_id, client
            )
            recommendations.extend(recs)
        except Exception as e:
            logger.debug(f"Lead recommendations failed: {e}")

        try:
            recs = await self._get_budget_recommendations(org_id, client)
            recommendations.extend(recs)
        except Exception as e:
            logger.debug(f"Budget recommendations failed: {e}")

        try:
            recs = await self._get_contract_recommendations(org_id, client)
            recommendations.extend(recs)
        except Exception as e:
            logger.debug(f"Contract recommendations failed: {e}")

        try:
            recs = await self._get_task_recommendations(user_id, client)
            recommendations.extend(recs)
        except Exception as e:
            logger.debug(f"Task recommendations failed: {e}")

        # Add time-based recommendations
        recommendations.extend(await self._get_time_based_recommendations())

        # Add page-context recommendations
        if ctx.get("page"):
            recommendations.extend(
                await self._get_page_recommendations(ctx["page"], ctx)
            )

        # Filter expired, sort by priority + confidence, and deduplicate
        recommendations = self._filter_expired(recommendations)
        recommendations.sort(
            key=lambda r: (r.priority.value, r.confidence), reverse=True
        )

        return recommendations[:limit]

    # ────────────────────────────────────────────────────────────────
    # Real data-driven recommendation generators
    # ────────────────────────────────────────────────────────────────

    async def _get_approval_recommendations(
        self, user_id: str, role: str, org_id: str | None, client: Any
    ) -> list[Recommendation]:
        """Check for pending approvals that need attention."""
        recs: list[Recommendation] = []

        if role not in ("manager", "boss"):
            return recs

        query = (
            client.table("approval_requests")
            .select("id, type, amount, description, created_at", count="exact")
            .eq("status", "pending")
        )
        if org_id:
            query = query.eq("organization_id", org_id)

        result = await query.order("created_at", desc=False).limit(20).execute()
        pending_count = result.count or len(result.data or [])

        if pending_count > 0:
            # Check for high-amount approvals
            high_amount = [
                a for a in (result.data or [])
                if float(a.get("amount", 0)) > 5000
            ]

            if high_amount:
                recs.append(Recommendation(
                    id=self._generate_id(),
                    type=RecommendationType.ALERT,
                    title=f"有 {len(high_amount)} 笔大额审批待处理",
                    description=f"最大金额 ¥{max(float(a.get('amount', 0)) for a in high_amount):,.0f}，请及时审批",
                    priority=Priority.HIGH,
                    confidence=0.95,
                    action_url="/approvals",
                    action_label="去审批",
                    metadata={"count": len(high_amount)},
                ))

            if pending_count > 5:
                recs.append(Recommendation(
                    id=self._generate_id(),
                    type=RecommendationType.ACTION,
                    title=f"积压 {pending_count} 笔待审批",
                    description="审批请求积压较多，建议及时处理避免业务延迟",
                    priority=Priority.MEDIUM,
                    confidence=0.9,
                    action_url="/approvals",
                    action_label="去审批",
                ))

        return recs

    async def _get_lead_recommendations(
        self, user_id: str, role: str, org_id: str | None, client: Any
    ) -> list[Recommendation]:
        """Check for stale sales leads that need follow-up."""
        recs: list[Recommendation] = []

        seven_days_ago = (
            datetime.now(UTC) - timedelta(days=7)
        ).isoformat()

        query = (
            client.table("sales_leads")
            .select("id, company_name, status, assigned_to, updated_at", count="exact")
            .in_("status", ["lead", "prospect", "negotiation"])
            .lt("updated_at", seven_days_ago)
        )
        if org_id:
            query = query.eq("organization_id", org_id)

        # For non-managers, only show their own leads
        if role not in ("manager", "boss"):
            query = query.eq("assigned_to", user_id)

        result = await query.limit(10).execute()
        stale_leads = result.data or []

        if stale_leads:
            my_stale = [lead for lead in stale_leads if lead.get("assigned_to") == user_id]

            if my_stale:
                recs.append(Recommendation(
                    id=self._generate_id(),
                    type=RecommendationType.ACTION,
                    title=f"你有 {len(my_stale)} 条商机待跟进",
                    description="商机超过7天未更新，建议尽快联系客户",
                    priority=Priority.HIGH,
                    confidence=0.9,
                    action_url="/crm",
                    action_label="查看商机",
                    metadata={"lead_ids": [lead["id"] for lead in my_stale[:5]]},
                ))

            if role in ("manager", "boss") and len(stale_leads) > len(my_stale):
                team_stale = len(stale_leads) - len(my_stale)
                recs.append(Recommendation(
                    id=self._generate_id(),
                    type=RecommendationType.ALERT,
                    title=f"团队有 {team_stale} 条停滞商机",
                    description="团队商机长时间未跟进，建议了解情况并督促跟进",
                    priority=Priority.MEDIUM,
                    confidence=0.85,
                    action_url="/crm",
                    action_label="查看",
                ))

        return recs

    async def _get_budget_recommendations(
        self, org_id: str | None, client: Any
    ) -> list[Recommendation]:
        """Check for budget overruns."""
        recs: list[Recommendation] = []

        query = client.table("finance_budgets").select(
            "id, name, total_amount, used_amount, period"
        )
        if org_id:
            query = query.eq("organization_id", org_id)

        result = await query.execute()

        for b in (result.data or []):
            total = float(b.get("total_amount", 0))
            used = float(b.get("used_amount", 0))
            if total > 0:
                ratio = used / total
                if ratio >= 1.0:
                    recs.append(Recommendation(
                        id=self._generate_id(),
                        type=RecommendationType.ALERT,
                        title=f"预算超支: {b.get('name', '未知')}",
                        description=f"已使用 {ratio:.0%}，超出预算 ¥{used - total:,.0f}",
                        priority=Priority.URGENT,
                        confidence=1.0,
                        action_url="/finance",
                        action_label="查看预算",
                        metadata={"budget_id": b["id"]},
                    ))
                elif ratio >= 0.9:
                    recs.append(Recommendation(
                        id=self._generate_id(),
                        type=RecommendationType.ALERT,
                        title=f"预算即将用尽: {b.get('name', '未知')}",
                        description=f"已使用 {ratio:.0%}，剩余 ¥{total - used:,.0f}",
                        priority=Priority.HIGH,
                        confidence=0.95,
                        action_url="/finance",
                        action_label="查看预算",
                    ))

        return recs

    async def _get_contract_recommendations(
        self, org_id: str | None, client: Any
    ) -> list[Recommendation]:
        """Check for contracts expiring soon."""
        recs: list[Recommendation] = []

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        thirty_days = (
            datetime.now(UTC) + timedelta(days=30)
        ).strftime("%Y-%m-%d")

        query = (
            client.table("contracts")
            .select("id, title, end_date, status")
            .eq("status", "active")
            .gte("end_date", today)
            .lte("end_date", thirty_days)
        )
        if org_id:
            query = query.eq("organization_id", org_id)

        result = await query.limit(10).execute()
        expiring = result.data or []

        if expiring:
            urgent = [
                c for c in expiring
                if (datetime.strptime(c["end_date"], "%Y-%m-%d") -
                    datetime.now()).days <= 7
            ]
            if urgent:
                recs.append(Recommendation(
                    id=self._generate_id(),
                    type=RecommendationType.ALERT,
                    title=f"{len(urgent)} 份合同本周内到期",
                    description=f"包括: {', '.join(c.get('title', '未命名')[:15] for c in urgent[:3])}",
                    priority=Priority.URGENT,
                    confidence=1.0,
                    action_url="/contracts",
                    action_label="查看合同",
                ))
            else:
                recs.append(Recommendation(
                    id=self._generate_id(),
                    type=RecommendationType.ACTION,
                    title=f"{len(expiring)} 份合同30天内到期",
                    description="建议提前准备续签或结算事宜",
                    priority=Priority.MEDIUM,
                    confidence=0.9,
                    action_url="/contracts",
                    action_label="查看",
                ))

        return recs

    async def _get_task_recommendations(
        self, user_id: str, client: Any
    ) -> list[Recommendation]:
        """Check for overdue or near-due tasks."""
        recs: list[Recommendation] = []

        today = datetime.now(UTC).strftime("%Y-%m-%d")

        try:
            # Overdue tasks
            overdue_res = (
                await client.table("oa_tasks")
                .select("id, title, due_date", count="exact")
                .eq("assigned_to", user_id)
                .in_("status", ["pending", "in_progress"])
                .lt("due_date", today)
                .limit(5)
                .execute()
            )
            overdue_count = overdue_res.count or len(overdue_res.data or [])

            if overdue_count > 0:
                recs.append(Recommendation(
                    id=self._generate_id(),
                    type=RecommendationType.ALERT,
                    title=f"你有 {overdue_count} 个逾期任务",
                    description="任务已超过截止日期，请尽快完成或申请延期",
                    priority=Priority.HIGH,
                    confidence=1.0,
                    action_url="/oa",
                    action_label="查看任务",
                ))
        except Exception:
            pass  # oa_tasks table may not exist

        return recs

    # ────────────────────────────────────────────────────────────────
    # Static / time-based recommendations
    # ────────────────────────────────────────────────────────────────

    async def _get_page_recommendations(
        self, page: str, context: dict
    ) -> list[Recommendation]:
        """Get recommendations specific to the current page."""
        page_map = {
            "dashboard": Recommendation(
                id=self._generate_id(),
                type=RecommendationType.ACTION,
                title="查看今日摘要",
                description="快速了解今日关键指标",
                priority=Priority.MEDIUM,
                confidence=0.9,
                action_url="/dashboard/summary",
                action_label="查看",
            ),
            "documents": Recommendation(
                id=self._generate_id(),
                type=RecommendationType.ACTION,
                title="智能搜索文档",
                description="使用AI快速找到需要的文档",
                priority=Priority.MEDIUM,
                confidence=0.85,
                action_url="/documents/search?ai=true",
                action_label="搜索",
            ),
            "reports": Recommendation(
                id=self._generate_id(),
                type=RecommendationType.ACTION,
                title="生成报告",
                description="AI可以帮您快速生成报告",
                priority=Priority.MEDIUM,
                confidence=0.88,
                action_url="/reports/create",
                action_label="创建",
            ),
        }

        rec = page_map.get(page)
        return [rec] if rec else []

    async def _get_time_based_recommendations(self) -> list[Recommendation]:
        """Get recommendations based on current time."""
        recommendations = []
        now = datetime.now(UTC)

        # Monday morning: weekly planning
        if now.weekday() == 0 and now.hour < 12:
            recommendations.append(Recommendation(
                id=self._generate_id(),
                type=RecommendationType.ACTION,
                title="本周工作计划",
                description="新的一周开始了，让我帮您规划工作",
                priority=Priority.MEDIUM,
                confidence=0.75,
                action_url="/planning/weekly",
                action_label="开始",
            ))

        # End of month: monthly review
        if now.day >= 25:
            recommendations.append(Recommendation(
                id=self._generate_id(),
                type=RecommendationType.CONTENT,
                title="月度总结",
                description="这个月即将结束，生成您的月度总结",
                priority=Priority.LOW,
                confidence=0.7,
                action_url="/reports/monthly",
                action_label="生成",
            ))

        # Friday afternoon: weekly review
        if now.weekday() == 4 and now.hour >= 14:
            recommendations.append(Recommendation(
                id=self._generate_id(),
                type=RecommendationType.CONTENT,
                title="本周回顾",
                description="周末将至，回顾本周工作完成情况",
                priority=Priority.LOW,
                confidence=0.7,
                action_url="/reports/weekly",
                action_label="查看",
            ))

        return recommendations

    def _filter_expired(self, recommendations: list[Recommendation]) -> list[Recommendation]:
        """Filter out expired recommendations."""
        now = datetime.now(UTC)
        return [
            r for r in recommendations
            if not r.expires_at or datetime.fromisoformat(r.expires_at) > now
        ]

    # ────────────────────────────────────────────────────────────────
    # Feedback & profile
    # ────────────────────────────────────────────────────────────────

    async def record_feedback(
        self,
        user_id: str,
        recommendation_id: str,
        feedback: str,  # "positive", "negative", "dismissed", "actioned"
        context: dict = None,
    ):
        """Record user feedback on a recommendation."""
        if user_id not in self._feedback_history:
            self._feedback_history[user_id] = []

        self._feedback_history[user_id].append({
            "recommendation_id": recommendation_id,
            "feedback": feedback,
            "context": context,
            "timestamp": datetime.now(UTC).isoformat(),
        })

    def update_user_profile(self, user_id: str, profile_update: dict):
        """Update user profile for better recommendations (no-op for DB-backed)."""
        pass  # User profiles are now derived from DB data

    async def trigger_proactive_notification(
        self,
        user_id: str,
        notification_type: str,
        data: dict = None,
    ) -> Recommendation | None:
        """
        Trigger a proactive notification.

        Args:
            user_id: User to notify
            notification_type: Type of notification
            data: Additional data

        Returns:
            Recommendation if triggered
        """
        templates = {
            "task_due": Recommendation(
                id=self._generate_id(),
                type=RecommendationType.ALERT,
                title="任务即将到期",
                description="您有任务将在24小时内到期",
                priority=Priority.HIGH,
                confidence=1.0,
                expires_at=(datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            ),
            "new_feature": Recommendation(
                id=self._generate_id(),
                type=RecommendationType.LEARNING,
                title="新功能上线",
                description="我们添加了新功能，快来体验吧！",
                priority=Priority.MEDIUM,
                confidence=0.9,
                expires_at=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
            ),
            "report_anomaly": Recommendation(
                id=self._generate_id(),
                type=RecommendationType.ALERT,
                title="数据异常预警",
                description=(data or {}).get("message", "检测到异常数据，需要您的关注"),
                priority=Priority.URGENT,
                confidence=0.95,
                expires_at=(datetime.now(UTC) + timedelta(hours=48)).isoformat(),
            ),
        }

        return templates.get(notification_type)

    def get_recommendation_stats(self, user_id: str = None) -> dict:
        """Get recommendation statistics."""
        stats = {
            "feedback_count": sum(
                len(feedback) for feedback in self._feedback_history.values()
            ),
        }

        if user_id:
            stats["user_feedback"] = len(self._feedback_history.get(user_id, []))

        return stats


# Global instance
smart_recommendation_service = SmartRecommendationService()
