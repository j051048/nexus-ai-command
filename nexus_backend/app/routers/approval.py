import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import ApprovalRequest, StandardResponse
from app.services.approval_chain import approval_chain_service
from app.services.approval_service import ApprovalService
from app.services.form_schema_service import form_schema_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approval", tags=["Approval"])


# ============== Request Models ==============


class SubmitWithFormRequest(BaseModel):
    type: str  # 审批类型
    amount: float
    details: str
    form_data: dict[str, Any] = {}


# ============== Endpoints ==============


@router.post("/process", response_model=StandardResponse)
async def process_approval(request: ApprovalRequest, user_id: str = Depends(get_current_user_id)):
    """
    Process approval request via AI analysis and intelligent rule enforcement.

    1. AI context analysis (semantic understanding)
    2. Rule engine guardrails (hard limits)
    3. Auto-decision or manual escalation
    """
    try:
        # P4 Enhancement: Delegate to service layer
        decision = await ApprovalService.process_approval(request)

        return api_success(data=decision.model_dump(), message="Approval Processed")
    except Exception as e:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/submit-with-form")
async def submit_with_form(
    request: Request,
    body: SubmitWithFormRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Submit an approval request with custom form data.

    Workflow:
    1. Load the active form_schema for the given approval type
    2. Validate form_data against the schema
    3. Create the approval request (with form_data and form_schema_id)
    4. Route through the approval chain
    """
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_PERMISSION_DENIED, "需要组织上下文")

    client = getattr(request.state, "db", None)
    if not client:
        raise api_error(ErrorCode.DB_CONNECTION_ERROR, "数据库连接不可用")

    try:
        # 1. Load form schema for this approval type
        schema = await form_schema_service.get_schema_for_type(
            org_id, body.type, db=client
        )

        form_schema_id = None

        if schema:
            form_schema_id = schema.get("id")
            schema_fields = schema.get("fields", [])

            # 2. Validate form_data against schema
            if schema_fields and body.form_data:
                validation_errors = form_schema_service.validate_form_data(
                    schema_fields, body.form_data
                )
                if validation_errors:
                    raise api_error(
                        ErrorCode.VALIDATION_INVALID_INPUT,
                        "表单数据校验失败",
                        details={"errors": validation_errors},
                    )
            elif schema_fields:
                # Schema exists but no form_data provided: check required fields
                validation_errors = form_schema_service.validate_form_data(
                    schema_fields, {}
                )
                if validation_errors:
                    raise api_error(
                        ErrorCode.VALIDATION_INVALID_INPUT,
                        "表单数据校验失败",
                        details={"errors": validation_errors},
                    )

        # 3. Create approval request record in database
        insert_data = {
            "submitted_by": user_id,
            "type": body.type,
            "amount": body.amount,
            "description": body.details,
            "status": "pending",
            "organization_id": org_id,
        }

        if body.form_data:
            insert_data["form_data"] = body.form_data
        if form_schema_id:
            insert_data["form_schema_id"] = form_schema_id

        result = await client.table("approval_requests").insert(
            insert_data
        ).execute()

        if not result.data:
            raise api_error(
                ErrorCode.DB_QUERY_ERROR, "审批请求创建失败"
            )

        created_request = (
            result.data[0] if isinstance(result.data, list) else result.data
        )
        request_id = created_request.get("id")

        # 4. Route through approval chain
        chain_result = await approval_chain_service.process_approval_request(
            request_id=request_id,
            approval_type=body.type,
            amount=body.amount,
            requester_id=user_id,
            description=body.details,
        )

        # Update approval request with chain result status if auto-approved
        if chain_result.get("auto_approved"):
            await client.table("approval_requests").update(
                {"status": "approved", "ai_decision": "auto_approved"}
            ).eq("id", request_id).execute()

        return api_success(
            data={
                "request_id": request_id,
                "form_schema_id": form_schema_id,
                "chain_result": chain_result,
                "approval_request": created_request,
            },
            message="审批请求已提交",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit with form failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
