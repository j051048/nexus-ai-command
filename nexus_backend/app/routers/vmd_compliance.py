"""VMD Compliance API - Content compliance checking and rule management endpoints."""

import logging
import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_list, api_success
from app.services.compliance_service import compliance_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vmd/compliance", tags=["VMD Compliance"])


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------


class CheckContentRequest(BaseModel):
    content: str = Field(..., min_length=1, description="待检查内容")
    categories: list[str] | None = Field(None, description="规则分类过滤(advertising/security/bid/industry)")
    use_llm: bool = Field(False, description="是否启用LLM深度分析")


class CreateRuleRequest(BaseModel):
    rule_code: str = Field(..., min_length=1, max_length=100, description="规则编码")
    rule_name: str = Field(..., min_length=1, max_length=200, description="规则名称")
    category: str = Field(..., min_length=1, max_length=50, description="分类")
    severity: str = Field("medium", description="严重程度: low/medium/high")
    check_type: str = Field("regex", description="检查类型: regex/keyword/llm")
    pattern: str = Field(..., min_length=1, description="匹配模式(正则或关键词)")
    description: str | None = Field(None, max_length=1000, description="规则描述")
    replacement_suggestion: str | None = Field(None, max_length=1000, description="替换建议")


class UpdateRuleRequest(BaseModel):
    rule_name: str | None = Field(None, max_length=200)
    category: str | None = Field(None, max_length=50)
    severity: str | None = None
    check_type: str | None = None
    pattern: str | None = None
    description: str | None = Field(None, max_length=1000)
    replacement_suggestion: str | None = Field(None, max_length=1000)


# ---------------------------------------------------------------------------
# Compliance check endpoint
# ---------------------------------------------------------------------------


@router.post("/check")
async def check_content(
    body: CheckContentRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """对提供的内容执行合规检查"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        client = getattr(req.state, "db", None)
        if not client:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Run compliance check via service
        result = await compliance_service.check_content(
            content=body.content,
            tenant_id=org_id,
            categories=body.categories,
            enable_llm=body.use_llm,
        )

        # Log to compliance_check_log table
        try:
            log_record = {
                "id": str(uuid.uuid4()),
                "tenant_id": org_id,
                "user_id": user_id,
                "content_snippet": body.content[:500] if body.content else "",
                "content_type": "text",
                "categories": body.categories,
                "use_llm": body.use_llm,
                "status": "compliant" if result.is_compliant else "non_compliant",
                "total_issues": result.total_issues,
                "error_count": result.errors,
                "warning_count": result.warnings,
                "high_issues": result.errors,
                "medium_issues": result.warnings,
                "low_issues": result.total_issues - result.errors - result.warnings,
                "checked_at": datetime.now(UTC).isoformat(),
            }
            await client.table("compliance_check_log").insert(log_record).execute()
        except Exception as log_err:
            logger.warning(f"Failed to log compliance check: {log_err}")

        return api_success(data={"result": asdict(result)}, message="合规检查完成")
    except Exception as e:
        logger.error(f"Compliance check error: user={user_id} err={e}")
        raise api_error(ErrorCode.COMPLIANCE_CHECK_FAILED, "VMD合规操作失败")


# ---------------------------------------------------------------------------
# Compliance rule CRUD endpoints
# ---------------------------------------------------------------------------


@router.get("/rules")
async def list_rules(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    category: str | None = Query(None, description="按分类筛选"),
):
    """获取合规规则列表"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        client = getattr(req.state, "db", None)
        if not client:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        query = client.table("compliance_rule").select("*").eq("tenant_id", org_id).order("create_time", desc=True)
        if category:
            query = query.eq("category", category)

        res = await query.execute()
        return api_success(data={"rules": res.data or []})
    except Exception as e:
        logger.error(f"List compliance rules error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "VMD合规操作失败")


@router.post("/rules")
async def create_rule(
    body: CreateRuleRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """创建自定义合规规则"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        client = getattr(req.state, "db", None)
        if not client:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        record = {
            "id": str(uuid.uuid4()),
            "tenant_id": org_id,
            "rule_code": body.rule_code,
            "rule_name": body.rule_name,
            "category": body.category,
            "severity": body.severity,
            "check_type": body.check_type,
            "pattern": body.pattern,
            "description": body.description,
            "replacement_suggestion": body.replacement_suggestion,
            "created_by": user_id,
        }

        res = await client.table("compliance_rule").insert(record).execute()
        rule = res.data[0] if res.data else record
        return api_success(data={"rule": rule}, message="合规规则创建成功")
    except Exception as e:
        logger.error(f"Create compliance rule error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "VMD合规操作失败")


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    body: UpdateRuleRequest,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """更新合规规则"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        update_data = body.model_dump(exclude_none=True)
        if not update_data:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "无更新内容")

        update_data["updated_by"] = user_id

        res = await client.table("compliance_rule").update(update_data).eq("id", rule_id).execute()
        if not res.data:
            raise api_error(ErrorCode.COMPLIANCE_RULE_NOT_FOUND, "合规规则不存在")

        return api_success(data={"rule": res.data[0]}, message="合规规则已更新")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "VMD合规参数校验失败")
    except Exception as e:
        logger.error(f"Update compliance rule error: id={rule_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "VMD合规操作失败")


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    req: Request,
    user_id: str = Depends(require_role(["admin", "founder", "boss"])),
):
    """删除合规规则"""
    try:
        client = getattr(req.state, "db", None)
        if not client:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        res = await client.table("compliance_rule").delete().eq("id", rule_id).execute()
        if not res.data:
            raise api_error(ErrorCode.COMPLIANCE_RULE_NOT_FOUND, "合规规则不存在")

        return api_success(None, message="合规规则已删除")
    except Exception as e:
        logger.error(f"Delete compliance rule error: id={rule_id} user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "VMD合规操作失败")


# ---------------------------------------------------------------------------
# Compliance check history endpoint
# ---------------------------------------------------------------------------


@router.get("/history")
async def get_check_history(
    req: Request,
    user_id: str = Depends(get_current_user_id),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    content_type: str | None = Query(None, description="内容类型筛选"),
):
    """获取合规检查历史记录"""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        client = getattr(req.state, "db", None)
        if not client:
            raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库不可用")

        # Count query
        count_query = client.table("compliance_check_log").select("id", count="exact").eq("tenant_id", org_id)
        if content_type:
            count_query = count_query.eq("content_type", content_type)

        count_res = await count_query.execute()
        total = count_res.count if count_res.count is not None else len(count_res.data or [])

        # Data query
        offset = (page - 1) * page_size
        data_query = (
            client.table("compliance_check_log")
            .select("*")
            .eq("tenant_id", org_id)
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
        )
        if content_type:
            data_query = data_query.eq("content_type", content_type)

        res = await data_query.execute()
        return api_list(items=res.data or [], total=total, page=page, page_size=page_size)
    except Exception as e:
        logger.error(f"Get compliance history error: user={user_id} err={e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "VMD合规操作失败")
