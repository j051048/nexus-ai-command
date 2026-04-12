"""
领导专属工具集
实现智能审批、经营洞察、团队管理等高级管理功能
支持语音/自然语言批量处理

Refactored: Split from monolithic boss_tools.py into sub-modules.
All classes are re-exported here for backward compatibility.
"""

from .announcement import AnnouncementTool
from .business_dashboard import BusinessDashboardTool
from .customer_profile import CustomerProfileTool
from .daily_briefing import DailyBriefingTool
from .smart_approval import SmartApprovalTool
from .team_insight import TeamInsightTool

__all__ = [
    "SmartApprovalTool",
    "DailyBriefingTool",
    "BusinessDashboardTool",
    "TeamInsightTool",
    "AnnouncementTool",
    "CustomerProfileTool",
]
