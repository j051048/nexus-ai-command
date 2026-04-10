"""
P1-1: 错误学习机制 - 从失败中改进

核心功能:
1. 记录工具调用失败案例
2. 学习成功解决方案
3. 规划前查询历史经验
"""

import logging
from datetime import UTC, datetime

from app.core.database import supabase

logger = logging.getLogger(__name__)


class LearningSystem:
    """从错误中学习的系统"""

    async def record_failure(
        self,
        tool_name: str,
        error_pattern: str,
        context: dict,
        user_id: str,
        org_id: str = "default",
    ):
        """记录失败案例"""
        try:
            # 检查是否已存在相同错误模式
            result = (
                await supabase.table("agent_failures")
                .select("id, frequency")
                .eq("tool_name", tool_name)
                .eq("error_pattern", error_pattern)
                .eq("org_id", org_id)
                .execute()
            )

            if result.data:
                # 增加频率
                await supabase.table("agent_failures").update(
                    {"frequency": result.data[0]["frequency"] + 1}
                ).eq("id", result.data[0]["id"]).execute()
            else:
                # 新建记录
                await supabase.table("agent_failures").insert(
                    {
                        "tool_name": tool_name,
                        "error_pattern": error_pattern,
                        "context": context,
                        "user_id": user_id,
                        "org_id": org_id,
                        "frequency": 1,
                        "created_at": datetime.now(UTC).isoformat(),
                    }
                ).execute()

        except Exception as e:
            logger.error(f"Failed to record failure: {e}")

    async def record_success(
        self, tool_name: str, solution: str, context: dict, org_id: str = "default"
    ):
        """记录成功解决方案"""
        try:
            await supabase.table("agent_successes").insert(
                {
                    "tool_name": tool_name,
                    "solution": solution,
                    "context": context,
                    "org_id": org_id,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ).execute()
        except Exception as e:
            logger.error(f"Failed to record success: {e}")

    async def get_learned_patterns(
        self, tool_name: str, org_id: str = "default"
    ) -> list[dict]:
        """获取历史经验"""
        try:
            result = (
                await supabase.table("agent_failures")
                .select("*")
                .eq("tool_name", tool_name)
                .eq("org_id", org_id)
                .order("frequency", desc=True)
                .limit(5)
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"Failed to get learned patterns: {e}")
            return []

    async def get_success_patterns(
        self, tool_name: str, org_id: str = "default"
    ) -> list[dict]:
        """获取成功案例"""
        try:
            result = (
                await supabase.table("agent_successes")
                .select("*")
                .eq("tool_name", tool_name)
                .eq("org_id", org_id)
                .order("created_at", desc=True)
                .limit(3)
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"Failed to get success patterns: {e}")
            return []


# 全局实例
learning_system = LearningSystem()
