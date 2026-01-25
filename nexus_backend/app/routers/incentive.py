from fastapi import APIRouter, HTTPException
from app.core.database import supabase
from pydantic import BaseModel

router = APIRouter(prefix="/api/incentive", tags=["Incentive"])

class IncentiveTrigger(BaseModel):
    user_id: str
    trigger_type: str # e.g., 'daily_target_hit', 'deal_closed'
    context: dict

@router.post("/trigger")
async def trigger_incentive(trigger: IncentiveTrigger):
    """
    Event-driven incentive generation.
    """
    try:
        bonus_amount = 0
        badge = None
        reason = ""
        type_ = "bonus"

        if trigger.trigger_type == 'daily_target_hit':
            bonus_amount = 100
            reason = "Daily score > 85"
        elif trigger.trigger_type == 'deal_closed':
            # Logic: 200-500 based on value
            deal_value = trigger.context.get('value', 0)
            if deal_value > 50000:
                bonus_amount = 500
            else:
                bonus_amount = 200
            reason = f"Deal closed: {deal_value}"
        elif trigger.trigger_type == 'rank_top_3':
            type_ = "rank"
            bonus_amount = 1000
            reason = "Monthly Top 3"

        # Write to Supabase
        payload = {
            "user_id": trigger.user_id,
            "type": type_,
            "amount": bonus_amount,
            "reason": reason,
            "status": "pending"
        }
        
        # res = supabase.table('incentives').insert(payload).execute()
        
        return {"status": "success", "generated_incentive": payload}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
