"""
Onboarding API — demo data generation for new organizations.
"""

import logging
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success
from app.services.demo_data_service import generate_demo_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


class ActivationStatePatch(BaseModel):
    step: (
        Literal["knowledge", "organize", "review", "first_value", "complete"] | None
    ) = None
    company_name: str | None = Field(default=None, max_length=200)
    instrument_families: list[str] | None = Field(default=None, max_length=10)
    markets: str | None = Field(default=None, max_length=1000)
    uploaded_document_count: int | None = Field(default=None, ge=0)
    uploaded_file_names: list[str] | None = Field(default=None, max_length=500)
    facts_confirmed: bool | None = None
    first_outcome: Literal["solution", "tender", "opportunity"] | None = None
    completed_at: datetime | None = None
    dismissed_until: datetime | None = None


class FirstValueCreate(BaseModel):
    outcome: Literal["solution", "tender", "opportunity"]
    artifact_id: UUID | None = None


def _activation_default(organization_id: str) -> dict:
    return {
        "organization_id": organization_id,
        "step": "knowledge",
        "company_name": "",
        "instrument_families": [],
        "markets": "",
        "uploaded_document_count": 0,
        "uploaded_file_names": [],
        "facts_confirmed": False,
        "first_outcome": None,
        "completed_at": None,
        "dismissed_until": None,
    }


@router.get("/activation")
async def get_activation_state(
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    result = (
        await db.table("organization_activation_state")
        .select("*")
        .eq("organization_id", organization_id)
        .maybe_single()
        .execute()
    )
    return api_success(data=result.data or _activation_default(organization_id))


@router.patch("/activation")
async def update_activation_state(
    body: ActivationStatePatch,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    current = (
        await db.table("organization_activation_state")
        .select("*")
        .eq("organization_id", organization_id)
        .maybe_single()
        .execute()
    )
    payload = {
        **_activation_default(organization_id),
        **(current.data or {}),
        **body.model_dump(exclude_unset=True, mode="json"),
        "organization_id": organization_id,
        "updated_by": user_id,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if payload.get("step") == "complete" and not payload.get("completed_at"):
        payload["completed_at"] = datetime.now(UTC).isoformat()
    result = (
        await db.table("organization_activation_state")
        .upsert(payload, on_conflict="organization_id")
        .execute()
    )
    return api_success(data=(result.data or [payload])[0], message="启用进度已保存")


@router.post("/activation/first-value")
async def record_first_value(
    body: FirstValueCreate,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    now = datetime.now(UTC).isoformat()
    payload = {
        "organization_id": organization_id,
        "step": "complete",
        "first_outcome": body.outcome,
        "first_artifact_id": str(body.artifact_id) if body.artifact_id else None,
        "facts_confirmed": True,
        "completed_at": now,
        "updated_at": now,
        "updated_by": user_id,
    }
    result = (
        await db.table("organization_activation_state")
        .upsert(payload, on_conflict="organization_id")
        .execute()
    )
    return api_success(data=(result.data or [payload])[0], message="首个业务成果已记录")


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

    logger.info(
        "[Onboarding] Demo data generation requested by user=%s org=%s", user_id, org_id
    )

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
