"""Tenant-safe workspace for evidence-grounded customer solution proposals."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success
from app.services.solution_commercial_service import (
    enrich_workspace_commercials,
    solution_value_metrics,
)
from app.services.solution_workspace_service import (
    STAGES,
    WORKSPACE_SCHEMA_VERSION,
    apply_template_structure,
    build_initial_workspace,
    export_docx,
    export_pdf,
    export_xlsx,
    extract_requirements,
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


class ProductCatalogWrite(BaseModel):
    instrument_line_code: str = Field(min_length=2, max_length=80)
    product_name: str = Field(min_length=2, max_length=200)
    model_code: str = Field(min_length=1, max_length=120)
    positioning: str | None = Field(default=None, max_length=1000)
    application_fields: list[str] = Field(default_factory=list, max_length=50)
    key_specs: dict[str, Any] = Field(default_factory=dict)
    competitor_models: list[str] = Field(default_factory=list, max_length=50)
    knowledge_refs: list[dict[str, Any] | str] = Field(default_factory=list)
    currency: str = Field(default="CNY", max_length=10)
    list_price: float | None = Field(default=None, ge=0)
    standard_cost: float | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    warranty_months: int | None = Field(default=None, ge=0, le=240)
    lifecycle_status: Literal["draft", "active", "limited", "eol"] = "active"
    validation_status: Literal["draft", "verified", "rejected"] = "draft"
    configuration_schema: dict[str, Any] = Field(default_factory=dict)
    compatibility_rules: list[dict[str, Any]] = Field(default_factory=list)
    service_items: list[dict[str, Any] | str] = Field(default_factory=list)
    consumables: list[dict[str, Any] | str] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any] | str] = Field(default_factory=list)
    is_active: bool = True


class RequirementExtractionRequest(BaseModel):
    document_ids: list[UUID] = Field(min_length=1, max_length=12)
    replace_existing: bool = False


class SolutionFeedbackCreate(BaseModel):
    section_id: str | None = Field(default=None, max_length=120)
    rating: int | None = Field(default=None, ge=1, le=5)
    change_type: Literal["accepted", "edited", "rejected", "other"]
    note: str | None = Field(default=None, max_length=2000)
    original_content: str | None = Field(default=None, max_length=20000)
    revised_content: str | None = Field(default=None, max_length=20000)


class ConnectorWrite(BaseModel):
    connector_code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,79}$")
    display_name: str = Field(min_length=2, max_length=120)
    connector_type: Literal["crm", "erp", "im", "storage", "email", "custom"]
    status: Literal["disabled", "active", "error"] = "disabled"
    capabilities: list[str] = Field(default_factory=list, max_length=50)
    config_ref: str | None = Field(default=None, max_length=500)


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
            "output_formats": ["markdown", "docx", "pdf", "xlsx"],
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
            "id,instrument_line_code,product_name,model_code,positioning,application_fields,key_specs,competitor_models,knowledge_refs,currency,list_price,standard_cost,lead_time_days,warranty_months,lifecycle_status,validation_status,configuration_schema,compatibility_rules,service_items,consumables,evidence_refs,revision"
        )
        .eq("organization_id", organization_id)
        .eq("is_active", True)
        .order("updated_at", desc=True)
        .limit(200)
        .execute()
    )
    documents = (
        await db.table("documents")
        .select(
            "id,name,doc_type,status,review_status,source_version,valid_until,quality_score,indexed_at,created_at"
        )
        .eq("organization_id", organization_id)
        .in_("status", ["ready", "completed"])
        .order("created_at", desc=True)
        .limit(300)
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
            "documents": documents.data or [],
        }
    )


@router.post("/products", status_code=status.HTTP_201_CREATED)
async def upsert_product_catalog(
    body: ProductCatalogWrite,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    payload = body.model_dump(mode="json")
    payload.update(
        {
            "organization_id": organization_id,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    if body.validation_status == "verified":
        payload.update(
            {"reviewed_by": user_id, "reviewed_at": datetime.now(UTC).isoformat()}
        )
    result = (
        await db.table("instrument_product_catalog")
        .upsert(payload, on_conflict="organization_id,model_code")
        .execute()
    )
    if not result.data:
        raise api_error(ErrorCode.DB_QUERY_ERROR, "保存产品目录失败")
    return api_success(data=result.data[0], message="产品目录已保存")


@router.delete("/products/{product_id}")
async def archive_product_catalog(
    product_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    result = (
        await db.table("instrument_product_catalog")
        .update({"is_active": False, "updated_at": datetime.now(UTC).isoformat()})
        .eq("organization_id", organization_id)
        .eq("id", str(product_id))
        .execute()
    )
    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "产品不存在")
    return api_success(data=result.data[0], message="产品已归档")


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
    products = (
        await db.table("instrument_product_catalog")
        .select(
            "product_name,model_code,currency,list_price,standard_cost,lead_time_days,warranty_months,lifecycle_status,validation_status,compatibility_rules"
        )
        .eq("organization_id", organization_id)
        .eq("is_active", True)
        .limit(500)
        .execute()
    )
    workspace = enrich_workspace_commercials(workspace, products.data or [])
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


@router.post("/projects/{project_id}/extract-requirements")
async def extract_project_requirements(
    project_id: UUID,
    body: RequirementExtractionRequest,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    document_ids = [str(value) for value in body.document_ids]
    documents_result = (
        await db.table("documents")
        .select(
            "id,name,doc_type,status,review_status,source_version,valid_until,quality_score,extracted_data"
        )
        .eq("organization_id", organization_id)
        .in_("id", document_ids)
        .execute()
    )
    documents = documents_result.data or []
    if len(documents) != len(set(document_ids)):
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            "部分资料不存在、尚未完成索引或不属于当前企业",
        )
    workspace = project.get("workspace") or build_initial_workspace(project)
    requirements, extraction = await extract_requirements(
        documents=documents,
        brief={**project, **(workspace.get("brief") or {})},
        user_id=user_id,
        organization_id=organization_id,
    )
    if not body.replace_existing:
        existing = workspace.get("requirements") or []
        existing_titles = {
            str(item.get("title") or "").strip().casefold() for item in existing
        }
        requirements = existing + [
            item
            for item in requirements
            if str(item.get("title") or "").strip().casefold() not in existing_titles
        ]
    extension = dict(workspace.get("extension_data") or {})
    extension["requirement_extraction"] = extraction
    extension["source_documents"] = [
        {
            "id": str(item.get("id")),
            "name": item.get("name"),
            "doc_type": item.get("doc_type"),
            "review_status": item.get("review_status"),
            "source_version": item.get("source_version"),
            "valid_until": item.get("valid_until"),
        }
        for item in documents
    ]
    workspace = {
        **workspace,
        "requirements": requirements,
        "active_stage": "requirements",
        "extension_data": extension,
    }
    workspace["quality"] = validate_workspace(workspace)
    updated = (
        await db.table("solution_projects")
        .update(
            {
                "workspace": workspace,
                "source_document_ids": document_ids,
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
            "extracted_count": len(requirements),
            "degraded": extraction.get("degraded", False),
        },
        message="需求矩阵已生成并保留来源证据",
    )


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
            "instrument_line_code,product_name,model_code,positioning,application_fields,key_specs,knowledge_refs,currency,list_price,standard_cost,lead_time_days,warranty_months,lifecycle_status,validation_status,configuration_schema,compatibility_rules,service_items,consumables,evidence_refs"
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
    evidence_catalog = await vector_service.search_evidence(
        query=query, user_id=user_id, limit=8, org_id=organization_id
    )
    source_document_ids = project.get("source_document_ids") or []
    if source_document_ids:
        source_documents = (
            await db.table("documents")
            .select(
                "id,name,doc_type,review_status,source_version,valid_until,quality_score,extracted_data"
            )
            .eq("organization_id", organization_id)
            .in_("id", source_document_ids)
            .execute()
        )
        explicit_evidence = []
        for document in source_documents.data or []:
            if document.get("review_status") in {"rejected", "expired"}:
                continue
            extracted = document.get("extracted_data") or {}
            excerpt = (
                extracted.get("full_text_context") or extracted.get("summary") or ""
                if isinstance(extracted, dict)
                else str(extracted)
            )
            explicit_evidence.append(
                {
                    "document_id": str(document.get("id")),
                    "title": document.get("name"),
                    "source": document.get("name"),
                    "doc_type": document.get("doc_type"),
                    "excerpt": str(excerpt)[:1200],
                    "score": 1.0,
                    "source_version": document.get("source_version"),
                    "valid_until": document.get("valid_until"),
                    "review_status": document.get("review_status"),
                    "quality_score": document.get("quality_score"),
                }
            )
        explicit_ids = {item["document_id"] for item in explicit_evidence}
        evidence_catalog = explicit_evidence + [
            item
            for item in evidence_catalog
            if item.get("document_id") not in explicit_ids
        ]
    knowledge_context = json.dumps(evidence_catalog, ensure_ascii=False, default=str)
    workspace_extension = dict(workspace.get("extension_data") or {})
    workspace_extension["evidence_catalog"] = evidence_catalog
    workspace = {**workspace, "extension_data": workspace_extension}
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
    output_format: Literal["markdown", "docx", "pdf", "xlsx"] = Query(
        default="docx", alias="format"
    ),
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    quality = validate_workspace(project.get("workspace") or {})
    if not quality["ready_for_external_use"]:
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT, "仍有待核验证据或必选项，暂不能外发"
        )
    safe_name = re_safe_filename(project.get("project_code") or str(project_id))
    brand: dict[str, Any] = {}
    try:
        organization = (
            await db.table("organizations")
            .select("name,brand")
            .eq("id", organization_id)
            .maybe_single()
            .execute()
        )
        if organization.data:
            brand = {
                **(
                    organization.data.get("brand")
                    if isinstance(organization.data.get("brand"), dict)
                    else {}
                ),
                "company_name": organization.data.get("name"),
            }
    except Exception:
        brand = {}
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
    if output_format == "xlsx":
        content = export_xlsx(project)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        suffix = "xlsx"
    else:
        content = export_docx(project, brand=brand)
        media_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        suffix = "docx"
    try:
        await db.table("solution_delivery_events").insert(
            {
                "organization_id": organization_id,
                "project_id": str(project_id),
                "version_number": project.get("current_version"),
                "channel": "download",
                "status": "prepared",
                "artifact_name": f"{safe_name}.{suffix}",
                "artifact_metadata": {"format": suffix},
                "created_by": user_id,
            }
        ).execute()
    except Exception:
        pass
    return Response(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.{suffix}"'},
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
    if body.outcome_type in {"won", "lost"}:
        try:
            await db.table("solution_feedback_events").insert(
                {
                    "organization_id": organization_id,
                    "project_id": str(project_id),
                    "version_number": project.get("current_version"),
                    "change_type": body.outcome_type,
                    "note": body.note,
                    "created_by": user_id,
                }
            ).execute()
        except Exception:
            pass
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


@router.post(
    "/projects/{project_id}/create-tender", status_code=status.HTTP_201_CREATED
)
async def create_tender_from_solution(
    project_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    linked_id = project.get("linked_tender_project_id")
    if linked_id:
        linked = (
            await db.table("bid_project")
            .select("*")
            .eq("tenant_id", organization_id)
            .eq("id", linked_id)
            .maybe_single()
            .execute()
        )
        if linked.data:
            return api_success(data=linked.data, message="已存在关联投标项目")

    workspace = project.get("workspace") or {}
    requirements = workspace.get("requirements") or []
    packages = workspace.get("packages") or []
    recommended = next(
        (item for item in packages if item.get("id") == "recommended"),
        packages[0] if packages else {},
    )
    response_matrix = [
        {
            "id": item.get("id") or f"matrix-{index + 1}",
            "requirement": item.get("title"),
            "priority": item.get("priority"),
            "response": "待编制",
            "compliance": "pending",
            "evidence_ref": item.get("evidence_ref"),
            "source_document_id": item.get("source_document_id"),
        }
        for index, item in enumerate(requirements)
    ]
    tender_workspace = {
        "schema_version": "tender-workspace.v1",
        "active_stage": "matrix",
        "requirements": requirements,
        "response_matrix": response_matrix,
        "draft_sections": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "content": item.get("content"),
                "evidence_refs": item.get("evidence_refs") or [],
                "status": "draft",
            }
            for item in workspace.get("sections") or []
        ],
        "review_gates": [],
        "artifacts": workspace.get("artifacts") or [],
        "extension_data": {
            "source_solution_project_id": str(project_id),
            "source_solution_version": project.get("current_version"),
        },
    }
    now = datetime.now(UTC).isoformat()
    payload = {
        "tenant_id": organization_id,
        "project_code": (
            f"BID-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
        ),
        "project_name": project.get("title"),
        "title": project.get("title"),
        "client_name": project.get("customer_name"),
        "buyer_name": project.get("customer_name"),
        "bid_deadline": project.get("deadline"),
        "deadline": project.get("deadline"),
        "estimated_value": project.get("budget_max"),
        "status": "preparation",
        "compliance_status": "unchecked",
        "instrument_line_code": project.get("instrument_line_code"),
        "application_field": project.get("application_scenario"),
        "target_product_models": recommended.get("product_models") or [],
        "requirements_summary": "\n".join(
            str(item.get("title") or "") for item in requirements[:50]
        ),
        "scoring_matrix": {
            "items": response_matrix,
            "schema_version": "tender-workspace.v1",
        },
        "evidence_refs": [
            item.get("evidence_ref")
            for item in requirements
            if item.get("evidence_ref")
        ],
        "source_solution_project_id": str(project_id),
        "metadata": {"tender_workspace": tender_workspace},
        "created_by": user_id,
        "updated_by": user_id,
        "update_time": now,
    }
    result = await db.table("bid_project").insert(payload).execute()
    if not result.data:
        raise api_error(ErrorCode.DB_QUERY_ERROR, "创建关联投标项目失败")
    tender = result.data[0]
    await db.table("solution_projects").update(
        {
            "linked_tender_project_id": tender.get("id"),
            "updated_by": user_id,
            "updated_at": now,
        }
    ).eq("organization_id", organization_id).eq("id", str(project_id)).execute()
    return api_success(data=tender, message="方案已转为投标项目")


@router.post("/projects/{project_id}/feedback")
async def record_solution_feedback(
    project_id: UUID,
    body: SolutionFeedbackCreate,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    payload = {
        **body.model_dump(mode="json"),
        "organization_id": organization_id,
        "project_id": str(project_id),
        "version_number": project.get("current_version"),
        "created_by": user_id,
    }
    result = await db.table("solution_feedback_events").insert(payload).execute()
    return api_success(
        data=(result.data or [payload])[0], message="反馈已进入方案学习样本"
    )


@router.get("/analytics")
async def get_solution_analytics(
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    projects = (
        await db.table("solution_projects")
        .select("id,status,current_version,workspace,outcome,created_at,updated_at")
        .eq("organization_id", organization_id)
        .limit(1000)
        .execute()
    )
    feedback = (
        await db.table("solution_feedback_events")
        .select("rating,change_type,created_at")
        .eq("organization_id", organization_id)
        .limit(5000)
        .execute()
    )
    deliveries = (
        await db.table("solution_delivery_events")
        .select("channel,status,created_at")
        .eq("organization_id", organization_id)
        .limit(5000)
        .execute()
    )
    return api_success(
        data=solution_value_metrics(
            projects.data or [], feedback.data or [], deliveries.data or []
        )
    )


@router.get("/connectors")
async def list_solution_connectors(
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    result = (
        await db.table("enterprise_connector_registry")
        .select(
            "id,connector_code,display_name,connector_type,status,capabilities,last_health_at,updated_at"
        )
        .eq("organization_id", organization_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return api_success(data={"connectors": result.data or []})


@router.put("/connectors/{connector_code}")
async def save_solution_connector(
    connector_code: str,
    body: ConnectorWrite,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    if connector_code != body.connector_code:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "连接器编码不一致")
    payload = {
        **body.model_dump(mode="json"),
        "organization_id": organization_id,
        "created_by": user_id,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    result = (
        await db.table("enterprise_connector_registry")
        .upsert(payload, on_conflict="organization_id,connector_code")
        .execute()
    )
    return api_success(data=(result.data or [payload])[0], message="连接器配置已保存")
