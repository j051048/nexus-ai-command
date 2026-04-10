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
    # Backend native format
    applies_to: list[str] | None = Field(
        None, description="Approval types this workflow handles"
    )
    steps: list[dict] | None = Field(
        None, description="Workflow step definitions (JSONB)"
    )
    conditions: list[dict] | None = Field(None, description="Condition branch rules")
    canvas_layout: dict | None = Field(None, description="Frontend canvas layout data")
    # Frontend format (accepted as alternative)
    approval_type: str | None = Field(
        None, description="Single approval type (frontend format)"
    )
    definition: dict | None = Field(
        None, description="Nested {steps, conditions} (frontend format)"
    )


class WorkflowUpdateBody(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    applies_to: list[str] | None = None
    steps: list[dict] | None = None
    conditions: list[dict] | None = None
    canvas_layout: dict | None = None
    approval_type: str | None = None
    definition: dict | None = None


# --- Format Normalization ---


def _normalize_create_body(
    body: WorkflowCreateBody,
) -> tuple[list[str], list[dict], list[dict] | None]:
    """Transform frontend format to backend format.

    Frontend sends: approval_type (str) + definition ({steps, conditions})
    Backend needs:  applies_to (list[str]) + flat steps + flat conditions

    Returns: (applies_to, steps, conditions)
    """
    # Steps: prefer flat 'steps', fallback to nested 'definition.steps'
    steps = body.steps
    conditions = body.conditions
    if not steps and body.definition:
        steps = body.definition.get("steps", [])
        if conditions is None:
            conditions = body.definition.get("conditions")

    if not steps:
        raise ValueError(
            "Workflow must contain steps (either as 'steps' or 'definition.steps')"
        )

    # Applies_to: prefer 'applies_to', fallback to wrapping 'approval_type'
    applies_to = body.applies_to
    if not applies_to and body.approval_type:
        applies_to = [body.approval_type]
    if not applies_to:
        applies_to = ["custom"]

    return applies_to, steps, conditions


def _normalize_update_body(body: WorkflowUpdateBody) -> dict:
    """Transform frontend update format to backend format."""
    updates = {}

    # Direct fields
    if body.name is not None:
        updates["name"] = body.name
    if body.description is not None:
        updates["description"] = body.description
    if body.canvas_layout is not None:
        updates["canvas_layout"] = body.canvas_layout

    # Steps: prefer flat, fallback to nested definition
    if body.steps is not None:
        updates["steps"] = body.steps
        if body.conditions is not None:
            updates["conditions"] = body.conditions
    elif body.definition is not None:
        updates["steps"] = body.definition.get("steps", [])
        conditions = body.definition.get("conditions")
        if conditions is not None:
            updates["conditions"] = conditions

    # Applies_to: prefer list, fallback to single approval_type
    if body.applies_to is not None:
        updates["applies_to"] = body.applies_to
    elif body.approval_type is not None:
        updates["applies_to"] = [body.approval_type]

    return updates


def _enrich_response(workflow: dict) -> dict:
    """Add frontend-compatible fields to workflow response.

    DB stores: applies_to (TEXT[]), steps (JSONB), conditions (JSONB)
    Frontend expects: approval_type (str), definition ({steps, conditions})
    """
    wf = dict(workflow)
    # approval_type: first element of applies_to
    applies_to = wf.get("applies_to")
    if applies_to and isinstance(applies_to, list) and len(applies_to) > 0:
        wf.setdefault("approval_type", applies_to[0])
    # definition: nest steps and conditions
    if "steps" in wf:
        wf.setdefault(
            "definition",
            {
                "steps": wf.get("steps", []),
                "conditions": wf.get("conditions") or [],
            },
        )
    return wf


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
            raise api_error(
                ErrorCode.VALIDATION_MISSING_FIELD, "Organization context required"
            )

        workflows = await workflow_definition_service.list_workflows(
            org_id=org_id, db=db
        )
        return api_success(data=[_enrich_response(w) for w in workflows])
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error listing workflows: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "工作流操作失败")


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
            raise api_error(
                ErrorCode.VALIDATION_MISSING_FIELD, "Organization context required"
            )

        applies_to, steps, conditions = _normalize_create_body(body)

        workflow = await workflow_definition_service.create_workflow(
            org_id=org_id,
            name=body.name,
            applies_to=applies_to,
            steps=steps,
            conditions=conditions,
            canvas_layout=body.canvas_layout,
            created_by=user_id,
            db=db,
        )
        return api_success(data=_enrich_response(workflow), message="Workflow created")
    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "工作流参数校验失败")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error creating workflow: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "工作流操作失败")


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

        workflow = await workflow_definition_service.get_workflow(
            workflow_id=workflow_id, db=db
        )
        if not workflow:
            raise api_error(
                ErrorCode.RESOURCE_NOT_FOUND, f"Workflow {workflow_id} not found"
            )

        return api_success(data=_enrich_response(workflow))
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error getting workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "工作流操作失败")


@router.put("/{workflow_id}")
async def update_workflow(
    request: Request,
    workflow_id: str,
    body: WorkflowUpdateBody,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """Update an existing workflow definition. Requires boss/founder role."""
    try:
        org_id = getattr(request.state, "org_id", None)
        db = getattr(request.state, "db", None)

        updates = _normalize_update_body(body)
        if not updates:
            return api_success(data=None, message="No updates provided")

        workflow = await workflow_definition_service.update_workflow(
            workflow_id=workflow_id,
            updates=updates,
            org_id=org_id,
            db=db,
        )
        return api_success(data=_enrich_response(workflow), message="Workflow updated")
    except ValueError:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "工作流参数校验失败")
    except RuntimeError:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "工作流操作失败")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error updating workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "工作流操作失败")


@router.delete("/{workflow_id}")
async def delete_workflow(
    request: Request,
    workflow_id: str,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """Delete a workflow definition. Requires boss/founder role."""
    try:
        db = getattr(request.state, "db", None)

        deleted = await workflow_definition_service.delete_workflow(
            workflow_id=workflow_id, db=db
        )
        if not deleted:
            raise api_error(
                ErrorCode.RESOURCE_NOT_FOUND, f"Workflow {workflow_id} not found"
            )

        return api_success(data={"deleted": workflow_id}, message="Workflow deleted")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error deleting workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "工作流操作失败")


@router.post("/{workflow_id}/toggle")
async def toggle_workflow(
    request: Request,
    workflow_id: str,
    user_id: str = Depends(require_role(["founder", "boss"])),
):
    """Toggle the active status of a workflow. Requires boss/founder role."""
    try:
        db = getattr(request.state, "db", None)

        workflow = await workflow_definition_service.toggle_workflow(
            workflow_id=workflow_id, db=db
        )
        return api_success(data=_enrich_response(workflow), message="Workflow toggled")
    except RuntimeError:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "工作流操作失败")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error toggling workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "工作流操作失败")


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
            raise api_error(
                ErrorCode.VALIDATION_MISSING_FIELD, "Organization context required"
            )

        workflow = await workflow_definition_service.set_default(
            workflow_id=workflow_id, org_id=org_id, db=db
        )
        return api_success(
            data=_enrich_response(workflow), message="Workflow set as default"
        )
    except RuntimeError:
        raise api_error(ErrorCode.RESOURCE_NOT_FOUND, "工作流操作失败")
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.error(f"Error setting default workflow {workflow_id}: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "工作流操作失败")
