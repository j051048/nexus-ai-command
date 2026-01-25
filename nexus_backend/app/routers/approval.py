from fastapi import APIRouter
from app.models.schemas import ApprovalRequest, ApprovalDecision
from app.services.rule_engine import RuleEngine

router = APIRouter(prefix="/api/approval", tags=["Approval"])

@router.post("/process", response_model=ApprovalDecision)
async def process_approval(request: ApprovalRequest):
    """
    Process approval request using AI rules.
    1. Parse NL (Simulated here, assuming frontend sends structured data or we use a parsed form)
    2. Run Rules
    3. Return decision
    """
    # In a real scenario, 'details' might be "I need to fly to Beijing for 3000 RMB".
    # An LLM chain would parse that into {type: travel, amount: 3000}.
    # Here we assume structured input for the backend logic.
    
    decision = RuleEngine.evaluate_approval(request)
    
    # If notify_boss is True, we would trigger a webhook here.
    if decision.boss_notification_sent:
        print(f"WEBHOOK TRIGGERED: Send to Boss Dashboard for {request.requester_id} - {request.amount}")

    return decision
