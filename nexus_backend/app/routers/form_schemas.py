"""
Form Schema Management API

Provides CRUD endpoints for custom form schema definitions
and form data validation for the approval workflow.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_success
from app.services.form_schema_service import form_schema_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/form-schemas", tags=["Form Schemas"])


# ============== Pydantic Request Models ==============


class FormSchemaCreate(BaseModel):
    approval_type: str
    name: str
    description: str | None = None
    fields: list[dict[str, Any]]
    layout: dict | None = None


class FormSchemaUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    fields: list[dict[str, Any]] | None = None
    layout: dict | None = None
    is_active: bool | None = None


class FormDataValidateRequest(BaseModel):
    schema_id: str
    form_data: dict[str, Any]


# ============== Endpoints ==============


@router.get("")
async def list_schemas(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """
    List all form schemas for the current organization.
    """
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    try:
        client = getattr(request.state, "db", None)
        schemas = await form_schema_service.list_schemas(org_id, db=client)
        return api_success(data=schemas)
    except Exception as e:
        logger.error(f"Failed to list form schemas: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("")
async def create_schema(
    request: Request,
    body: FormSchemaCreate,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """
    Create a new form schema for an approval type. Requires boss/founder role.

    If an active schema already exists for the same (org, type),
    the old one will be deactivated automatically.
    """
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    try:
        client = getattr(request.state, "db", None)
        schema = await form_schema_service.create_schema(
            org_id=org_id,
            approval_type=body.approval_type,
            name=body.name,
            fields=body.fields,
            description=body.description,
            layout=body.layout,
            created_by=user_id,
            db=client,
        )
        return api_success(data=schema, message="表单 Schema 创建成功")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Failed to create form schema: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/by-type/{approval_type}")
async def get_by_type(
    request: Request,
    approval_type: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get the active form schema for a specific approval type.
    """
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    try:
        client = getattr(request.state, "db", None)
        schema = await form_schema_service.get_schema_for_type(org_id, approval_type, db=client)
        if not schema:
            raise api_error(
                ErrorCode.RESOURCE_NOT_FOUND,
                f"未找到类型 '{approval_type}' 的表单 Schema",
            )
        return api_success(data=schema)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get form schema by type: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/{schema_id}")
async def get_schema(
    request: Request,
    schema_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get a form schema by ID.
    """
    try:
        client = getattr(request.state, "db", None)
        schema = await form_schema_service.get_schema(schema_id, db=client)
        if not schema:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "表单 Schema 不存在")
        return api_success(data=schema)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get form schema: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/{schema_id}")
async def update_schema(
    request: Request,
    schema_id: str,
    body: FormSchemaUpdate,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """
    Update an existing form schema. Requires boss/founder role.

    Version is auto-incremented on each update.
    """
    try:
        client = getattr(request.state, "db", None)
        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "没有需要更新的字段")

        schema = await form_schema_service.update_schema(schema_id, updates, db=client)
        return api_success(data=schema, message="表单 Schema 更新成功")
    except HTTPException:
        raise
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        logger.error(f"Failed to update form schema: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/{schema_id}")
async def delete_schema(
    request: Request,
    schema_id: str,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """
    Delete a form schema by ID. Requires boss/founder role.
    """
    try:
        client = getattr(request.state, "db", None)
        deleted = await form_schema_service.delete_schema(schema_id, db=client)
        if not deleted:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "表单 Schema 不存在")
        return api_success(data={"deleted": True}, message="表单 Schema 已删除")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete form schema: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/validate")
async def validate_data(
    request: Request,
    body: FormDataValidateRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Online validation: validate form data against a schema definition.

    Returns validation result with any errors found.
    """
    try:
        client = getattr(request.state, "db", None)

        # Load the schema
        schema = await form_schema_service.get_schema(body.schema_id, db=client)
        if not schema:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "表单 Schema 不存在")

        schema_fields = schema.get("fields", [])
        errors = form_schema_service.validate_form_data(schema_fields, body.form_data)

        return api_success(
            data={
                "valid": len(errors) == 0,
                "errors": errors,
                "schema_id": body.schema_id,
                "schema_version": schema.get("version", 1),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Form data validation failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
