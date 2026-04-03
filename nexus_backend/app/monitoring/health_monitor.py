"""
P0-3: Agent 健康监控和退化检测
"""

import logging
from datetime import datetime, timedelta

from app.core.database import supabase

logger = logging.getLogger(__name__)


class AgentHealthMonitor:
    """Agent 健康度监控"""

    async def get_success_rate(self, hours: int = None, days: int = None) -> float:
        """计算成功率"""
        try:
            if hours:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
            elif days:
                cutoff = datetime.utcnow() - timedelta(days=days)
            else:
                cutoff = datetime.utcnow() - timedelta(hours=1)

            result = await supabase.rpc("get_tool_success_rate", {"since": cutoff.isoformat()}).execute()

            return result.data if result.data else 0.0

        except Exception as e:
            logger.error(f"Failed to get success rate: {e}")
            return 0.0

    async def detect_degradation(self) -> dict:
        """检测性能退化"""
        recent = await self.get_success_rate(hours=1)
        baseline = await self.get_success_rate(days=7)

        degraded = recent < baseline * 0.8 if baseline > 0 else False

        return {
            "degraded": degraded,
            "recent_rate": recent,
            "baseline_rate": baseline,
            "drop_percentage": ((baseline - recent) / baseline * 100) if baseline > 0 else 0,
        }

    async def trigger_auto_recovery(self):
        """自动恢复"""
        from app.services.cache_service import cache_service

        logger.warning("Triggering auto-recovery")

        # 1. 清理过期缓存
        await cache_service.clear_pattern("tool_cache:*")

        # 2. 压缩历史状态
        await self.compress_old_states()

        logger.info("Auto-recovery completed")

    async def compress_old_states(self):
        """压缩旧状态"""
        datetime.utcnow() - timedelta(days=7)
        # 实现状态压缩逻辑
        pass


# 全局实例
health_monitor = AgentHealthMonitor()
