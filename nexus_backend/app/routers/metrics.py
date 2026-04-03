"""Agent metrics API endpoint."""
import logging

from fastapi import APIRouter, Depends

from app.core.agent_metrics import get_metrics
from app.core.auth import get_current_user_id
from app.core.errors import api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/metrics", tags=["Metrics"])


@router.get("")
async def get_agent_metrics(user_id: str = Depends(get_current_user_id)):
    """Get Agent execution metrics."""
    metrics = get_metrics()
    return api_success(data=metrics)
