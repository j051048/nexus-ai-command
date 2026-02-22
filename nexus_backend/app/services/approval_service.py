"""
P4 Enhancement: Approval Service

Handles approval workflow logic including:
- AI-based decision recommendation
- Rule-based filtering
- Database updates
- Notifications
"""

import logging

from app.core.errors import ErrorCode, api_error
from app.models.schemas import ApprovalDecision, ApprovalRequest
from app.services.ai_service import AIService
from app.services.rule_engine import RuleEngine

logger = logging.getLogger(__name__)

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


class ApprovalService:
    @staticmethod
    async def process_approval(request: ApprovalRequest) -> ApprovalDecision:
        """
        Orchestrate approval process:
        1. AI Analysis
        2. Rule Engine Check (Guardrails)
        3. Decision normalization
        """
        try:
            # 1. AI Analysis
            ai_result = await AIService.analyze_approval(
                request_type=request.type,
                description=request.details,
                amount=request.amount,
            )

            raw_decision = ai_result.get("decision", "manual_review_required")
            normalized_decision = DECISION_MAP.get(
                raw_decision, "manual_review_required"
            )
            ai_reason = ai_result.get("reasoning", "需要人工进一步核实详情")

            # 2. Rule Engine Guardrails (Optional but recommended)
            # We can use RuleEngine to forcefully reject or require review for large amounts, overriding AI
            rule_decision = RuleEngine.evaluate_approval(request)

            final_decision = normalized_decision
            final_reason = ai_reason

            # If Rule Engine suggests manual review but AI says auto-approve, trust Rule Engine for safety (amounts)
            if (
                rule_decision.decision == "manual_review_required"
                and normalized_decision == "auto_approved"
            ):
                final_decision = "manual_review_required"
                final_reason = f"Security Rule Override: {rule_decision.reason}. AI Reason: {ai_reason}"

            # 3. Construct Result
            return ApprovalDecision(
                decision=final_decision,
                reason=final_reason,
                boss_notification_sent=(final_decision != "auto_approved"),
                requires_human_review=(final_decision == "manual_review_required"),
            )

        except Exception as e:
            logger.error(f"Approval process failed: {e}")
            raise api_error(
                ErrorCode.SYSTEM_INTERNAL_ERROR, f"Approval processing error: {str(e)}"
            )
