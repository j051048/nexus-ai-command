"""Versioned AI growth command workspace API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import api_success
from app.services.growth_command_service import (
    GROWTH_COMMAND_SCHEMA_VERSION,
    INDUSTRY_PLAYBOOKS,
    growth_capability_registry,
    growth_command_service,
)

router = APIRouter(prefix="/api/growth-command", tags=["Growth Command"])


class GrowthOutcomeRequest(BaseModel):
    action_id: str = Field(min_length=1, max_length=200)
    outcome_type: str = Field(
        pattern="^(qualified_lead|meeting|proposal|tender_submitted|won|lost|revenue|time_saved)$"
    )
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    evidence_ref: str | None = Field(default=None, max_length=1000)
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_business_evidence(self):
        if self.outcome_type in {"won", "revenue"} and not self.evidence_ref:
            raise ValueError("成交与收入结果必须提供证据引用")
        if self.outcome_type == "revenue" and self.amount is None:
            raise ValueError("收入结果必须提供金额")
        return self


@router.get("/workspace")
async def get_growth_workspace(
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    data = await growth_command_service.get_workspace(db)
    data["scope"] = {"organization_id": organization_id, "user_id": user_id}
    return api_success(data=data)


@router.get("/capabilities")
async def get_growth_capabilities(
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    return api_success(
        data={
            "schema_version": GROWTH_COMMAND_SCHEMA_VERSION,
            "scope": {"organization_id": organization_id, "user_id": user_id},
            "capabilities": growth_capability_registry.manifest(),
        }
    )


@router.get("/playbooks")
async def get_growth_playbooks(
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    return api_success(
        data={
            "schema_version": GROWTH_COMMAND_SCHEMA_VERSION,
            "scope": {"organization_id": organization_id, "user_id": user_id},
            "playbooks": INDUSTRY_PLAYBOOKS,
        }
    )


@router.post("/outcomes")
async def record_growth_outcome(
    body: GrowthOutcomeRequest,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    payload = body.model_dump(exclude_none=True)
    payload.update({"organization_id": organization_id, "user_id": user_id})
    result = await db.table("growth_outcome_events").insert(payload).execute()
    record = (result.data or [payload])[0]
    return api_success(data={"outcome": record}, message="业务结果已记录")
