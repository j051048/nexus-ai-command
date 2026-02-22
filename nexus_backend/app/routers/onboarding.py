"""
Onboarding API — demo data generation for new organizations.
"""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.demo_data_service import generate_demo_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@router.post("/generate-demo-data")
async def generate_demo(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    One-click demo data generation for new organizations.

    Creates sample employees, customers, projects, approvals, sales leads,
    contracts, and attendance records so users can explore the platform
    immediately after onboarding.
    """
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(
            ErrorCode.VALIDATION_FAILED,
            "Organization context required. Please ensure you belong to an organization.",
        )

    logger.info("[Onboarding] Demo data generation requested by user=%s org=%s", user_id, org_id)

    try:
        summary = await generate_demo_data(user_id=user_id, org_id=org_id)
        return api_success(
            data=summary,
            message=f"Demo data generated successfully: {sum(summary.values())} records created.",
        )
    except Exception as exc:
        logger.exception("[Onboarding] Demo data generation failed: %s", exc)
        raise api_error(
            ErrorCode.SYSTEM_INTERNAL_ERROR,
            f"Failed to generate demo data: {exc}",
        )
