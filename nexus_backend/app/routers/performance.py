from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.schemas import PerformanceEvent, PerformanceResult
from app.services.rule_engine import RuleEngine
from app.core.database import supabase
from datetime import date

router = APIRouter(prefix="/api/performance", tags=["Performance"])

@router.post("/calculate", response_model=PerformanceResult)
async def calculate_performance(event: PerformanceEvent):
    """
    Real-time performance calculation based on incoming events.
    """
    try:
        # 1. Get current daily stats for user (Mocked or DB query)
        today = date.today().isoformat()
        
        # Query Supabase for existing score today
        # In real app: supabase.table('performance_scores').select('*').eq('user_id', event.user_id).eq('date', today).execute()
        current_stats = {"daily_updates_count": 2} # Mocked current state: User has done 2 updates so far

        # 2. Calculate Score Delta
        score_delta = RuleEngine.calculate_performance_score(event, current_stats)
        
        if score_delta == 0:
             return PerformanceResult(score_delta=0, new_daily_score=0)

        # 3. Update DB (Upsert)
        # We fetch current score, add delta, save back.
        # atomic increment is userd in real PG, here we simplify for Python logic layer
        
        # data = {"user_id": event.user_id, "date": today, "daily_score": score_delta} 
        # supabase.table('performance_scores').upsert(data).execute()
        
        # 4. Check for Triggers (Incentives)
        triggered = []
        if score_delta > 0:
            # Simple check: If delta pushed it over 85 (Assuming previous was 80)
            triggered.append("Potential Bonus Triggered")

        return PerformanceResult(
            score_delta=score_delta,
            new_daily_score=85.0, # Mocked new total
            triggered_incentives=triggered
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
