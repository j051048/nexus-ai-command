"""
P2 Enhancement: Smart Recommendation Service

Implements proactive suggestions and intelligent recommendations.
Fixes Issue #3: Missing proactive suggestions and smart recommendations.
"""

import json
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio

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
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    expires_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class SmartRecommendationService:
    """
    P2 Enhancement: Intelligent recommendations and proactive suggestions.
    
    Features:
    - Context-aware recommendations
    - User behavior analysis
    - Proactive alerts
    - Personalized suggestions
    - Learning from feedback
    """
    
    # Recommendation rules
    RECOMMENDATION_RULES = [
        {
            "id": "low_activity_alert",
            "trigger": "user_activity_low",
            "condition": {"days_inactive": 3},
            "recommendation": {
                "type": "alert",
                "title": "好久不见",
                "description": "您有一段时间没来了，有什么我们可以帮您的？",
                "priority": "medium"
            }
        },
        {
            "id": "data_anomaly",
            "trigger": "data_anomaly_detected",
            "condition": {"threshold": 0.8},
            "recommendation": {
                "type": "alert",
                "title": "发现数据异常",
                "description": "检测到数据异常波动，建议立即查看",
                "priority": "high"
            }
        },
        {
            "id": "report_ready",
            "trigger": "report_generated",
            "condition": {},
            "recommendation": {
                "type": "content",
                "title": "报告已生成",
                "description": "您的月度报告已准备好，点击查看",
                "priority": "medium"
            }
        },
        {
            "id": "learning_suggestion",
            "trigger": "feature_unused",
            "condition": {"feature": "advanced_analysis"},
            "recommendation": {
                "type": "learning",
                "title": "发现新功能",
                "description": "高级分析功能可以帮您更好地理解数据",
                "priority": "low"
            }
        },
        {
            "id": "optimization_tip",
            "trigger": "performance_issue",
            "condition": {},
            "recommendation": {
                "type": "optimization",
                "title": "性能优化建议",
                "description": "检测到查询性能下降，建议优化索引",
                "priority": "high"
            }
        }
    ]
    
    def __init__(self):
        self._recommendations: Dict[str, List[Recommendation]] = {}  # user_id -> recommendations
        self._user_profiles: Dict[str, Dict] = {}  # user_id -> profile
        self._feedback_history: Dict[str, List] = {}
        self._recommendation_counter = 0
    
    def _generate_id(self) -> str:
        """Generate unique recommendation ID."""
        import uuid
        return f"rec_{uuid.uuid4().hex[:8]}"
    
    async def get_recommendations(
        self,
        user_id: str,
        context: Dict[str, Any] = None,
        limit: int = 5
    ) -> List[Recommendation]:
        """
        Get personalized recommendations for a user.
        
        Args:
            user_id: User identifier
            context: Current context (page, activity, etc.)
            limit: Maximum recommendations to return
            
        Returns:
            List of Recommendation objects
        """
        # Get user profile
        profile = self._user_profiles.get(user_id, {})
        
        # Get existing recommendations
        existing = self._recommendations.get(user_id, [])
        
        # Generate new recommendations based on context and rules
        new_recommendations = await self._generate_recommendations(
            user_id, profile, context or {}
        )
        
        # Combine and prioritize
        all_recommendations = existing + new_recommendations
        
        # Filter expired
        all_recommendations = self._filter_expired(all_recommendations)
        
        # Sort by priority and confidence
        all_recommendations.sort(
            key=lambda r: (r.priority.value, r.confidence),
            reverse=True
        )
        
        # Update stored recommendations
        self._recommendations[user_id] = all_recommendations
        
        return all_recommendations[:limit]
    
    async def _generate_recommendations(
        self,
        user_id: str,
        profile: Dict,
        context: Dict
    ) -> List[Recommendation]:
        """Generate new recommendations based on rules and context."""
        recommendations = []
        
        for rule in self.RECOMMENDATION_RULES:
            # Check if rule applies
            if await self._check_rule(rule, user_id, profile, context):
                rec = self._create_recommendation_from_rule(rule)
                if rec:
                    recommendations.append(rec)
        
        # Add context-based recommendations
        if context.get("page"):
            page_recs = await self._get_page_recommendations(context["page"], context)
            recommendations.extend(page_recs)
        
        # Add time-based recommendations
        time_recs = await self._get_time_based_recommendations(profile)
        recommendations.extend(time_recs)
        
        return recommendations
    
    async def _check_rule(
        self,
        rule: Dict,
        user_id: str,
        profile: Dict,
        context: Dict
    ) -> bool:
        """Check if a recommendation rule applies."""
        trigger = rule["trigger"]
        condition = rule["condition"]
        
        # Check various triggers
        if trigger == "user_activity_low":
            last_active = profile.get("last_active")
            if last_active:
                days_inactive = (datetime.utcnow() - datetime.fromisoformat(last_active)).days
                return days_inactive >= condition.get("days_inactive", 3)
        
        elif trigger == "data_anomaly_detected":
            return context.get("anomaly_detected", False)
        
        elif trigger == "report_generated":
            return context.get("report_ready", False)
        
        elif trigger == "feature_unused":
            feature = condition.get("feature")
            used_features = profile.get("used_features", [])
            return feature not in used_features
        
        elif trigger == "performance_issue":
            return context.get("performance_degraded", False)
        
        return False
    
    def _create_recommendation_from_rule(self, rule: Dict) -> Optional[Recommendation]:
        """Create recommendation from rule."""
        rec_config = rule["recommendation"]
        
        try:
            return Recommendation(
                id=self._generate_id(),
                type=RecommendationType(rec_config["type"]),
                title=rec_config["title"],
                description=rec_config["description"],
                priority=Priority[rec_config.get("priority", "MEDIUM").upper()],
                confidence=0.85,
                metadata={"rule_id": rule["id"]}
            )
        except Exception as e:
            logger.warning(f"Failed to create recommendation: {e}")
            return None
    
    async def _get_page_recommendations(
        self,
        page: str,
        context: Dict
    ) -> List[Recommendation]:
        """Get recommendations specific to a page."""
        page_recommendations = {
            "dashboard": [
                Recommendation(
                    id=self._generate_id(),
                    type=RecommendationType.ACTION,
                    title="查看今日摘要",
                    description="快速了解今日关键指标",
                    priority=Priority.MEDIUM,
                    confidence=0.9,
                    action_url="/dashboard/summary",
                    action_label="查看"
                )
            ],
            "documents": [
                Recommendation(
                    id=self._generate_id(),
                    type=RecommendationType.ACTION,
                    title="智能搜索文档",
                    description="使用AI快速找到需要的文档",
                    priority=Priority.MEDIUM,
                    confidence=0.85,
                    action_url="/documents/search?ai=true",
                    action_label="搜索"
                )
            ],
            "reports": [
                Recommendation(
                    id=self._generate_id(),
                    type=RecommendationType.ACTION,
                    title="生成报告",
                    description="AI可以帮您快速生成报告",
                    priority=Priority.MEDIUM,
                    confidence=0.88,
                    action_url="/reports/create",
                    action_label="创建"
                )
            ]
        }
        
        return page_recommendations.get(page, [])
    
    async def _get_time_based_recommendations(
        self,
        profile: Dict
    ) -> List[Recommendation]:
        """Get recommendations based on time."""
        recommendations = []
        now = datetime.utcnow()
        
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
                action_label="开始"
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
                action_label="生成"
            ))
        
        return recommendations
    
    def _filter_expired(self, recommendations: List[Recommendation]) -> List[Recommendation]:
        """Filter out expired recommendations."""
        now = datetime.utcnow()
        
        return [
            r for r in recommendations
            if not r.expires_at or datetime.fromisoformat(r.expires_at) > now
        ]
    
    async def record_feedback(
        self,
        user_id: str,
        recommendation_id: str,
        feedback: str,  # "positive", "negative", "dismissed", "actioned"
        context: Dict = None
    ):
        """
        Record user feedback on a recommendation.
        
        Args:
            user_id: User identifier
            recommendation_id: Recommendation ID
            feedback: Feedback type
            context: Additional context
        """
        if user_id not in self._feedback_history:
            self._feedback_history[user_id] = []
        
        self._feedback_history[user_id].append({
            "recommendation_id": recommendation_id,
            "feedback": feedback,
            "context": context,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Update user profile based on feedback
        if feedback == "positive":
            self._update_preference(user_id, recommendation_id, positive=True)
        elif feedback == "negative":
            self._update_preference(user_id, recommendation_id, positive=False)
        
        # Remove dismissed recommendations
        if feedback == "dismissed":
            self._remove_recommendation(user_id, recommendation_id)
    
    def _update_preference(self, user_id: str, recommendation_id: str, positive: bool):
        """Update user preferences based on feedback."""
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = {}
        
        profile = self._user_profiles[user_id]
        
        if "preferences" not in profile:
            profile["preferences"] = {}
        
        # Find the recommendation
        for rec in self._recommendations.get(user_id, []):
            if rec.id == recommendation_id:
                pref_key = f"{rec.type.value}_preference"
                current = profile["preferences"].get(pref_key, 0.5)
                
                if positive:
                    profile["preferences"][pref_key] = min(1.0, current + 0.1)
                else:
                    profile["preferences"][pref_key] = max(0.0, current - 0.1)
                break
    
    def _remove_recommendation(self, user_id: str, recommendation_id: str):
        """Remove a recommendation."""
        if user_id in self._recommendations:
            self._recommendations[user_id] = [
                r for r in self._recommendations[user_id]
                if r.id != recommendation_id
            ]
    
    def update_user_profile(self, user_id: str, profile_update: Dict):
        """Update user profile for better recommendations."""
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = {}
        
        self._user_profiles[user_id].update(profile_update)
        self._user_profiles[user_id]["last_active"] = datetime.utcnow().isoformat()
    
    async def trigger_proactive_notification(
        self,
        user_id: str,
        notification_type: str,
        data: Dict = None
    ) -> Optional[Recommendation]:
        """
        Trigger a proactive notification.
        
        Args:
            user_id: User to notify
            notification_type: Type of notification
            data: Additional data
            
        Returns:
            Recommendation if triggered
        """
        # Check if user should receive this notification
        profile = self._user_profiles.get(user_id, {})
        
        # Notification templates
        templates = {
            "task_due": Recommendation(
                id=self._generate_id(),
                type=RecommendationType.ALERT,
                title="任务即将到期",
                description="您有任务将在24小时内到期",
                priority=Priority.HIGH,
                confidence=1.0,
                expires_at=(datetime.utcnow() + timedelta(hours=24)).isoformat()
            ),
            "new_feature": Recommendation(
                id=self._generate_id(),
                type=RecommendationType.LEARNING,
                title="新功能上线",
                description="我们添加了新功能，快来体验吧！",
                priority=Priority.MEDIUM,
                confidence=0.9,
                expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat()
            ),
            "report_anomaly": Recommendation(
                id=self._generate_id(),
                type=RecommendationType.ALERT,
                title="数据异常预警",
                description="检测到异常数据，需要您的关注",
                priority=Priority.URGENT,
                confidence=0.95,
                expires_at=(datetime.utcnow() + timedelta(hours=48)).isoformat()
            )
        }
        
        if notification_type in templates:
            rec = templates[notification_type]
            
            if user_id not in self._recommendations:
                self._recommendations[user_id] = []
            
            self._recommendations[user_id].append(rec)
            
            return rec
        
        return None
    
    def get_recommendation_stats(self, user_id: str = None) -> Dict:
        """Get recommendation statistics."""
        stats = {
            "total_users": len(self._recommendations),
            "total_recommendations": sum(
                len(recs) for recs in self._recommendations.values()
            ),
            "feedback_count": sum(
                len(feedback) for feedback in self._feedback_history.values()
            )
        }
        
        if user_id:
            stats["user_recommendations"] = len(self._recommendations.get(user_id, []))
            stats["user_feedback"] = len(self._feedback_history.get(user_id, []))
        
        return stats


# Global instance
smart_recommendation_service = SmartRecommendationService()
