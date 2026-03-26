"""
P0-2: 目标追踪系统 - 让 Agent 记住长期目标

核心功能:
1. 跨会话目标管理
2. 进度自动追踪
3. 主动提醒用户
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.core.database import supabase

logger = logging.getLogger(__name__)


class GoalTracker:
    """长期目标追踪器"""

    async def create_goal(self, goal_data: dict) -> str:
        """
        创建目标

        Args:
            goal_data: {
                "user_id": "uuid",
                "org_id": "uuid",
                "goal_text": "本月完成 5 个销售订单",
                "deadline": "2026-03-31T23:59:59",
                "metadata": {"target": 5, "current": 0}
            }
        """
        result = await supabase.table("agent_goals").insert({
            "user_id": goal_data["user_id"],
            "org_id": goal_data.get("org_id", "default"),
            "goal_text": goal_data["goal_text"],
            "deadline": goal_data.get("deadline"),
            "status": "pending",
            "progress": goal_data.get("metadata", {}),
            "created_at": datetime.utcnow().isoformat()
        }).execute()

        return result.data[0]["id"]

    async def get_active_goals(self, user_id: str, org_id: str = "default") -> list[dict]:
        """获取用户的活跃目标"""
        result = await supabase.table("agent_goals")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("org_id", org_id)\
            .in_("status", ["pending", "in_progress"])\
            .order("deadline", desc=False)\
            .execute()

        return result.data

    async def update_progress(self, goal_id: str, progress: dict):
        """更新目标进度"""
        await supabase.table("agent_goals")\
            .update({
                "progress": progress,
                "status": "in_progress",
                "updated_at": datetime.utcnow().isoformat()
            })\
            .eq("id", goal_id)\
            .execute()

    async def complete_goal(self, goal_id: str):
        """标记目标完成"""
        await supabase.table("agent_goals")\
            .update({
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat()
            })\
            .eq("id", goal_id)\
            .execute()

    async def check_overdue_goals(self, user_id: str) -> list[dict]:
        """检查逾期目标"""
        now = datetime.utcnow().isoformat()
        result = await supabase.table("agent_goals")\
            .select("*")\
            .eq("user_id", user_id)\
            .in_("status", ["pending", "in_progress"])\
            .lt("deadline", now)\
            .execute()

        return result.data

    async def get_goal_context_for_agent(self, user_id: str, org_id: str = "default") -> str:
        """为 Agent 生成目标上下文"""
        goals = await self.get_active_goals(user_id, org_id)

        if not goals:
            return ""

        context_parts = ["当前用户的活跃目标:"]
        for goal in goals:
            progress = goal.get("progress", {})
            deadline = goal.get("deadline", "无截止日期")
            context_parts.append(
                f"- {goal['goal_text']} (截止: {deadline}, 进度: {progress})"
            )

        return "\n".join(context_parts)


# 全局实例
goal_tracker = GoalTracker()
