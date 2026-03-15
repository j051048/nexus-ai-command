"""
Item 54: Onboarding Agent API

Endpoints for AI-driven user onboarding: plan generation, next-step
suggestions, and tenant readiness evaluation.
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.onboarding_agent_service import onboarding_agent_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/onboarding", tags=["Onboarding Agent"])


class OnboardingPlanRequest(BaseModel):
    """Request body for generating an onboarding plan."""

    user_role: str = Field(..., description="用户角色: sales / manager / hr / finance")
    company_info: dict | None = Field(None, description="公司信息: name, industry, size 等")


@router.post("/plan")
async def generate_plan(
    body: OnboardingPlanRequest,
    user_id: str = Depends(get_current_user_id),
):
    """根据用户角色生成个性化引导计划"""
    try:
        plan = onboarding_agent_service.generate_onboarding_plan(
            user_role=body.user_role,
            company_info=body.company_info,
        )
        return api_success(data=plan, message="引导计划已生成")
    except Exception as e:
        logger.error(f"[OnboardingAgent] generate_plan error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/next")
async def get_next_suggestion(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """基于已完成步骤，推荐下一步操作"""
    try:
        db = getattr(request.state, "db", None)
        suggestion = await onboarding_agent_service.get_next_suggestion(
            user_id, db=db
        )
        return api_success(data=suggestion)
    except Exception as e:
        logger.error(f"[OnboardingAgent] get_next_suggestion error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/readiness")
async def evaluate_readiness(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """评估租户的配置完整度（0-100%）"""
    try:
        org_id = getattr(request.state, "org_id", None)
        if not org_id:
            raise api_error(
                ErrorCode.VALIDATION_INVALID_INPUT,
                "Organization context required",
            )
        db = getattr(request.state, "db", None)
        result = await onboarding_agent_service.evaluate_readiness(org_id, db=db)
        return api_success(data=result)
    except Exception as e:
        logger.error(f"[OnboardingAgent] evaluate_readiness error: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
