"""
Item 12: Workflow Template Marketplace API

Endpoints for browsing, previewing, and creating workflows from templates.
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.workflow_template_service import workflow_template_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflow-templates", tags=["Workflow Templates"])


# ─── Request Models ──────────────────────────────────────────


class CreateFromTemplateBody(BaseModel):
    name: str | None = Field(None, max_length=200, description="自定义工作流名称")


# ─── Endpoints ───────────────────────────────────────────────


@router.get("")
async def list_templates(
    request: Request,
    category: str | None = None,
    user_id: str = Depends(get_current_user_id),
):
    """列出所有可用模板（内置 + 组织共享）"""
    try:
        org_id = getattr(request.state, "org_id", None)
        db = getattr(request.state, "db", None)

        templates = await workflow_template_service.list_templates(
            category=category,
            org_id=org_id,
            db=db,
        )

        categories = workflow_template_service.get_categories()

        return api_success(
            data={"templates": templates, "categories": categories},
            message="模板列表获取成功",
        )
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error listing templates: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/{template_id}")
async def get_template(
    request: Request,
    template_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """获取模板详情"""
    try:
        db = getattr(request.state, "db", None)

        template = await workflow_template_service.get_template(
            template_id=template_id,
            db=db,
        )
        if not template:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "模板不存在")

        return api_success(data=template)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting template {template_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/create-from/{template_id}")
async def create_from_template(
    request: Request,
    template_id: str,
    body: CreateFromTemplateBody = CreateFromTemplateBody(),
    user_id: str = Depends(get_current_user_id),
):
    """从模板创建新的工作流"""
    try:
        org_id = getattr(request.state, "org_id", None)
        db = getattr(request.state, "db", None)

        if not org_id:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "需要组织上下文")

        workflow = await workflow_template_service.create_workflow_from_template(
            template_id=template_id,
            org_id=org_id,
            name=body.name,
            created_by=user_id,
            db=db,
        )

        return api_success(data=workflow, message="工作流已从模板创建")
    except ValueError as e:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, str(e))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error creating from template {template_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/share/{workflow_id}")
async def share_as_template(
    request: Request,
    workflow_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """将现有工作流分享为组织模板"""
    try:
        org_id = getattr(request.state, "org_id", None)
        db = getattr(request.state, "db", None)

        if not org_id:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "需要组织上下文")

        template = await workflow_template_service.share_workflow_as_template(
            workflow_id=workflow_id,
            org_id=org_id,
            shared_by=user_id,
            db=db,
        )

        return api_success(data=template, message="工作流已分享为模板")
    except ValueError as e:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, str(e))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error sharing workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
