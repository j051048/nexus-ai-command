"""
P1-2: 用户偏好学习 - 适应用户风格

核心功能:
1. 从用户反馈学习偏好
2. 记住沟通风格
3. 优化工具推荐
"""

import logging
from datetime import datetime

from app.core.database import supabase

logger = logging.getLogger(__name__)


class PreferenceLearner:
    """用户偏好学习器"""

    async def learn_from_feedback(
        self,
        user_id: str,
        feedback_type: str,
        content: dict,
        org_id: str = "default"
    ):
        """从用户反馈学习"""
        try:
            await supabase.table("user_preferences").upsert({
                "user_id": user_id,
                "org_id": org_id,
                "preference_type": feedback_type,
                "preference_data": content,
                "updated_at": datetime.utcnow().isoformat()
            }, on_conflict="user_id,preference_type").execute()
        except Exception as e:
            logger.error(f"Failed to learn preference: {e}")

    async def get_preferences(self, user_id: str, org_id: str = "default") -> dict:
        """获取用户偏好"""
        try:
            result = await supabase.table("user_preferences")\
                .select("*")\
                .eq("user_id", user_id)\
                .eq("org_id", org_id)\
                .execute()

            prefs = {}
            for row in result.data:
                prefs[row["preference_type"]] = row["preference_data"]
            return prefs
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
            return {}


# 全局实例
preference_learner = PreferenceLearner()
