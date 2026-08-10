"""Quality platform APIs: golden templates, SLO, failure modes, monthly report
and the learning-feedback endpoints for generated artifacts."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import ErrorCode, api_error, api_success
from app.services.artifact_feedback_loop import (
    record_customer_outcome,
    record_learning_candidate,
    summarize_failure_modes,
)
from app.services.artifact_quality_slo import build_monthly_report, evaluate_slo
from app.services.artifact_template_service import (
    get_optimal_template,
    list_templates,
    record_template_usage,
    save_template,
)

router = APIRouter(prefix="/api/artifact-quality", tags=["Artifact Quality"])


class TemplateSaveRequest(BaseModel):
    template_key: str = Field(min_length=2, max_length=120)
    artifact_type: str = Field(min_length=2, max_length=60)
    title: str = Field(min_length=2, max_length=300)
    sections: list[str] = Field(default_factory=list, max_length=30)
    content_markdown: str = Field(default="", max_length=20000)
    instrument_line: str | None = Field(default=None, max_length=60)
    industry: str | None = Field(default=None, max_length=60)
    version: str = Field(default="1.0.0", max_length=30)
    status: Literal["active", "draft", "archived"] = "active"


class TemplateUsageRequest(BaseModel):
    template_key: str = Field(min_length=2, max_length=120)
    quality: dict[str, Any] = Field(default_factory=dict)


class LearningCandidateRequest(BaseModel):
    artifact_id: str
    artifact_version_id: str
    change_type: Literal["accepted", "edited", "rejected", "won", "lost", "other"]
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)
    original_content: str | None = None
    revised_content: str | None = None
    quality_before: dict[str, Any] = Field(default_factory=dict)
    quality_after: dict[str, Any] = Field(default_factory=dict)
    evidence_fingerprint: str | None = None


class CustomerOutcomeRequest(BaseModel):
    artifact_id: str
    artifact_version_id: str
    outcome: Literal["used", "edited", "discarded", "won", "lost"]
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


@router.get("/slo")
async def get_quality_slo(
    days: int = Query(default=30, ge=1, le=180),
    request_db: Any = Depends(get_request_db),
    org_id: str = Depends(get_current_org_id),
):
    result = await evaluate_slo(request_db, organization_id=org_id, days=days)
    return api_success(result)


@router.get("/monthly-report")
async def get_monthly_report(
    year: int = Query(ge=2024, le=2100),
    month: int = Query(ge=1, le=12),
    request_db: Any = Depends(get_request_db),
    org_id: str = Depends(get_current_org_id),
):
    result = await build_monthly_report(
        request_db, organization_id=org_id, year=year, month=month
    )
    if not result.get("available"):
        return api_success(result, message="该月份暂无质量事件")
    return api_success(result)


@router.get("/failure-modes")
async def get_failure_modes(
    days: int = Query(default=30, ge=1, le=180),
    request_db: Any = Depends(get_request_db),
    org_id: str = Depends(get_current_org_id),
):
    result = await summarize_failure_modes(
        request_db, organization_id=org_id, days=days
    )
    return api_success(result)


@router.get("/templates")
async def get_templates(
    artifact_type: str | None = Query(default=None),
    instrument_line: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    request_db: Any = Depends(get_request_db),
    org_id: str = Depends(get_current_org_id),
):
    result = await list_templates(
        request_db,
        organization_id=org_id,
        artifact_type=artifact_type,
        instrument_line=instrument_line,
        industry=industry,
    )
    return api_success(result)


@router.get("/templates/optimal")
async def get_optimal(
    artifact_type: str = Query(min_length=2),
    instrument_line: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    request_db: Any = Depends(get_request_db),
    org_id: str = Depends(get_current_org_id),
):
    template = await get_optimal_template(
        request_db,
        organization_id=org_id,
        artifact_type=artifact_type,
        instrument_line=instrument_line,
        industry=industry,
    )
    if not template:
        return api_success({"template": None}, message="未找到匹配模板")
    return api_success({"template": template})


@router.post("/templates")
async def create_template(
    body: TemplateSaveRequest,
    request_db: Any = Depends(get_request_db),
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    result = await save_template(
        request_db,
        organization_id=org_id,
        user_id=user_id,
        template_key=body.template_key,
        artifact_type=body.artifact_type,
        title=body.title,
        sections=body.sections,
        content_markdown=body.content_markdown,
        instrument_line=body.instrument_line,
        industry=body.industry,
        version=body.version,
        status=body.status,
    )
    if not result.get("ok"):
        raise api_error(
            ErrorCode.DB_QUERY_ERROR, message=result.get("error", "保存模板失败")
        )
    return api_success(result.get("template"), message="模板已保存")


@router.post("/templates/usage")
async def post_template_usage(
    body: TemplateUsageRequest,
    request_db: Any = Depends(get_request_db),
    org_id: str = Depends(get_current_org_id),
):
    result = await record_template_usage(
        request_db,
        organization_id=org_id,
        template_key=body.template_key,
        quality=body.quality,
    )
    if not result.get("ok"):
        return api_success({"ok": False}, message=result.get("error", "未记录"))
    return api_success(result.get("metrics"), message="模板指标已更新")


@router.post("/learning-candidates")
async def post_learning_candidate(
    body: LearningCandidateRequest,
    request_db: Any = Depends(get_request_db),
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    result = await record_learning_candidate(
        request_db,
        organization_id=org_id,
        user_id=user_id,
        artifact_id=body.artifact_id,
        artifact_version_id=body.artifact_version_id,
        change_type=body.change_type,
        rating=body.rating,
        comment=body.comment,
        original_content=body.original_content,
        revised_content=body.revised_content,
        quality_before=body.quality_before,
        quality_after=body.quality_after,
        evidence_fingerprint=body.evidence_fingerprint,
    )
    return api_success(result, message="反馈已进入学习队列")


@router.post("/outcomes")
async def post_customer_outcome(
    body: CustomerOutcomeRequest,
    request_db: Any = Depends(get_request_db),
    org_id: str = Depends(get_current_org_id),
    user_id: str = Depends(get_current_user_id),
):
    result = await record_customer_outcome(
        request_db,
        organization_id=org_id,
        user_id=user_id,
        artifact_id=body.artifact_id,
        artifact_version_id=body.artifact_version_id,
        outcome=body.outcome,
        rating=body.rating,
        comment=body.comment,
    )
    if not result.get("ok"):
        raise api_error(
            ErrorCode.DB_QUERY_ERROR, message=result.get("error", "记录失败")
        )
    return api_success(result, message="客户结果已回流")
