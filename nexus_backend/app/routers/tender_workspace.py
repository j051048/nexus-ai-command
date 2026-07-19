"""Project-oriented tender workspace API.

This router is intentionally a thin state layer. Document extraction and AI
generation remain owned by the document pipeline and Agent tool runtime, while
this API persists the human-reviewable work product around those runs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success

router = APIRouter(prefix="/api/tender-workspace", tags=["Tender Workspace"])

WORKSPACE_SCHEMA_VERSION = "tender-workspace.v1"
TenderStage = Literal[
    "intake",
    "review",
    "matrix",
    "draft",
    "quality",
    "delivery",
]


class TenderProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=500)
    client_name: str | None = Field(default=None, max_length=200)
    deadline: datetime | None = None
    estimated_value: float | None = Field(default=None, ge=0)
    instrument_line_code: str | None = Field(default=None, max_length=80)
    application_field: str | None = Field(default=None, max_length=200)
    target_product_models: list[str] = Field(default_factory=list, max_length=30)


class TenderProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=500)
    client_name: str | None = Field(default=None, max_length=200)
    deadline: datetime | None = None
    estimated_value: float | None = Field(default=None, ge=0)
    status: (
        Literal[
            "preparation",
            "in_progress",
            "submitted",
            "won",
            "lost",
            "cancelled",
        ]
        | None
    ) = None
    compliance_status: Literal["unchecked", "passed", "has_issues"] | None = None
    win_probability: int | None = Field(default=None, ge=0, le=100)
    instrument_line_code: str | None = Field(default=None, max_length=80)
    application_field: str | None = Field(default=None, max_length=200)
    target_product_models: list[str] | None = Field(default=None, max_length=30)


class TenderWorkspaceState(BaseModel):
    schema_version: Literal["tender-workspace.v1"] = WORKSPACE_SCHEMA_VERSION
    active_stage: TenderStage = "intake"
    source_document_id: str | None = None
    source_document_name: str | None = Field(default=None, max_length=500)
    requirements: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    response_matrix: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    draft_sections: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    review_gates: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    artifacts: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    extension_data: dict[str, Any] = Field(default_factory=dict)


def _project_code() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"BID-{stamp}-{uuid4().hex[:6].upper()}"


def _workspace_from_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    workspace = metadata.get("tender_workspace")
    if not isinstance(workspace, dict):
        workspace = {
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "active_stage": "intake",
            "requirements": [],
            "response_matrix": [],
            "draft_sections": [],
            "review_gates": [],
            "artifacts": [],
            "extension_data": {},
        }
    return {**row, "workspace": workspace}


async def _get_project(db, organization_id: str, project_id: int) -> dict[str, Any]:
    result = (
        await db.table("bid_project")
        .select("*")
        .eq("tenant_id", organization_id)
        .eq("id", project_id)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "投标项目不存在")
    return result.data


@router.get("/manifest")
async def get_tender_workspace_manifest(
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    """Stable extension contract for future templates and external connectors."""
    return api_success(
        data={
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "scope": {"organization_id": organization_id, "user_id": user_id},
            "stages": [
                "intake",
                "review",
                "matrix",
                "draft",
                "quality",
                "delivery",
            ],
            "output_formats": ["pdf", "docx", "xlsx", "markdown"],
            "agent_tools": [
                "extract_bid_requirements",
                "generate_deviation_table",
                "generate_bid_document",
                "check_bid_compliance",
            ],
            "external_actions_require_confirmation": True,
        }
    )


@router.get("/projects")
async def list_tender_projects(
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    result = (
        await db.table("bid_project")
        .select("*")
        .eq("tenant_id", organization_id)
        .order("update_time", desc=True)
        .execute()
    )
    projects = [_workspace_from_row(row) for row in (result.data or [])]
    return api_success(
        data={"projects": projects, "scope": {"user_id": user_id}},
    )


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_tender_project(
    body: TenderProjectCreate,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    workspace = TenderWorkspaceState().model_dump(mode="json")
    now = datetime.now(UTC).isoformat()
    payload = {
        "tenant_id": organization_id,
        "project_code": _project_code(),
        "project_name": body.name,
        "title": body.name,
        "client_name": body.client_name,
        "buyer_name": body.client_name,
        "bid_deadline": body.deadline.isoformat() if body.deadline else None,
        "deadline": body.deadline.isoformat() if body.deadline else None,
        "estimated_value": body.estimated_value,
        "status": "preparation",
        "compliance_status": "unchecked",
        "instrument_line_code": body.instrument_line_code,
        "application_field": body.application_field,
        "target_product_models": body.target_product_models,
        "created_by": user_id,
        "updated_by": user_id,
        "metadata": {"tender_workspace": workspace},
        "update_time": now,
    }
    result = await db.table("bid_project").insert(payload).execute()
    if not result.data:
        raise api_error(ErrorCode.DB_ERROR, "创建投标项目失败")
    return api_success(
        data=_workspace_from_row(result.data[0]), message="投标项目已创建"
    )


@router.get("/projects/{project_id}")
async def get_tender_project(
    project_id: int,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    return api_success(data={**_workspace_from_row(project), "viewer_id": user_id})


@router.patch("/projects/{project_id}")
async def update_tender_project(
    project_id: int,
    body: TenderProjectUpdate,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    await _get_project(db, organization_id, project_id)
    raw = body.model_dump(exclude_none=True)
    payload: dict[str, Any] = {
        "updated_by": user_id,
        "update_time": datetime.now(UTC).isoformat(),
    }
    aliases = {
        "name": ("project_name", "title"),
        "client_name": ("client_name", "buyer_name"),
        "deadline": ("bid_deadline", "deadline"),
    }
    for key, value in raw.items():
        if isinstance(value, datetime):
            value = value.isoformat()
        targets = aliases.get(key, (key,))
        for target in targets:
            payload[target] = value
    result = (
        await db.table("bid_project")
        .update(payload)
        .eq("tenant_id", organization_id)
        .eq("id", project_id)
        .execute()
    )
    if not result.data:
        raise api_error(ErrorCode.DB_ERROR, "更新投标项目失败")
    return api_success(
        data=_workspace_from_row(result.data[0]), message="投标项目已更新"
    )


@router.put("/projects/{project_id}/workspace")
async def save_tender_workspace(
    project_id: int,
    body: TenderWorkspaceState,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    metadata = (
        project.get("metadata") if isinstance(project.get("metadata"), dict) else {}
    )
    workspace = body.model_dump(mode="json")
    workspace["updated_at"] = datetime.now(UTC).isoformat()
    metadata = {**metadata, "tender_workspace": workspace}
    evidence_refs = [
        item.get("evidence_ref")
        for item in body.response_matrix
        if item.get("evidence_ref")
    ]
    payload = {
        "metadata": metadata,
        "scoring_matrix": {
            "items": body.response_matrix,
            "schema_version": WORKSPACE_SCHEMA_VERSION,
        },
        "evidence_refs": evidence_refs,
        "documents": body.artifacts,
        "updated_by": user_id,
        "update_time": datetime.now(UTC).isoformat(),
    }
    result = (
        await db.table("bid_project")
        .update(payload)
        .eq("tenant_id", organization_id)
        .eq("id", project_id)
        .execute()
    )
    if not result.data:
        raise api_error(ErrorCode.DB_ERROR, "保存投标工作区失败")
    return api_success(
        data=_workspace_from_row(result.data[0]), message="投标工作区已保存"
    )
