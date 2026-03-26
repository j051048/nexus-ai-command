"""免费版配置"""
import logging
from app.core.database import supabase

logger = logging.getLogger(__name__)

FREE_TIER_LIMITS = {
    "max_tasks_per_day": 10,
    "max_conversations": 50,
    "max_memory_items": 100
}

async def check_quota(user_id: str, resource: str, org_id: str = "default") -> bool:
    """检查用户配额"""
    try:
        # 获取用户当前使用量
        result = await supabase.table("tenant_credits")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("org_id", org_id)\
            .single()\
            .execute()

        if not result.data:
            return True  # 新用户，允许使用

        usage = result.data.get(f"{resource}_usage", 0)
        limit = FREE_TIER_LIMITS.get(f"max_{resource}", 999999)

        return usage < limit
    except Exception as e:
        logger.error(f"检查配额失败: {e}")
        return True  # 失败时允许使用
