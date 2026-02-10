"""
P4 Enhancement: Performance Service

Handles real-time performance calculation, score updates, and persistent storage.
Separates orchestration logic from the API router.
"""
import logging
from datetime import date
from typing import Dict, Optional, Any
from app.models.schemas import PerformanceEvent, PerformanceResult
from app.services.rule_engine import RuleEngine
from app.core.database import supabase
from app.core.errors import api_error, ErrorCode

logger = logging.getLogger(__name__)

class PerformanceService:
    @staticmethod
    async def calculate_and_save(event: PerformanceEvent) -> PerformanceResult:
        """
        Process a performance event:
        1. Fetch current daily stats
        2. Calculate score delta
        3. Persist update
        4. Check for incentives
        """
        try:
            today_str = date.today().isoformat()
            current_stats = await PerformanceService._get_daily_stats(event.user_id, today_str)
            
            # Use data from event context if stats unavailable (fallback)
            if not current_stats and "daily_updates_count" in event.data:
                 current_stats = {"daily_updates_count": event.data["daily_updates_count"]}
            
            # Use RuleEngine for score logic
            score_delta = RuleEngine.calculate_performance_score(event, current_stats or {})
            
            new_total_score = 0.0
            if current_stats:
                current_score = float(current_stats.get("daily_score", 0))
                new_total_score = current_score + score_delta
            else:
                new_total_score = score_delta

            if score_delta != 0:
                await PerformanceService._update_score(event.user_id, today_str, score_delta, new_total_score)

            triggered = []
            if new_total_score >= 85 and (new_total_score - score_delta) < 85:
                 triggered.append("Daily Target Hit (85)")

            return PerformanceResult(
                score_delta=score_delta,
                new_daily_score=new_total_score,
                triggered_incentives=triggered
            )
            
        except Exception as e:
            logger.error(f"Performance calculation failed: {e}")
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "Performance calculation error")

    @staticmethod
    async def _get_daily_stats(user_id: str, date_str: str) -> Optional[Dict[str, Any]]:
        """Fetch daily stats from Supabase"""
        if not supabase: 
            return None
            
        try:
            # P4: Use single() for exact match
            res = await supabase.table('performance_scores')\
                .select('*')\
                .eq('user_id', user_id)\
                .eq('date', date_str)\
                .maybe_single()\
                .execute()
            
            return res.data
        except Exception as e:
            logger.warning(f"Failed to fetch daily stats from DB: {e}")
            return None

    @staticmethod
    async def _update_score(user_id: str, date_str: str, delta: float, new_total: float):
        """Persist score update to Supabase"""
        if not supabase:
            logger.info(f"[Mock DB] Updated score for {user_id}: +{delta} -> {new_total}")
            return

        try:
            data = {
                "user_id": user_id, 
                "date": date_str, 
                "daily_score": new_total,
                "updated_at": "now()" # In real PG this would use now() or CURRENT_TIMESTAMP
            }
            
            # Using upsert
            await supabase.table('performance_scores').upsert(data).execute()
        except Exception as e:
             logger.error(f"Failed to persist score update: {e}")
