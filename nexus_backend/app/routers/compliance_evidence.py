"""Compliance evidence collection endpoints."""

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import api_success
from app.services.compliance_evidence_service import compliance_evidence_service

router = APIRouter(prefix="/api/compliance/evidence", tags=["Compliance Evidence"])


class EvidenceCreateRequest(BaseModel):
    control_id: str = Field(..., min_length=2, max_length=64)
    framework: str = Field(..., min_length=2, max_length=32)
    evidence_type: str = Field(..., min_length=2, max_length=64)
    description: str = Field(..., min_length=3, max_length=2000)
    metadata: dict = Field(default_factory=dict)


@router.post("")
async def record_evidence(
    body: EvidenceCreateRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    org_id = getattr(request.state, "org_id", None)
    evidence = await compliance_evidence_service.record_evidence(
        control_id=body.control_id,
        framework=body.framework,
        evidence_type=body.evidence_type,
        description=body.description,
        actor_user_id=user_id,
        org_id=org_id,
        metadata=body.metadata,
    )
    return api_success(data=evidence)


@router.get("/export")
async def export_evidence(
    framework: str,
    start_at: str,
    end_at: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    org_id = getattr(request.state, "org_id", None)
    rows = await compliance_evidence_service.export_manifest(
        framework=framework,
        start_at=start_at,
        end_at=end_at,
        org_id=org_id,
    )
    return api_success(data={"rows": rows, "count": len(rows)})
