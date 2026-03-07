"""
Phase 1E: Workflow Management API
Visual workflow designer endpoints for managing approval chains.
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_success
from app.services.workflow_definition_service import (
    VALID_APPROVAL_TYPES,
    workflow_definition_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


# --- Request Body Models ---


class WorkflowCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Workflow name")
    description: str | None = Field(None, max_length=1000)
    applies_to: list[str] = Field(..., min_length=1, description="Approval types this workflow handles")
    steps: list[dict] = Field(..., min_length=1, description="Workflow step definitions (JSONB)")
    conditions: list[dict] | None = Field(None, description="Condition branch rules")
    canvas_layout: dict | None = Field(None, description="Frontend canvas layout data")


class WorkflowUpdateBody(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    applies_to: list[str] | None = None
    steps: list[dict] | None = None
    conditions: list[dict] | None = None
    canvas_layout: dict | None = None


# --- Endpoints ---


@router.get("")
async def list_workflows(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """List all workflow definitions for the current organization."""
    try:
        org_id = getattr(request.state, "org_id", None)
        db = getattr(request.state, "db", None)

        if not org_id:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "Organization context required")

        workflows = await workflow_definition_service.list_workflows(org_id=org_id, db=db)
        return api_success(data=workflows)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error listing workflows: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("")
async def create_workflow(
    request: Request,
    body: WorkflowCreateBody,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """Create a new workflow definition. Requires boss/founder role."""
    try:
        org_id = getattr(request.state, "org_id", None)
        db = getattr(request.state, "db", None)

        if not org_id:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "Organization context required")

        workflow = await workflow_definition_service.create_workflow(
            org_id=org_id,
            name=body.name,
            applies_to=body.applies_to,
            steps=body.steps,
            conditions=body.conditions,
            canvas_layout=body.canvas_layout,
            created_by=user_id,
            db=db,
        )
        return api_success(data=workflow, message="Workflow created")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error creating workflow: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/types")
async def list_approval_types():
    """Return all supported approval types."""
    return api_success(data=sorted(VALID_APPROVAL_TYPES))


@router.get("/{workflow_id}")
async def get_workflow(
    request: Request,
    workflow_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get a single workflow definition by ID."""
    try:
        db = getattr(request.state, "db", None)

        workflow = await workflow_definition_service.get_workflow(workflow_id=workflow_id, db=db)
        if not workflow:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, f"Workflow {workflow_id} not found")

        return api_success(data=workflow)
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.put("/{workflow_id}")
async def update_workflow(
    request: Request,
    workflow_id: str,
    body: WorkflowUpdateBody,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """Update an existing workflow definition. Requires boss/founder role."""
    try:
        db = getattr(request.state, "db", None)

        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            return api_success(data=None, message="No updates provided")

        workflow = await workflow_definition_service.update_workflow(workflow_id=workflow_id, updates=updates, db=db)
        return api_success(data=workflow, message="Workflow updated")
    except ValueError as e:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, str(e))
    except RuntimeError as e:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, str(e))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error updating workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.delete("/{workflow_id}")
async def delete_workflow(
    request: Request,
    workflow_id: str,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """Delete a workflow definition. Requires boss/founder role."""
    try:
        db = getattr(request.state, "db", None)

        deleted = await workflow_definition_service.delete_workflow(workflow_id=workflow_id, db=db)
        if not deleted:
            raise api_error(ErrorCode.RESOURCE_NOT_FOUND, f"Workflow {workflow_id} not found")

        return api_success(data={"deleted": workflow_id}, message="Workflow deleted")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error deleting workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/{workflow_id}/toggle")
async def toggle_workflow(
    request: Request,
    workflow_id: str,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """Toggle the active status of a workflow. Requires boss/founder role."""
    try:
        db = getattr(request.state, "db", None)

        workflow = await workflow_definition_service.toggle_workflow(workflow_id=workflow_id, db=db)
        return api_success(data=workflow, message="Workflow toggled")
    except RuntimeError as e:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, str(e))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error toggling workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/{workflow_id}/set-default")
async def set_default(
    request: Request,
    workflow_id: str,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """Set a workflow as the default for the organization. Requires boss/founder role."""
    try:
        org_id = getattr(request.state, "org_id", None)
        db = getattr(request.state, "db", None)

        if not org_id:
            raise api_error(ErrorCode.VALIDATION_MISSING_FIELD, "Organization context required")

        workflow = await workflow_definition_service.set_default(workflow_id=workflow_id, org_id=org_id, db=db)
        return api_success(data=workflow, message="Workflow set as default")
    except RuntimeError as e:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, str(e))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error setting default workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
