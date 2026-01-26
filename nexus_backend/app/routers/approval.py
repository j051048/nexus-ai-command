from fastapi import APIRouter, HTTPException
from app.models.schemas import ApprovalRequest, ApprovalDecision
from app.services.ai_service import AIService
from app.services.rule_engine import RuleEngine

router = APIRouter(prefix="/api/approval", tags=["Approval"])

@router.post("/process", response_model=ApprovalDecision)
async def process_approval(request: ApprovalRequest):
    """
    Process approval request using AI Orchestration (Task A).
    """
    try:
        # Task A: AI Orchestration Layer
        # Instead of hardcoding, we use LLM to analyze the request context
        ai_result = await AIService.analyze_approval(
            request_type=request.type,
            description=request.details,
            amount=request.amount
        )
        
        # We can still check hardcoded safety limits in RuleEngine as a guardrail
        # but the primary reasoning comes from AI
        return ApprovalDecision(
            decision=ai_result.get("decision", "manual_review_required"),
            reason=ai_result.get("reasoning", "需要人工进一步核实详情"),
            boss_notification_sent=ai_result.get("decision") != "auto_approved"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval Analysis Failed: {str(e)}")
