"""
P2 Enhancement: AI-Native Interaction Service

Implements AI-first interaction patterns and smart suggestions.
Fixes Issue #1: Product lacks AI-native interaction design.
"""

import json
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re

logger = logging.getLogger(__name__)


class InteractionType(Enum):
    """Types of AI interactions."""
    PROACTIVE_SUGGESTION = "proactive_suggestion"
    SMART_COMPLETION = "smart_completion"
    CONTEXTUAL_HELP = "contextual_help"
    PREDICTIVE_ACTION = "predictive_action"
    CONVERSATION_STARTER = "conversation_starter"


@dataclass
class AIInteraction:
    """AI interaction suggestion."""
    interaction_type: InteractionType
    trigger: str
    suggestion: str
    action: Optional[str] = None
    confidence: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AIInteractionService:
    """
    P2 Enhancement: AI-native interaction patterns.
    
    Features:
    - Proactive AI suggestions
    - Smart input completion
    - Contextual help
    - Predictive actions
    - Conversation starters
    - User behavior learning
    """
    
    # Proactive suggestion triggers
    SUGGESTION_TRIGGERS = {
        "idle_timeout": {
            "delay_seconds": 30,
            "suggestions": [
                "需要我帮您分析数据吗？",
                "我可以帮您查询最新的业务报告",
                "有什么问题想问我吗？"
            ]
        },
        "page_load": {
            "suggestions": [
                "我可以帮您处理这些数据",
                "点击这里开始智能分析"
            ]
        },
        "error_occurred": {
            "suggestions": [
                "看起来遇到了问题，需要帮助吗？",
                "我可以帮您排查这个错误"
            ]
        },
        "task_completed": {
            "suggestions": [
                "任务已完成，还需要其他帮助吗？",
                "我可以帮您生成报告"
            ]
        }
    }
    
    # Smart completion patterns
    COMPLETION_PATTERNS = [
        {
            "pattern": r"查询(.+)",
            "completions": ["销售数据", "用户信息", "订单记录", "库存状态"]
        },
        {
            "pattern": r"分析(.+)",
            "completions": ["销售趋势", "用户行为", "产品表现", "市场数据"]
        },
        {
            "pattern": r"生成(.+)",
            "completions": ["报告", "图表", "摘要", "建议"]
        },
        {
            "pattern": r"帮我(.+)",
            "completions": ["写一封邮件", "整理数据", "创建任务", "安排会议"]
        }
    ]
    
    # Conversation starters based on context
    CONVERSATION_STARTERS = {
        "dashboard": [
            "今天的数据表现如何？",
            "帮我分析关键指标变化",
            "生成今日业务摘要"
        ],
        "documents": [
            "帮我搜索相关文档",
            "总结这个文档的要点",
            "找出文档中的关键信息"
        ],
        "settings": [
            "推荐最佳配置方案",
            "帮我优化系统设置"
        ],
        "reports": [
            "生成最新的业务报告",
            "分析报告数据趋势",
            "对比历史数据"
        ],
        "default": [
            "有什么我可以帮您的？",
            "您可以问我任何问题",
            "需要我帮您做什么？"
        ]
    }
    
    def __init__(self):
        self._user_context: Dict[str, Dict] = {}  # user_id -> context
        self._interaction_history: Dict[str, List] = {}
        self._learned_preferences: Dict[str, Dict] = {}
    
    async def get_proactive_suggestion(
        self,
        user_id: str,
        trigger: str,
        context: Dict[str, Any] = None
    ) -> Optional[AIInteraction]:
        """
        Get proactive AI suggestion based on trigger.
        
        Args:
            user_id: User identifier
            trigger: Trigger type (idle_timeout, page_load, etc.)
            context: Current context
            
        Returns:
            AIInteraction suggestion or None
        """
        trigger_config = self.SUGGESTION_TRIGGERS.get(trigger)
        if not trigger_config:
            return None
        
        # Get user preferences for personalized suggestions
        preferences = self._learned_preferences.get(user_id, {})
        suggestions = trigger_config["suggestions"]
        
        # Prioritize suggestions based on user history
        if preferences.get("preferred_actions"):
            suggestions = self._prioritize_suggestions(suggestions, preferences)
        
        import random
        suggestion_text = random.choice(suggestions)
        
        return AIInteraction(
            interaction_type=InteractionType.PROACTIVE_SUGGESTION,
            trigger=trigger,
            suggestion=suggestion_text,
            confidence=0.8,
            context=context or {},
            metadata={"trigger_delay": trigger_config.get("delay_seconds", 0)}
        )
    
    async def get_smart_completions(
        self,
        user_id: str,
        current_input: str,
        limit: int = 5
    ) -> List[str]:
        """
        Get smart completions for user input.
        
        Args:
            user_id: User identifier
            current_input: Current input text
            limit: Maximum completions to return
            
        Returns:
            List of completion suggestions
        """
        completions = []
        
        for pattern_config in self.COMPLETION_PATTERNS:
            if re.search(pattern_config["pattern"], current_input):
                for completion in pattern_config["completions"]:
                    full_completion = re.sub(
                        pattern_config["pattern"],
                        f"\\1{completion}",
                        current_input
                    )
                    completions.append(full_completion)
        
        # Add user-specific completions from history
        history = self._interaction_history.get(user_id, [])
        if history:
            recent_inputs = [h.get("input", "") for h in history[-10:]]
            for inp in recent_inputs:
                if inp and inp.startswith(current_input) and inp != current_input:
                    completions.append(inp)
        
        return list(set(completions))[:limit]
    
    async def get_contextual_help(
        self,
        user_id: str,
        current_page: str,
        current_action: str = None
    ) -> Optional[AIInteraction]:
        """
        Get contextual help based on current page/action.
        
        Args:
            user_id: User identifier
            current_page: Current page identifier
            current_action: Current action being performed
            
        Returns:
            AIInteraction with help content
        """
        help_content = self._generate_contextual_help(current_page, current_action)
        
        if not help_content:
            return None
        
        return AIInteraction(
            interaction_type=InteractionType.CONTEXTUAL_HELP,
            trigger=current_page,
            suggestion=help_content["message"],
            action=help_content.get("action"),
            confidence=0.9,
            context={"page": current_page, "action": current_action}
        )
    
    def _generate_contextual_help(self, page: str, action: str = None) -> Optional[Dict]:
        """Generate contextual help content."""
        help_map = {
            "query_builder": {
                "message": "我可以帮您构建复杂查询，只需描述您想要的数据",
                "action": "show_query_examples"
            },
            "report_creator": {
                "message": "需要帮您生成报告吗？可以说出您的需求",
                "action": "start_report_wizard"
            },
            "data_import": {
                "message": "上传数据文件后，我可以自动分析并提供建议",
                "action": "show_import_tips"
            },
            "settings": {
                "message": "不确定如何配置？让我帮您优化设置",
                "action": "optimize_settings"
            }
        }
        
        return help_map.get(page)
    
    async def get_predictive_actions(
        self,
        user_id: str,
        context: Dict[str, Any]
    ) -> List[AIInteraction]:
        """
        Predict user's next actions based on context and history.
        
        Args:
            user_id: User identifier
            context: Current context
            
        Returns:
            List of predicted actions
        """
        predictions = []
        
        # Analyze user history to predict next actions
        history = self._interaction_history.get(user_id, [])
        
        if len(history) >= 3:
            # Pattern: user often does X after Y
            recent_actions = [h.get("action") for h in history[-5:]]
            
            # Simple pattern matching
            if "view_report" in recent_actions:
                predictions.append(AIInteraction(
                    interaction_type=InteractionType.PREDICTIVE_ACTION,
                    trigger="pattern_match",
                    suggestion="需要我帮您分析这份报告吗？",
                    action="analyze_report",
                    confidence=0.7
                ))
            
            if "search" in recent_actions:
                predictions.append(AIInteraction(
                    interaction_type=InteractionType.PREDICTIVE_ACTION,
                    trigger="pattern_match",
                    suggestion="要导出搜索结果吗？",
                    action="export_results",
                    confidence=0.6
                ))
        
        # Context-based predictions
        if context.get("has_unread_notifications"):
            predictions.append(AIInteraction(
                interaction_type=InteractionType.PREDICTIVE_ACTION,
                trigger="context",
                suggestion="您有新的通知，需要我帮您处理吗？",
                action="view_notifications",
                confidence=0.8
            ))
        
        return predictions[:3]  # Top 3 predictions
    
    async def get_conversation_starters(
        self,
        user_id: str,
        context: str = "default"
    ) -> List[str]:
        """
        Get conversation starters for current context.
        
        Args:
            user_id: User identifier
            context: Context identifier (dashboard, documents, etc.)
            
        Returns:
            List of conversation starter suggestions
        """
        starters = self.CONVERSATION_STARTERS.get(context, self.CONVERSATION_STARTERS["default"])
        
        # Personalize based on user history
        preferences = self._learned_preferences.get(user_id, {})
        if preferences.get("common_tasks"):
            starters = list(set(starters + preferences["common_tasks"]))
        
        return starters[:5]
    
    def record_interaction(
        self,
        user_id: str,
        interaction_type: str,
        input_text: str,
        action_taken: str = None
    ):
        """Record user interaction for learning."""
        if user_id not in self._interaction_history:
            self._interaction_history[user_id] = []
        
        self._interaction_history[user_id].append({
            "type": interaction_type,
            "input": input_text,
            "action": action_taken,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep history manageable
        if len(self._interaction_history[user_id]) > 100:
            self._interaction_history[user_id] = self._interaction_history[user_id][-50:]
        
        # Update learned preferences
        self._update_preferences(user_id)
    
    def _update_preferences(self, user_id: str):
        """Update learned preferences from interaction history."""
        history = self._interaction_history.get(user_id, [])
        if len(history) < 5:
            return
        
        # Analyze common actions
        action_counts = {}
        for h in history:
            action = h.get("action")
            if action:
                action_counts[action] = action_counts.get(action, 0) + 1
        
        # Get top actions
        top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        self._learned_preferences[user_id] = {
            "preferred_actions": [a[0] for a in top_actions],
            "common_tasks": [h.get("input", "") for h in history[-10:] if h.get("input")]
        }
    
    def _prioritize_suggestions(
        self,
        suggestions: List[str],
        preferences: Dict
    ) -> List[str]:
        """Prioritize suggestions based on user preferences."""
        preferred = preferences.get("preferred_actions", [])
        
        # Move preferred suggestions to front
        prioritized = []
        remaining = []
        
        for s in suggestions:
            if any(p in s.lower() for p in preferred):
                prioritized.append(s)
            else:
                remaining.append(s)
        
        return prioritized + remaining
    
    def set_user_context(self, user_id: str, context: Dict):
        """Set user context for better suggestions."""
        self._user_context[user_id] = context
    
    def get_user_context(self, user_id: str) -> Dict:
        """Get user context."""
        return self._user_context.get(user_id, {})


# Global instance
ai_interaction_service = AIInteractionService()
