"""Durable Agent artifact generation, review and download API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.agent.artifact_contract import ArtifactAudience, ArtifactType
from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success
from app.services.artifact_docx_renderer import (
    render_artifact_docx,
    render_artifact_pdf,
    render_artifact_xlsx,
)
from app.services.artifact_generation_service import generate_artifact

router = APIRouter(prefix="/api/artifacts", tags=["Agent Artifacts"])


class ArtifactGenerateRequest(BaseModel):
    original_request: str = Field(min_length=2, max_length=8000)
    source_content: str = Field(default="", max_length=40000)
    title: str | None = Field(default=None, max_length=300)
    artifact_type: ArtifactType = ArtifactType.CUSTOMER_SOLUTION
    audience: ArtifactAudience = ArtifactAudience.CUSTOMER
    requested_formats: list[Literal["docx", "pdf", "xlsx"]] = Field(
        default_factory=lambda: ["docx", "pdf"], min_length=1, max_length=3
    )
    customer_context: dict[str, Any] = Field(default_factory=dict)
    selected_document_ids: list[UUID] = Field(default_factory=list, max_length=20)
    target_character_count: int | None = Field(default=None, ge=600, le=12000)
    session_id: str | None = Field(default=None, max_length=200)
    review_confirmed: bool = False


class ArtifactReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    notes: str | None = Field(default=None, max_length=2000)
    confirmations: dict[str, bool] = Field(default_factory=dict)


class ArtifactFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
    outcome: Literal["used", "edited", "discarded", "won", "lost"] | None = None


async def _load_artifact(
    db: Any, organization_id: str, artifact_id: UUID
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact_result = (
        await db.table("artifacts")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("id", str(artifact_id))
        .maybe_single()
        .execute()
    )
    artifact = artifact_result.data
    if not artifact:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "成果不存在或无权访问")
    version_result = (
        await db.table("artifact_versions")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("artifact_id", str(artifact_id))
        .eq("version_number", artifact.get("latest_version") or 1)
        .maybe_single()
        .execute()
    )
    version = version_result.data
    if not version:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "成果版本不存在")
    return artifact, version


def _public_artifact(
    artifact: dict[str, Any], version: dict[str, Any] | None = None
) -> dict[str, Any]:
    metadata = artifact.get("metadata") or {}
    result = {
        "id": artifact.get("id"),
        "artifact_code": artifact.get("artifact_code"),
        "title": artifact.get("title"),
        "artifact_type": artifact.get("artifact_type"),
        "audience": artifact.get("audience"),
        "status": artifact.get("status"),
        "approval_status": artifact.get("approval_status"),
        "quality_score": float(artifact.get("quality_score") or 0),
        "version_number": artifact.get("latest_version") or 1,
        "requested_formats": metadata.get("requested_formats") or ["docx", "pdf"],
        "verification_items": metadata.get("verification_items") or [],
        "created_at": artifact.get("created_at"),
        "updated_at": artifact.get("updated_at"),
    }
    if version:
        result["quality"] = version.get("quality_snapshot") or {}
        evidence = version.get("evidence_snapshot") or {}
        result["evidence"] = {
            "count": len(evidence.get("records") or []),
            "coverage": evidence.get("coverage") or 0,
            "sufficient": bool(evidence.get("sufficient")),
            "missing_topics": evidence.get("missing_topics") or [],
        }
    result["download_urls"] = {
        output_format: f"/api/artifacts/{artifact.get('id')}/download?format={output_format}"
        for output_format in result["requested_formats"]
    }
    return result


@router.post("/generate", status_code=status.HTTP_201_CREATED)
async def create_artifact(
    body: ArtifactGenerateRequest,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    result = await generate_artifact(
        db=db,
        organization_id=organization_id,
        user_id=user_id,
        original_request=body.original_request,
        source_content=body.source_content,
        title=body.title,
        artifact_type=body.artifact_type,
        audience=body.audience,
        requested_formats=list(body.requested_formats),
        customer_context=body.customer_context,
        selected_document_ids=[str(item) for item in body.selected_document_ids],
        target_character_count=body.target_character_count,
        session_id=body.session_id,
        review_confirmed=body.review_confirmed,
    )
    result["download_urls"] = {
        output_format: f"/api/artifacts/{result['id']}/download?format={output_format}"
        for output_format in result["requested_formats"]
    }
    return api_success(data=result, message="精品成果已生成")


@router.get("")
async def list_artifacts(
    limit: int = Query(default=40, ge=1, le=100),
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
):
    result = (
        await db.table("artifacts")
        .select(
            "id,artifact_code,title,artifact_type,audience,status,approval_status,quality_score,latest_version,metadata,created_at,updated_at"
        )
        .eq("organization_id", organization_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return api_success(
        data={"artifacts": [_public_artifact(item) for item in (result.data or [])]}
    )


@router.get("/{artifact_id}")
async def get_artifact(
    artifact_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
):
    artifact, version = await _load_artifact(db, organization_id, artifact_id)
    return api_success(data=_public_artifact(artifact, version))


@router.get("/{artifact_id}/status")
async def get_artifact_status(
    artifact_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
):
    artifact, version = await _load_artifact(db, organization_id, artifact_id)
    return api_success(data=_public_artifact(artifact, version))


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: UUID,
    format: Literal["docx", "pdf", "xlsx"] = Query(default="docx"),
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
):
    artifact, version = await _load_artifact(db, organization_id, artifact_id)
    artifact_payload = {
        **artifact,
        "content_markdown": version.get("content_markdown") or "",
        "version_number": version.get("version_number") or 1,
        "quality_snapshot": version.get("quality_snapshot") or {},
        "artifact_label": (artifact.get("metadata") or {}).get("artifact_label"),
    }
    evidence = version.get("evidence_snapshot") or {}
    organization_result = (
        await db.table("organizations")
        .select("name")
        .eq("id", organization_id)
        .maybe_single()
        .execute()
    )
    brand = organization_result.data or {}
    if format == "pdf":
        content = render_artifact_pdf(artifact_payload, evidence, brand)
        media_type = "application/pdf"
    elif format == "xlsx":
        content = render_artifact_xlsx(artifact_payload, evidence)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        content = render_artifact_docx(artifact_payload, evidence, brand)
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    filename = f"{artifact.get('title') or 'AI成果'}.{format}"
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        "X-Artifact-Quality": str(artifact.get("quality_score") or 0),
        "X-Artifact-Approval": str(artifact.get("approval_status") or "pending"),
    }
    return Response(content=content, media_type=media_type, headers=headers)


@router.post("/{artifact_id}/review")
async def review_artifact(
    artifact_id: UUID,
    body: ArtifactReviewRequest,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    artifact, version = await _load_artifact(db, organization_id, artifact_id)
    quality = version.get("quality_snapshot") or {}
    if body.decision == "approved" and not quality.get("ready"):
        raise api_error(
            ErrorCode.RESOURCE_CONFLICT,
            "质量门尚未通过，请先补充资料或修订成果",
            details={"findings": quality.get("findings") or []},
        )
    now = datetime.now(UTC).isoformat()
    await db.table("artifact_reviews").insert(
        {
            "organization_id": organization_id,
            "artifact_id": str(artifact_id),
            "artifact_version_id": version.get("id"),
            "reviewer_id": user_id,
            "decision": body.decision,
            "notes": body.notes,
            "confirmations": body.confirmations,
            "created_at": now,
        }
    ).execute()
    next_status = "approved" if body.decision == "approved" else "needs_revision"
    await db.table("artifacts").update(
        {
            "approval_status": body.decision,
            "status": next_status,
            "updated_at": now,
        }
    ).eq("organization_id", organization_id).eq("id", str(artifact_id)).execute()
    artifact.update(
        {"approval_status": body.decision, "status": next_status, "updated_at": now}
    )
    return api_success(
        data=_public_artifact(artifact, version), message="审核状态已更新"
    )


@router.post("/{artifact_id}/feedback")
async def record_artifact_feedback(
    artifact_id: UUID,
    body: ArtifactFeedbackRequest,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    artifact, version = await _load_artifact(db, organization_id, artifact_id)
    await db.table("artifact_feedback_events").insert(
        {
            "organization_id": organization_id,
            "artifact_id": str(artifact_id),
            "artifact_version_id": version.get("id"),
            "user_id": user_id,
            "rating": body.rating,
            "comment": body.comment,
            "outcome": body.outcome,
            "quality_snapshot": version.get("quality_snapshot") or {},
            "evidence_fingerprint": (version.get("evidence_snapshot") or {}).get(
                "fingerprint"
            ),
            "created_at": datetime.now(UTC).isoformat(),
        }
    ).execute()
    return api_success(
        data={
            "artifact_id": str(artifact_id),
            "recorded": True,
            "title": artifact.get("title"),
        }
    )
