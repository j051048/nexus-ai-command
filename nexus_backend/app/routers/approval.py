from fastapi import APIRouter
from app.models.schemas import ApprovalRequest, StandardResponse
from app.services.approval_service import ApprovalService
from app.core.errors import api_success, api_error, ErrorCode

router = APIRouter(prefix="/api/approval", tags=["Approval"])

@router.post("/process", response_model=StandardResponse)
async def process_approval(request: ApprovalRequest):
    """
    Process approval request via AI analysis and intelligent rule enforcement.
    
    1. AI context analysis (semantic understanding)
    2. Rule engine guardrails (hard limits)
    3. Auto-decision or manual escalation
    """
    try:
        # P4 Enhancement: Delegate to service layer
        decision = await ApprovalService.process_approval(request)
        
        return api_success(
            data=decision.model_dump(),
            message="Approval Processed"
        )
    except Exception as e:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
