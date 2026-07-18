"""
用户偏好学习服务

追踪用户对 AI 主动推送（智能巡检、定时任务、推荐等）的反馈，
学习偏好以控制推送频率和类型。

存储层: 内存缓存 + Supabase，Redis 可选。
"""

import logging
import time
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# ── 内存缓存 (key → (value, expire_ts)) ────────────────────
_cache: dict[str, tuple] = {}
_CACHE_TTL = 300  # 5 分钟


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (entry[1] is None or time.time() < entry[1]):
        return entry[0]
    _cache.pop(key, None)
    return None


def _cache_set(key: str, value, ttl: int = _CACHE_TTL):
    _cache[key] = (value, time.time() + ttl)


def _cache_delete_prefix(prefix: str):
    keys = [k for k in _cache if k.startswith(prefix)]
    for k in keys:
        del _cache[k]


# ── 默认值 ──────────────────────────────────────────────────
_DEFAULTS = {
    "active_hours_start": 9,
    "active_hours_end": 18,
    "daily_notification_limit": 5,
    "muted_types": [],
}
_WINDOW_SIZE = 20  # 滑动窗口大小
_MIN_ACCEPT_RATE = 0.10  # 最低接受率


class UserPreferenceService:
    """追踪用户对主动消息的反馈，学习偏好"""

    # ── record_feedback ─────────────────────────────────────
    async def record_feedback(
        self, user_id: str, notification_type: str, action: str
    ) -> None:
        """记录用户对通知的反馈
        action: clicked | dismissed | ignored | muted
        """
        from app.core.database import supabase

        await supabase.table("user_notification_preferences").insert(
            {
                "user_id": user_id,
                "notification_type": notification_type,
                "action": action,
            }
        ).execute()

        # 如果是 mute，同步更新 settings
        if action == "muted":
            settings = await self._load_settings(user_id)
            muted = list(set(settings.get("muted_types", []) + [notification_type]))
            await self._upsert_settings(user_id, {"muted_types": muted})

        # 清除该用户缓存
        _cache_delete_prefix(f"pref:{user_id}")

    # ── should_notify ───────────────────────────────────────
    async def should_notify(self, user_id: str, notification_type: str) -> bool:
        """判断是否应该向该用户发送该类型的通知"""
        settings = await self._load_settings(user_id)

        # 1) muted
        if notification_type in settings.get("muted_types", []):
            return False

        # 2) 活跃时段
        now_hour = datetime.now(UTC).hour  # 简化：用 UTC
        start = settings.get("active_hours_start", 9)
        end = settings.get("active_hours_end", 18)
        if start <= end:
            if not (start <= now_hour < end):
                return False
        else:  # 跨午夜
            if end <= now_hour < start:
                return False

        # 3) 今日已推送次数
        today_count = await self._get_today_count(user_id, notification_type)
        limit = settings.get("daily_notification_limit", 5)
        if today_count >= limit:
            return False

        # 4) 接受率 < 10%（但每天至少允许 1 次）
        if today_count == 0:
            return True  # 每天至少 1 次
        accept_rate = await self._get_accept_rate(user_id, notification_type)
        return not accept_rate < _MIN_ACCEPT_RATE

    # ── get_user_preferences ────────────────────────────────
    async def get_user_preferences(self, user_id: str) -> dict:
        """获取用户偏好摘要"""
        settings = await self._load_settings(user_id)
        type_stats = await self._get_type_stats(user_id)
        return {
            "active_hours": [
                settings.get("active_hours_start", 9),
                settings.get("active_hours_end", 18),
            ],
            "daily_limit": settings.get("daily_notification_limit", 5),
            "muted_types": settings.get("muted_types", []),
            "type_stats": type_stats,
        }

    # ── get_active_hours ────────────────────────────────────
    async def get_active_hours(self, user_id: str) -> tuple[int, int]:
        settings = await self._load_settings(user_id)
        return (
            settings.get("active_hours_start", 9),
            settings.get("active_hours_end", 18),
        )

    # ── update_settings ─────────────────────────────────────
    async def update_settings(self, user_id: str, updates: dict) -> dict:
        """更新用户偏好配置，返回最新设置"""
        await self._upsert_settings(user_id, updates)
        _cache_delete_prefix(f"pref:{user_id}")
        return await self.get_user_preferences(user_id)

    # ── 内部方法 ────────────────────────────────────────────
    async def _upsert_settings(self, user_id: str, updates: dict) -> None:
        from app.core.database import supabase

        row = {"user_id": user_id, **updates, "updated_at": "now()"}
        await supabase.table("user_preference_settings").upsert(
            row, on_conflict="user_id"
        ).execute()

    async def _load_settings(self, user_id: str) -> dict:
        cache_key = f"pref:{user_id}:settings"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        from app.core.database import supabase

        resp = await (
            supabase.table("user_preference_settings")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        settings = resp.data[0] if resp.data else dict(_DEFAULTS)
        _cache_set(cache_key, settings)
        return settings

    async def _get_today_count(self, user_id: str, notification_type: str) -> int:
        cache_key = f"pref:{user_id}:today:{notification_type}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        from app.core.database import supabase

        today_str = datetime.now(UTC).strftime("%Y-%m-%d")
        resp = await (
            supabase.table("user_notification_preferences")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("notification_type", notification_type)
            .gte("created_at", f"{today_str}T00:00:00Z")
            .execute()
        )
        count = resp.count or 0
        _cache_set(cache_key, count, ttl=60)  # 1 分钟缓存
        return count

    async def _get_accept_rate(self, user_id: str, notification_type: str) -> float:
        cache_key = f"pref:{user_id}:rate:{notification_type}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        from app.core.database import supabase

        resp = await (
            supabase.table("user_notification_preferences")
            .select("action")
            .eq("user_id", user_id)
            .eq("notification_type", notification_type)
            .order("created_at", desc=True)
            .limit(_WINDOW_SIZE)
            .execute()
        )
        if not resp.data:
            return 1.0  # 无数据时默认通过

        clicked = sum(1 for r in resp.data if r["action"] == "clicked")
        rate = clicked / len(resp.data)
        _cache_set(cache_key, rate, ttl=120)
        return rate

    async def _get_type_stats(self, user_id: str) -> dict:
        """获取各通知类型的统计"""
        from app.core.database import supabase

        resp = await (
            supabase.table("user_notification_preferences")
            .select("notification_type, action")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(100)
            .execute()
        )
        stats: dict[str, dict] = {}
        for row in resp.data or []:
            nt = row["notification_type"]
            if nt not in stats:
                stats[nt] = {"total": 0, "clicked": 0, "dismissed": 0, "ignored": 0}
            stats[nt]["total"] += 1
            action = row["action"]
            if action in stats[nt]:
                stats[nt][action] += 1
        # 计算接受率
        for _nt, s in stats.items():
            s["accept_rate"] = round(s["clicked"] / s["total"], 2) if s["total"] else 0
        return stats


# 单例
user_preference_service = UserPreferenceService()
