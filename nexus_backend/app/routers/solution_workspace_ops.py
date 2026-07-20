"""Operational APIs for CPQ, review, evaluation and solution delivery."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_current_user_role, get_request_db, require_role
from app.core.errors import ErrorCode, api_error, api_success
from app.routers.solution_workspace import _get_project
from app.services.audit_logger import audit_logger
from app.services.solution_connector_service import deliver_solution_payload
from app.services.solution_cpq_service import build_workspace_quotes
from app.services.solution_editor_service import rewrite_solution_section
from app.services.solution_learning_service import build_learning_insights
from app.services.solution_quality_eval_service import evaluate_solution
from app.services.solution_scenario_catalog import list_scenario_packs
from app.services.solution_tender_service import build_tender_readiness

router = APIRouter(prefix="/api/solution-workspace", tags=["Solution Operations"])

require_catalog_admin = require_role(["admin", "founder", "boss"])
require_commercial_approver = require_role(["admin", "founder", "boss"])
require_solution_manager = require_role(["manager", "admin", "founder", "boss"])


class CPQPreviewRequest(BaseModel):
    workspace: dict[str, Any] | None = None
    price_book_id: UUID | None = None
    tax_rate: float | None = Field(default=None, ge=0, le=1)


class CommercialApprovalCreate(BaseModel):
    package_id: str = Field(min_length=1, max_length=120)
    workspace: dict[str, Any] | None = None
    price_book_id: UUID | None = None
    tax_rate: float | None = Field(default=None, ge=0, le=1)
    reason: str = Field(min_length=2, max_length=1000)


class CommercialApprovalDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class ReviewCommentCreate(BaseModel):
    section_id: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=4000)


class SectionRewriteRequest(BaseModel):
    section_id: str = Field(min_length=1, max_length=120)
    mode: Literal["concise", "technical", "executive", "proofread"] = "proofread"
    instruction: str = Field(
        default="保持事实与证据不变，提升表达质量", max_length=1000
    )


class ConnectorDeliveryRequest(BaseModel):
    connector_code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,79}$")
    request_key: str = Field(min_length=8, max_length=160)


class PriceBookWrite(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    currency: str = Field(default="CNY", max_length=10)
    tax_rate: float = Field(default=0, ge=0, le=1)
    is_default: bool = False
    status: Literal["draft", "active", "archived"] = "active"


class PriceBookItemWrite(BaseModel):
    unit_price: float = Field(ge=0)
    floor_price: float | None = Field(default=None, ge=0)
    max_discount_percent: float = Field(default=0, ge=0, le=100)
    minimum_margin_percent: float | None = Field(default=None, ge=-100, le=100)


async def _audit(
    action: str,
    *,
    user_id: str,
    organization_id: str,
    project_id: str | None = None,
    target_table: str = "solution_projects",
    details: dict[str, Any] | None = None,
) -> None:
    await audit_logger.log(
        action=action,
        actor_user_id=user_id,
        org_id=organization_id,
        target_id=project_id,
        target_table=target_table,
        details=details or {},
    )
    await audit_logger.force_flush()


async def _build_cpq_preview(
    db,
    organization_id: str,
    workspace: dict[str, Any],
    *,
    price_book_id: UUID | None = None,
    tax_rate: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Build a canonical quote from tenant-owned catalog and pricing data."""
    products_result = (
        await db.table("instrument_product_catalog")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("is_active", True)
        .limit(500)
        .execute()
    )
    price_book_query = (
        db.table("solution_price_books")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("status", "active")
    )
    if price_book_id:
        price_book_query = price_book_query.eq("id", str(price_book_id))
    else:
        price_book_query = price_book_query.eq("is_default", True)
    price_book_result = await price_book_query.maybe_single().execute()
    price_book = price_book_result.data

    items: list[dict[str, Any]] = []
    if price_book:
        item_result = (
            await db.table("solution_price_book_items")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("price_book_id", price_book["id"])
            .execute()
        )
        products_by_id = {
            str(item.get("id")): item for item in products_result.data or []
        }
        items = [
            {
                **item,
                "model_code": (
                    products_by_id.get(str(item.get("product_id"))) or {}
                ).get("model_code"),
            }
            for item in item_result.data or []
        ]
    quote = build_workspace_quotes(
        workspace,
        products_result.data or [],
        price_book_items=items,
        tax_rate=(
            tax_rate
            if tax_rate is not None
            else float((price_book or {}).get("tax_rate") or 0)
        ),
    )
    return quote, price_book


def _is_unique_violation(exc: Exception) -> bool:
    return str(getattr(exc, "code", "")) == "23505" or "23505" in str(exc)


def _shape_approval_for_role(approval: dict[str, Any], role: str) -> dict[str, Any]:
    if role in {"manager", "admin", "founder", "boss"}:
        return approval
    shaped = dict(approval)
    quote = dict(shaped.get("quote_snapshot") or {})
    quote.pop("gross_margin_percent", None)
    shaped["quote_snapshot"] = quote
    return shaped


@router.get("/scenario-packs")
async def scenario_packs(_user_id: str = Depends(get_current_user_id)):
    return api_success(data={"packs": list_scenario_packs()})


@router.get("/product-catalog-admin")
async def product_catalog_admin(
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _admin_id: str = Depends(require_catalog_admin),
):
    result = (
        await db.table("instrument_product_catalog")
        .select("*")
        .eq("organization_id", organization_id)
        .order("updated_at", desc=True)
        .limit(500)
        .execute()
    )
    return api_success(data={"products": result.data or []})


@router.get("/price-books")
async def list_price_books(
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    result = (
        await db.table("solution_price_books")
        .select(
            "id,name,region,currency,tax_rate,is_default,status,valid_from,valid_until"
        )
        .eq("organization_id", organization_id)
        .neq("status", "archived")
        .order("is_default", desc=True)
        .execute()
    )
    return api_success(data={"price_books": result.data or []})


@router.post("/price-books", status_code=status.HTTP_201_CREATED)
async def save_price_book(
    body: PriceBookWrite,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    admin_id: str = Depends(require_catalog_admin),
):
    if body.is_default:
        await db.table("solution_price_books").update({"is_default": False}).eq(
            "organization_id", organization_id
        ).eq("is_default", True).execute()
    payload = {
        **body.model_dump(mode="json"),
        "organization_id": organization_id,
        "created_by": admin_id,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    result = (
        await db.table("solution_price_books")
        .upsert(payload, on_conflict="organization_id,name")
        .execute()
    )
    await _audit(
        "solution.price_book.save",
        user_id=admin_id,
        organization_id=organization_id,
        target_table="solution_price_books",
        details={"name": body.name, "region": body.region},
    )
    return api_success(data=(result.data or [{}])[0], message="价格册已保存")


@router.get("/price-books/{price_book_id}/items")
async def list_price_book_items(
    price_book_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _admin_id: str = Depends(require_catalog_admin),
):
    price_book = (
        await db.table("solution_price_books")
        .select("id")
        .eq("organization_id", organization_id)
        .eq("id", str(price_book_id))
        .neq("status", "archived")
        .maybe_single()
        .execute()
    )
    if not price_book.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "价格册不存在")
    result = (
        await db.table("solution_price_book_items")
        .select(
            "id,price_book_id,product_id,unit_price,floor_price,"
            "max_discount_percent,minimum_margin_percent,updated_at"
        )
        .eq("organization_id", organization_id)
        .eq("price_book_id", str(price_book_id))
        .order("updated_at", desc=True)
        .execute()
    )
    return api_success(data={"items": result.data or []})


@router.put("/price-books/{price_book_id}/items/{product_id}")
async def save_price_book_item(
    price_book_id: UUID,
    product_id: UUID,
    body: PriceBookItemWrite,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    admin_id: str = Depends(require_catalog_admin),
):
    if body.floor_price is not None and body.floor_price > body.unit_price:
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            "价格底线不能高于销售单价",
        )
    price_book = (
        await db.table("solution_price_books")
        .select("id")
        .eq("organization_id", organization_id)
        .eq("id", str(price_book_id))
        .neq("status", "archived")
        .maybe_single()
        .execute()
    )
    product = (
        await db.table("instrument_product_catalog")
        .select("id,model_code")
        .eq("organization_id", organization_id)
        .eq("id", str(product_id))
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not price_book.data or not product.data:
        raise api_error(
            ErrorCode.RESOURCE_NOT_FOUND,
            "价格册或产品不存在于当前企业",
        )
    payload = {
        **body.model_dump(mode="json"),
        "organization_id": organization_id,
        "price_book_id": str(price_book_id),
        "product_id": str(product_id),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    result = (
        await db.table("solution_price_book_items")
        .upsert(payload, on_conflict="price_book_id,product_id")
        .execute()
    )
    await _audit(
        "solution.price_book_item.save",
        user_id=admin_id,
        organization_id=organization_id,
        target_table="solution_price_book_items",
        details={
            "price_book_id": str(price_book_id),
            "product_id": str(product_id),
            "model_code": product.data.get("model_code"),
        },
    )
    return api_success(data=(result.data or [{}])[0], message="产品价格已保存")


@router.post("/projects/{project_id}/cpq-preview")
async def preview_cpq(
    project_id: UUID,
    body: CPQPreviewRequest,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    role: str = Depends(get_current_user_role),
):
    project = await _get_project(db, organization_id, project_id)
    workspace = body.workspace or project.get("workspace") or {}
    quote, price_book = await _build_cpq_preview(
        db,
        organization_id,
        workspace,
        price_book_id=body.price_book_id,
        tax_rate=(body.tax_rate if body.tax_rate is not None else None),
    )
    if role not in {"manager", "admin", "founder", "boss"}:
        for package_quote in quote["quotes"]:
            package_quote.pop("gross_margin_percent", None)
    return api_success(data={**quote, "price_book": price_book})


@router.post(
    "/projects/{project_id}/commercial-approvals", status_code=status.HTTP_201_CREATED
)
async def request_commercial_approval(
    project_id: UUID,
    body: CommercialApprovalCreate,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
    role: str = Depends(get_current_user_role),
):
    project = await _get_project(db, organization_id, project_id)
    workspace = body.workspace or project.get("workspace") or {}
    packages = workspace.get("packages") or []
    if not any(item.get("id") == body.package_id for item in packages):
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "待审批方案档位不存在")
    cpq, price_book = await _build_cpq_preview(
        db,
        organization_id,
        workspace,
        price_book_id=body.price_book_id,
        tax_rate=body.tax_rate,
    )
    canonical_quote = next(
        (item for item in cpq["quotes"] if item.get("package_id") == body.package_id),
        None,
    )
    if not canonical_quote or not canonical_quote.get("valid"):
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "报价数据未通过后端核验")
    if not canonical_quote.get("approval_required"):
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "该报价无需商业例外审批")
    existing = (
        await db.table("solution_commercial_approvals")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("project_id", str(project_id))
        .eq("package_id", body.package_id)
        .eq("status", "pending")
        .maybe_single()
        .execute()
    )
    if existing.data:
        return api_success(
            data=_shape_approval_for_role(existing.data, role),
            message="该方案已有待处理商业审批",
        )
    result = (
        await db.table("solution_commercial_approvals")
        .insert(
            {
                "organization_id": organization_id,
                "project_id": str(project_id),
                "package_id": body.package_id,
                "quote_snapshot": {
                    **canonical_quote,
                    "price_book_id": (price_book or {}).get("id"),
                    "calculated_at": datetime.now(UTC).isoformat(),
                },
                "reason": "；".join(canonical_quote.get("approval_reasons") or [])
                or body.reason,
                "requested_by": user_id,
            }
        )
        .execute()
    )
    await _audit(
        "solution.commercial_approval.request",
        user_id=user_id,
        organization_id=organization_id,
        project_id=str(project_id),
        target_table="solution_commercial_approvals",
        details={
            "package_id": body.package_id,
            "reason": canonical_quote.get("approval_reasons"),
        },
    )
    approval = _shape_approval_for_role((result.data or [{}])[0], role)
    return api_success(data=approval, message="商业例外已提交审批")


@router.get("/projects/{project_id}/commercial-approvals")
async def list_commercial_approvals(
    project_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
    role: str = Depends(get_current_user_role),
):
    await _get_project(db, organization_id, project_id)
    result = (
        await db.table("solution_commercial_approvals")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("project_id", str(project_id))
        .order("requested_at", desc=True)
        .execute()
    )
    return api_success(
        data={
            "approvals": [
                _shape_approval_for_role(item, role) for item in result.data or []
            ]
        }
    )


@router.post("/commercial-approvals/{approval_id}/decision")
async def decide_commercial_approval(
    approval_id: UUID,
    body: CommercialApprovalDecision,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    approver_id: str = Depends(require_commercial_approver),
):
    result = (
        await db.table("solution_commercial_approvals")
        .update(
            {
                "status": body.decision,
                "decision_note": body.note,
                "decided_by": approver_id,
                "decided_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("organization_id", organization_id)
        .eq("id", str(approval_id))
        .eq("status", "pending")
        .execute()
    )
    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "待审批记录不存在或已处理")
    await _audit(
        "solution.commercial_approval.decide",
        user_id=approver_id,
        organization_id=organization_id,
        project_id=str(result.data[0].get("project_id") or ""),
        target_table="solution_commercial_approvals",
        details={"decision": body.decision, "note": body.note},
    )
    return api_success(data=result.data[0], message="商业审批已处理")


@router.get("/projects/{project_id}/comments")
async def list_review_comments(
    project_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    await _get_project(db, organization_id, project_id)
    result = (
        await db.table("solution_review_comments")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("project_id", str(project_id))
        .order("created_at", desc=False)
        .execute()
    )
    return api_success(data={"comments": result.data or []})


@router.get("/projects/{project_id}/versions/{version_number}")
async def get_solution_version(
    project_id: UUID,
    version_number: int,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    await _get_project(db, organization_id, project_id)
    result = (
        await db.table("solution_versions")
        .select(
            "id,version_number,title,content,evidence_refs,generation_metadata,review_status,created_at"
        )
        .eq("organization_id", organization_id)
        .eq("project_id", str(project_id))
        .eq("version_number", version_number)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "方案版本不存在")
    return api_success(data=result.data)


@router.post("/projects/{project_id}/comments", status_code=status.HTTP_201_CREATED)
async def create_review_comment(
    project_id: UUID,
    body: ReviewCommentCreate,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    result = (
        await db.table("solution_review_comments")
        .insert(
            {
                "organization_id": organization_id,
                "project_id": str(project_id),
                "version_number": project.get("current_version"),
                "section_id": body.section_id,
                "content": body.content,
                "created_by": user_id,
            }
        )
        .execute()
    )
    return api_success(data=(result.data or [{}])[0], message="评审意见已添加")


@router.post("/projects/{project_id}/comments/{comment_id}/resolve")
async def resolve_review_comment(
    project_id: UUID,
    comment_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    await _get_project(db, organization_id, project_id)
    result = (
        await db.table("solution_review_comments")
        .update(
            {
                "status": "resolved",
                "resolved_by": user_id,
                "resolved_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("organization_id", organization_id)
        .eq("project_id", str(project_id))
        .eq("id", str(comment_id))
        .execute()
    )
    if not result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "评审意见不存在")
    return api_success(data=result.data[0], message="评审意见已解决")


@router.post("/projects/{project_id}/rewrite-section")
async def rewrite_section(
    project_id: UUID,
    body: SectionRewriteRequest,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    workspace = project.get("workspace") or {}
    section = next(
        (
            item
            for item in workspace.get("sections") or []
            if item.get("id") == body.section_id
        ),
        None,
    )
    if not section:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "方案章节不存在")
    try:
        result = await rewrite_solution_section(
            section=section,
            instruction=body.instruction,
            mode=body.mode,
            evidence_catalog=(workspace.get("extension_data") or {}).get(
                "evidence_catalog"
            )
            or [],
            user_id=user_id,
            organization_id=organization_id,
        )
    except RuntimeError as exc:
        raise api_error(ErrorCode.AI_SERVICE_UNAVAILABLE, str(exc))
    await _audit(
        "solution.section.rewrite",
        user_id=user_id,
        organization_id=organization_id,
        project_id=str(project_id),
        details={
            "section_id": body.section_id,
            "mode": body.mode,
            "usage": result.get("usage"),
        },
    )
    return api_success(data=result, message="改写建议已生成，确认后才会应用")


@router.post("/projects/{project_id}/evaluate")
async def evaluate_project_solution(
    project_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    evaluation = evaluate_solution(project.get("workspace") or {})
    await db.table("solution_quality_eval_runs").insert(
        {
            "organization_id": organization_id,
            "project_id": str(project_id),
            "version_number": project.get("current_version"),
            "evaluator_version": evaluation["evaluator_version"],
            "score": evaluation["score"],
            "dimensions": evaluation["dimensions"],
            "findings": evaluation["findings"],
            "created_by": user_id,
        }
    ).execute()
    await db.table("solution_projects").update({"quality_evaluation": evaluation}).eq(
        "organization_id", organization_id
    ).eq("id", str(project_id)).execute()
    return api_success(data=evaluation, message="方案质量评测已完成")


@router.get("/projects/{project_id}/tender-readiness")
async def tender_readiness(
    project_id: UUID,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    project = await _get_project(db, organization_id, project_id)
    readiness = build_tender_readiness(project)
    await db.table("solution_projects").update({"bid_readiness": readiness}).eq(
        "organization_id", organization_id
    ).eq("id", str(project_id)).execute()
    return api_success(data=readiness)


@router.get("/learning-insights")
async def learning_insights(
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _manager_id: str = Depends(require_solution_manager),
):
    projects = (
        await db.table("solution_projects")
        .select("id,status,instrument_line_code,industry,workspace")
        .eq("organization_id", organization_id)
        .limit(1000)
        .execute()
    )
    feedback = (
        await db.table("solution_feedback_events")
        .select("section_id,change_type,rating,note")
        .eq("organization_id", organization_id)
        .limit(2000)
        .execute()
    )
    return api_success(
        data=build_learning_insights(projects.data or [], feedback.data or [])
    )


@router.post("/projects/{project_id}/deliver")
async def deliver_project(
    project_id: UUID,
    body: ConnectorDeliveryRequest,
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    manager_id: str = Depends(require_solution_manager),
):
    project = await _get_project(db, organization_id, project_id)
    duplicate = (
        await db.table("solution_delivery_events")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("request_key", body.request_key)
        .maybe_single()
        .execute()
    )
    if duplicate.data:
        return api_success(data=duplicate.data, message="该交付请求已处理")
    connector_result = (
        await db.table("enterprise_connector_registry")
        .select("*")
        .eq("organization_id", organization_id)
        .eq("connector_code", body.connector_code)
        .maybe_single()
        .execute()
    )
    if not connector_result.data:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "连接器不存在")
    quality = evaluate_solution(project.get("workspace") or {})
    if not quality["ready"]:
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT, "方案质量门禁未通过，暂不能外发"
        )
    reservation_payload = {
        "organization_id": organization_id,
        "project_id": str(project_id),
        "version_number": project.get("current_version"),
        "channel": connector_result.data.get("connector_type") or "custom",
        "status": "prepared",
        "artifact_name": project.get("title"),
        "artifact_metadata": {
            "connector_code": body.connector_code,
            "delivery_state": "reserved",
        },
        "request_key": body.request_key,
        "created_by": manager_id,
    }
    try:
        await db.table("solution_delivery_events").insert(reservation_payload).execute()
    except Exception as exc:
        if not _is_unique_violation(exc):
            raise
        duplicate = (
            await db.table("solution_delivery_events")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("request_key", body.request_key)
            .maybe_single()
            .execute()
        )
        return api_success(data=duplicate.data or {}, message="该交付请求已受理")
    try:
        delivery = await deliver_solution_payload(
            connector_result.data,
            {
                "event": "solution.ready",
                "project": {
                    "id": str(project_id),
                    "project_code": project.get("project_code"),
                    "title": project.get("title"),
                    "customer_name": project.get("customer_name"),
                    "status": project.get("status"),
                    "version": project.get("current_version"),
                },
                "workspace": project.get("workspace") or {},
            },
        )
        event_status = "sent"
    except (ValueError, httpx.HTTPError) as exc:
        delivery = {"ok": False, "error": str(exc)}
        event_status = "failed"
    event = (
        await db.table("solution_delivery_events")
        .update(
            {
                "status": event_status,
                "artifact_metadata": {
                    "connector_code": body.connector_code,
                    **delivery,
                },
            }
        )
        .eq("organization_id", organization_id)
        .eq("request_key", body.request_key)
        .execute()
    )
    await _audit(
        "solution.connector.deliver",
        user_id=manager_id,
        organization_id=organization_id,
        project_id=str(project_id),
        target_table="solution_delivery_events",
        details={"connector_code": body.connector_code, "status": event_status},
    )
    if event_status == "failed":
        raise api_error(ErrorCode.INTEGRATION_CONNECT_FAILED, delivery["error"])
    return api_success(data=(event.data or [{}])[0], message="方案已交付到企业连接器")
