from fastapi import APIRouter, HTTPException
from app.models.schemas import ApprovalRequest, ApprovalDecision
from app.services.ai_service import AIService
from app.services.rule_engine import RuleEngine

router = APIRouter(prefix="/api/approval", tags=["Approval"])

# AI 返回值 → Pydantic 枚举值映射
DECISION_MAP = {
    # approved 变体
    "approved": "auto_approved",
    "APPROVED": "auto_approved",
    "Approved": "auto_approved",
    "auto_approved": "auto_approved",
    # rejected 变体
    "rejected": "auto_rejected",
    "REJECTED": "auto_rejected",
    "Rejected": "auto_rejected",
    "auto_rejected": "auto_rejected",
    # manual review 变体
    "manual_review": "manual_review_required",
    "manual": "manual_review_required",
    "review": "manual_review_required",
    "manual_review_required": "manual_review_required",
}


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
        
        # 获取 AI 返回的原始决策值并映射到 Pydantic 枚举
        raw_decision = ai_result.get("decision", "manual_review_required")
        normalized_decision = DECISION_MAP.get(raw_decision, "manual_review_required")
        
        # We can still check hardcoded safety limits in RuleEngine as a guardrail
        # but the primary reasoning comes from AI
        return ApprovalDecision(
            decision=normalized_decision,
            reason=ai_result.get("reasoning", "需要人工进一步核实详情"),
            boss_notification_sent=normalized_decision != "auto_approved"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval Analysis Failed: {str(e)}")
