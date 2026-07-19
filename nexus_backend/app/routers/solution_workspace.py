"""Tenant-safe workspace for evidence-grounded customer solution proposals."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success
from app.services.solution_workspace_service import (
    STAGES,
    WORKSPACE_SCHEMA_VERSION,
    apply_template_structure,
    build_initial_workspace,
    export_docx,
    export_pdf,
    generate_solution,
    validate_workspace,
    workspace_markdown,
)
from app.services.vector_service import vector_service

router = APIRouter(prefix="/api/solution-workspace", tags=["Solution Workspace"])


class SolutionProjectCreate(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    customer_id: UUID | None = None
    customer_name: str | None = Field(default=None, max_length=200)
    industry: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    instrument_line_code: str | None = Field(default=None, max_length=80)
    application_scenario: str | None = Field(default=None, max_length=1000)
    deadline: datetime | None = None
    template_id: UUID | None = None


class SolutionProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    customer_name: str | None = Field(default=None, max_length=200)
    industry: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    instrument_line_code: str | None = Field(default=None, max_length=80)
    application_scenario: str | None = Field(default=None, max_length=1000)
    deadline: datetime | None = None
    status: (
        Literal[
            "discovery",
            "drafting",
            "review",
            "approved",
            "sent",
            "won",
            "lost",
            "archived",
        ]
        | None
    ) = None


class SolutionWorkspaceState(BaseModel):
    schema_version: Literal["solution-workspace.v1"] = WORKSPACE_SCHEMA_VERSION
    active_stage: Literal[
        "brief", "requirements", "configuration", "draft", "review", "delivery"
    ] = "brief"
    brief: dict[str, Any] = Field(default_factory=dict)
    requirements: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    packages: list[dict[str, Any]] = Field(default_factory=list, max_length=10)
    sections: list[dict[str, Any]] = Field(default_factory=list, max_length=80)
    review_gates: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    artifacts: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    generation: dict[str, Any] = Field(default_factory=dict)
    quality: dict[str, Any] = Field(default_factory=dict)
    extension_data: dict[str, Any] = Field(default_factory=dict)


class OutcomeCreate(BaseModel):
    outcome_type: Literal["proposal", "won", "lost", "revenue", "time_saved"]
    amount: float | None = Field(default=None, ge=0)
    currency: str = Field(default="CNY", max_length=10)
    note: str | None = Field(default=None, max_length=1000)


def _project_code() -> str:
    return f"SOL-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:5].upper()}"


async def _get_project(db, organization_id: str, project_id: UUID) -> dict[str, Any]:
    result = (
        await db.table("solution_projects")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("id", str(project_id))
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "方案项目不存在")
    return result.data


@router.get("/manifest")
async def get_manifest(
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    return api_success(
        data={
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "stages": STAGES,
            "output_formats": ["markdown", "docx", "pdf"],
            "external_actions_require_confirmation": True,
            "scope": {"organization_id": organization_id, "user_id": user_id},
        }
    )


@router.get("/context-options")
async def get_context_options(
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    customers = (
        await db.table("customers")
        .select(
            "id,name,company,industry,instrument_line_code,application_fields,purchase_stage,budget_source"
        )
        .eq("organization_id", organization_id)
        .order("updated_at", desc=True)
        .limit(200)
        .execute()
    )
    products = (
        await db.table("instrument_product_catalog")
        .select(
            "id,instrument_line_code,product_name,model_code,positioning,application_fields,key_specs,competitor_models,knowledge_refs"
        )
        .eq("organization_id", organization_id)
        .eq("is_active", True)
        .order("updated_at", desc=True)
        .limit(200)
        .execute()
    )
    templates = (
        await db.table("solution_templates")
        .select(
            "id,name,industry,region,instrument_line_code,status,usage_count,success_count"
        )
        .eq("organization_id", organization_id)
        .eq("status", "approved")
        .order("updated_at", desc=True)
        .execute()
    )
    return api_success(
        data={
            "customers": customers.data or [],
            "products": products.data or [],
            "templates": templates.data or [],
        }
    )


@router.get("/projects")
async def list_projects(
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    result = (
        await db.table("solution_projects")
        .select("*")
        .eq("organization_id", organization_id)
        .order("updated_at", desc=True)
        .limit(200)
        .execute()
    )
    return api_success(data={"projects": result.data or []})


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(
    body: SolutionProjectCreate,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    brief = body.model_dump(mode="json")
    brief["customer_id"] = str(body.customer_id) if body.customer_id else None
    workspace = build_initial_workspace(brief)
    if body.template_id:
        template_result = (
            await db.table("solution_templates")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("id", str(body.template_id))
            .eq("status", "approved")
            .maybe_single()
            .execute()
        )
        if not template_result.data:
            raise api_error(
                ErrorCode.VALIDATION_INVALID_INPUT, "所选企业方案模板不可用"
            )
        structure = template_result.data.get("structure")
        if isinstance(structure, dict):
            workspace = apply_template_structure(workspace, structure)
        workspace["extension_data"]["template_id"] = str(body.template_id)
        await db.table("solution_templates").update(
            {
                "usage_count": int(template_result.data.get("usage_count") or 0) + 1,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ).eq("organization_id", organization_id).eq(
            "id", str(body.template_id)
        ).execute()
    else:
        workspace["extension_data"]["template_id"] = None
    payload = {
        **brief,
        "organization_id": organization_id,
        "project_code": _project_code(),
        "workspace": workspace,
        "created_by": user_id,
        "updated_by": user_id,
    }
    payload.pop("template_id", None)
    result = await db.table("solution_projects").insert(payload).execute()
    if not result.data:
        raise api_error(ErrorCode.DB_QUERY_ERROR, "创建方案项目失败")
    return api_success(data=result.data[0], message="方案项目已创建")


@router.get("/projects/{project_id}")
async def get_project(
    project_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    return api_success(data=await _get_project(db, organization_id, project_id))


@router.get("/projects/{project_id}/versions")
async def list_project_versions(
    project_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    await _get_project(db, organization_id, project_id)
    result = (
        await db.table("solution_versions")
        .select("id,version_number,title,review_status,generation_metadata,created_at")
        .eq("organization_id", organization_id)
        .eq("project_id", str(project_id))
        .order("version_number", desc=True)
        .execute()
    )
    return api_success(data={"versions": result.data or []})


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: UUID,
    body: SolutionProjectUpdate,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    await _get_project(db, organization_id, project_id)
    payload = body.model_dump(exclude_none=True, mode="json")
    payload.update({"updated_by": user_id, "updated_at": datetime.now(UTC).isoformat()})
    result = (
        await db.table("solution_projects")
        .update(payload)
        .eq("organization_id", organization_id)
        .eq("id", str(project_id))
        .execute()
    )
    return api_success(data=(result.data or [{}])[0], message="方案项目已更新")


@router.put("/projects/{project_id}/workspace")
async def save_workspace(
    project_id: UUID,
    body: SolutionWorkspaceState,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    await _get_project(db, organization_id, project_id)
    workspace = body.model_dump(mode="json")
    workspace["quality"] = validate_workspace(workspace)
    result = (
        await db.table("solution_projects")
        .update(
            {
                "workspace": workspace,
                "updated_by": user_id,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("organization_id", organization_id)
        .eq("id", str(project_id))
        .execute()
    )
    return api_success(data=(result.data or [{}])[0], message="方案工作区已保存")


@router.post("/projects/{project_id}/generate")
async def generate_project_solution(
    project_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    workspace = (
        project.get("workspace")
        if isinstance(project.get("workspace"), dict)
        else build_initial_workspace({})
    )
    brief = {**project, **(workspace.get("brief") or {})}
    products_result = (
        await db.table("instrument_product_catalog")
        .select(
            "instrument_line_code,product_name,model_code,positioning,application_fields,key_specs,knowledge_refs"
        )
        .eq("organization_id", organization_id)
        .eq("is_active", True)
        .limit(50)
        .execute()
    )
    products = products_result.data or []
    line_code = brief.get("instrument_line_code")
    if line_code:
        products = [
            item
            for item in products
            if item.get("instrument_line_code") in {None, line_code}
        ]
    query = " ".join(
        str(brief.get(key) or "")
        for key in [
            "customer_name",
            "industry",
            "region",
            "instrument_line_code",
            "application_scenario",
            "title",
        ]
    )
    knowledge_context = await vector_service.search(
        query=query, user_id=user_id, limit=6, org_id=organization_id
    )
    template = None
    template_id = (workspace.get("extension_data") or {}).get("template_id")
    if template_id:
        template_result = (
            await db.table("solution_templates")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("id", template_id)
            .maybe_single()
            .execute()
        )
        template = template_result.data
    generated_workspace, generation = await generate_solution(
        brief=brief,
        current_workspace=workspace,
        products=products,
        knowledge_context=knowledge_context,
        template=template,
        user_id=user_id,
        organization_id=organization_id,
    )
    next_version = int(project.get("current_version") or 0) + 1
    version_payload = {
        "organization_id": organization_id,
        "project_id": str(project_id),
        "version_number": next_version,
        "title": project.get("title") or "客户解决方案",
        "content": generated_workspace,
        "evidence_refs": [
            ref
            for section in generated_workspace.get("sections", [])
            for ref in section.get("evidence_refs", [])
        ],
        "generation_metadata": generation,
        "created_by": user_id,
    }
    await db.table("solution_versions").insert(version_payload).execute()
    updated = (
        await db.table("solution_projects")
        .update(
            {
                "workspace": generated_workspace,
                "current_version": next_version,
                "status": "review",
                "updated_by": user_id,
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("organization_id", organization_id)
        .eq("id", str(project_id))
        .execute()
    )
    return api_success(
        data={
            "project": (updated.data or [{}])[0],
            "version": next_version,
            "degraded": generation.get("degraded", False),
        },
        message="方案草稿已生成",
    )


@router.get("/projects/{project_id}/export")
async def export_solution(
    project_id: UUID,
    output_format: Literal["markdown", "docx", "pdf"] = Query(
        default="docx", alias="format"
    ),
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    quality = validate_workspace(project.get("workspace") or {})
    if not quality["ready_for_external_use"]:
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT, "仍有待核验证据或必选项，暂不能外发"
        )
    safe_name = re_safe_filename(project.get("project_code") or str(project_id))
    if output_format == "markdown":
        return Response(
            workspace_markdown(project).encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.md"'},
        )
    if output_format == "pdf":
        return Response(
            export_pdf(project),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.pdf"'},
        )
    return Response(
        export_docx(project),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.docx"'},
    )


def re_safe_filename(value: str) -> str:
    return "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in value
    )[:80]


@router.post("/projects/{project_id}/outcome")
async def record_outcome(
    project_id: UUID,
    body: OutcomeCreate,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    outcome_payload = body.model_dump(mode="json")
    previous_outcome = project.get("outcome") or {}
    if previous_outcome and all(
        previous_outcome.get(key) == value for key, value in outcome_payload.items()
    ):
        return api_success(data=previous_outcome, message="方案结果已记录")

    event = {
        "organization_id": organization_id,
        "user_id": user_id,
        "action_id": f"solution:{project_id}",
        "outcome_type": body.outcome_type,
        "amount": body.amount,
        "currency": body.currency,
        "evidence_ref": f"solution_project:{project_id}",
        "metadata": {"title": project.get("title"), "note": body.note},
    }
    await db.table("growth_outcome_events").insert(event).execute()
    outcome = {
        **(project.get("outcome") or {}),
        **outcome_payload,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    status_map = {"won": "won", "lost": "lost", "proposal": "sent"}
    payload: dict[str, Any] = {
        "outcome": outcome,
        "updated_by": user_id,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    if body.outcome_type in status_map:
        payload["status"] = status_map[body.outcome_type]
    await db.table("solution_projects").update(payload).eq(
        "organization_id", organization_id
    ).eq("id", str(project_id)).execute()
    if body.outcome_type == "won":
        template_id = (
            (project.get("workspace") or {}).get("extension_data") or {}
        ).get("template_id")
        if template_id:
            template_result = (
                await db.table("solution_templates")
                .select("success_count")
                .eq("organization_id", organization_id)
                .eq("id", template_id)
                .maybe_single()
                .execute()
            )
            if template_result.data:
                await db.table("solution_templates").update(
                    {
                        "success_count": int(
                            template_result.data.get("success_count") or 0
                        )
                        + 1,
                        "updated_at": datetime.now(UTC).isoformat(),
                    }
                ).eq("organization_id", organization_id).eq("id", template_id).execute()
    return api_success(data=outcome, message="方案结果已记录")


@router.post("/projects/{project_id}/promote-template")
async def promote_template(
    project_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    if project.get("status") not in {"approved", "sent", "won"}:
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT, "方案通过审核后才能沉淀为模板"
        )
    payload = {
        "organization_id": organization_id,
        "name": f"{project.get('title')}模板",
        "industry": project.get("industry"),
        "region": project.get("region"),
        "instrument_line_code": project.get("instrument_line_code"),
        "structure": project.get("workspace") or {},
        "source_project_id": str(project_id),
        "status": "approved",
        "success_count": 1 if project.get("status") == "won" else 0,
        "created_by": user_id,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    result = (
        await db.table("solution_templates")
        .upsert(payload, on_conflict="organization_id,name")
        .execute()
    )
    return api_success(data=(result.data or [{}])[0], message="已沉淀为企业方案模板")
