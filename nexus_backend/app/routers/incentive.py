from fastapi import APIRouter
from app.models.schemas import IncentiveTrigger
from app.services.incentive_service import IncentiveService
from app.core.errors import api_success, api_error, ErrorCode
from typing import Dict, Any

router = APIRouter(prefix="/api/incentive", tags=["Incentive"])

@router.post("/trigger", response_model=Dict[str, Any])
async def trigger_incentive(trigger: IncentiveTrigger):
    """
    Event-driven incentive generation API.
    
    Receives trigger events and calculates bonuses/rewards.
    """
    try:
        # P4 Enhancement: Move logic to service layer
        result = await IncentiveService.trigger_incentive(trigger)
        
        return api_success(
            data=result.model_dump(),
            message="Incentive Generated Successfully"
        )
    except Exception as e:
        # Catch unexpected errors handled by service layer
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
