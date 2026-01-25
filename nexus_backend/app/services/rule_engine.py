from app.models.schemas import ApprovalRequest, ApprovalDecision, PerformanceEvent
from typing import Dict

class RuleEngine:
    """
    Core Logic for Project Nexus.
    95% automation goal.
    """

    @staticmethod
    def calculate_performance_score(event: PerformanceEvent, current_daily_stats: Dict) -> float:
        """
        Calculate score delta based on event and current stats.
        Hardcoded rules as per requirements.
        """
        score = 0.0
        
        # Rule 1: Daily Follow-ups
        if event.event_type == 'lead_updated':
            # Check if this update pushes the count over 3 (Logic would normally query DB, simulating here)
            # Assuming 'data' contains 'daily_count' for simplicity in this MVP
            current_count = event.data.get('daily_updates_count', 0)
            if current_count == 3: # Just hit the threshold
                score += 20.0
        
        # Rule 2: Call Quality (AI Analyzed upstream)
        if event.event_type == 'call_finished':
            quality_score = event.data.get('ai_quality_score', 0)
            if quality_score > 80:
                score += 30.0

        # Rule 3: Win Rate / Opportunity Stage (Simplified)
        if event.event_type == 'deal_won':
            deal_value = event.data.get('value', 0)
            score += (deal_value / 1000) * 5 # 5 points per 1000 currency

        return score

    @staticmethod
    def evaluate_approval(request: ApprovalRequest) -> ApprovalDecision:
        """
        Auto-approve small requests. Escalate large ones.
        """
        decision = "manual_review_required"
        reason = "Standard review procedure"
        notify_boss = True

        # Rule: Purchase < 15,000
        if request.type == 'purchase':
            if request.amount < 15000:
                decision = "auto_approved"
                reason = "Purchase under auto-approval limit (15k)"
                notify_boss = False
            elif request.amount > 15000 * 1.1: # > 10% over standard
                decision = "manual_review_required"
                reason = "Purchase exceeds limit by >10%"
                notify_boss = True
        
        # Rule: Travel < 2,000 / day
        elif request.type == 'travel':
            if request.amount < 2000:
                decision = "auto_approved"
                reason = "Travel expense under daily limit (2k)"
                notify_boss = False
            else:
                decision = "manual_review_required"
                reason = "Travel expense high"
                notify_boss = True

        # Rule: Expense (Reimbursement)
        elif request.type == 'expense' and request.amount < 500:
             decision = "auto_approved"
             reason = "Small expense auto-approved"
             notify_boss = False

        return ApprovalDecision(
            decision=decision,
            reason=reason,
            boss_notification_sent=notify_boss
        )
