from fastapi import APIRouter
from app.models.schemas import PerformanceEvent, StandardResponse
from app.services.performance_service import PerformanceService
from app.core.errors import api_success, api_error, ErrorCode

router = APIRouter(prefix="/api/performance", tags=["Performance"])


@router.post("/calculate", response_model=StandardResponse)
async def calculate_performance(event: PerformanceEvent):
    """
    Real-time performance calculation API.

    Accepts performance events (call finished, email sent), calculates score updates,
    and returns immediate feedback including triggered incentives.
    """
    try:
        # P4 Enhancement: Use PerformanceService
        result = await PerformanceService.calculate_and_save(event)

        return api_success(data=result, message="Performance Calculated Successfully")

    except Exception as e:
        # Catch unexpected errors handled by service layer
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
