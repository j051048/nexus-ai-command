from typing import Any

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import IncentiveTrigger
from app.services.incentive_service import IncentiveService

router = APIRouter(prefix="/api/incentive", tags=["Incentive"])


@router.post("/trigger", response_model=dict[str, Any])
async def trigger_incentive(
    trigger: IncentiveTrigger, user_id: str = Depends(get_current_user_id)
):
    """
    Event-driven incentive generation API.

    Receives trigger events and calculates bonuses/rewards.
    """
    try:
        # P4 Enhancement: Move logic to service layer
        result = await IncentiveService.trigger_incentive(trigger)

        return api_success(
            data=result.model_dump(), message="Incentive Generated Successfully"
        )
    except Exception:
        # Catch unexpected errors handled by service layer
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "激励方案操作失败")
