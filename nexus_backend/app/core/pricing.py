"""免费版配置"""
FREE_TIER_LIMITS = {
    "max_tasks_per_day": 10,
    "max_conversations": 50,
    "max_memory_items": 100
}

def check_quota(user_id: str, resource: str) -> bool:
    # 检查用户配额
    return True
