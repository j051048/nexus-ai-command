"""
P4 Enhancement: Approval Service

Handles approval workflow logic including:
- AI-based decision recommendation
- Rule-based filtering
- Database updates
- Notifications
- P0: AI risk analysis for smart approval
"""

import logging
from datetime import UTC, datetime, timedelta

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
            normalized_decision = DECISION_MAP.get(raw_decision, "manual_review_required")
            ai_reason = ai_result.get("reasoning", "需要人工进一步核实详情")

            # 2. Rule Engine Guardrails (Optional but recommended)
            # We can use RuleEngine to forcefully reject or require review for large amounts, overriding AI
            rule_decision = RuleEngine.evaluate_approval(request)

            final_decision = normalized_decision
            final_reason = ai_reason

            # If Rule Engine suggests manual review but AI says auto-approve, trust Rule Engine for safety (amounts)
            if rule_decision.decision == "manual_review_required" and normalized_decision == "auto_approved":
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
            raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, f"Approval processing error: {str(e)}")

    @staticmethod
    async def analyze_risk(
        request_type: str,
        amount: float,
        description: str,
        user_id: str,
        org_id: str,
        db=None,
    ) -> dict:
        """
        P0: AI risk analysis for approval requests.

        Analyzes:
        1. Compliance rules - check description against patterns in compliance_rule table
        2. Historical patterns - how many similar requests this user made recently, average amounts
        3. Calculate risk_score (0-100)

        Returns:
            {
                "risk_score": int,          # 0-100, higher = more risky
                "compliance_flags": list,    # matched compliance rule names
                "historical_context": dict,  # user's recent request stats
                "recommendation": str,       # risk assessment recommendation
            }
        """
        risk_score = 0
        compliance_flags: list[str] = []
        historical_context: dict = {}
        recommendation = "低风险，可正常审批"

        if not db:
            logger.warning("No DB client for risk analysis, returning default low-risk result")
            return {
                "risk_score": risk_score,
                "compliance_flags": compliance_flags,
                "historical_context": historical_context,
                "recommendation": recommendation,
            }

        try:
            # ============ 1. Compliance Rules Check ============
            # Query active compliance rules and check description for matching patterns
            try:
                rules_result = (
                    await db.table("compliance_rule")
                    .select("rule_name, pattern, severity, check_type")
                    .eq("is_active", True)
                    .execute()
                )

                if rules_result.data:
                    import re

                    desc_lower = description.lower()
                    for rule in rules_result.data:
                        pattern = rule.get("pattern", "")
                        check_type = rule.get("check_type", "keyword")
                        severity = rule.get("severity", "warning")
                        rule_name = rule.get("rule_name", "未命名规则")

                        if not pattern:
                            continue

                        matched = False

                        if check_type == "keyword":
                            # Simple keyword matching
                            keywords = [k.strip().lower() for k in pattern.split(",") if k.strip()]
                            for kw in keywords:
                                if kw in desc_lower:
                                    matched = True
                                    break
                        elif check_type == "regex":
                            # Regex pattern matching
                            try:
                                if re.search(pattern, description, re.IGNORECASE):
                                    matched = True
                            except re.error:
                                logger.warning(f"Invalid regex pattern in compliance rule: {pattern}")

                        if matched:
                            compliance_flags.append(rule_name)
                            # Adjust risk score based on severity
                            if severity == "error":
                                risk_score += 30
                            elif severity == "warning":
                                risk_score += 15
                            else:
                                risk_score += 5

            except Exception as e:
                logger.warning(f"Compliance rules check failed: {e}")

            # ============ 2. Historical Patterns ============
            try:
                # Get recent requests from this user (last 30 days)
                thirty_days_ago = (datetime.now(UTC) - timedelta(days=30)).isoformat()

                hist_result = (
                    await db.table("approval_requests")
                    .select("amount, type, status, created_at")
                    .eq("submitted_by", user_id)
                    .gte("created_at", thirty_days_ago)
                    .execute()
                )

                if hist_result.data:
                    recent_requests = hist_result.data
                    total_count = len(recent_requests)
                    same_type_count = sum(1 for r in recent_requests if r.get("type") == request_type)
                    amounts = [float(r.get("amount", 0)) for r in recent_requests if r.get("amount")]
                    avg_amount = sum(amounts) / len(amounts) if amounts else 0
                    max_amount = max(amounts) if amounts else 0
                    rejected_count = sum(1 for r in recent_requests if r.get("status") == "rejected")

                    historical_context = {
                        "recent_30d_total": total_count,
                        "recent_30d_same_type": same_type_count,
                        "avg_amount": round(avg_amount, 2),
                        "max_amount": round(max_amount, 2),
                        "rejected_count": rejected_count,
                    }

                    # Adjust risk score based on historical patterns
                    # High frequency of same type requests
                    if same_type_count > 10:
                        risk_score += 15
                    elif same_type_count > 5:
                        risk_score += 5

                    # Amount significantly above average
                    if avg_amount > 0 and amount > avg_amount * 3:
                        risk_score += 20
                    elif avg_amount > 0 and amount > avg_amount * 2:
                        risk_score += 10

                    # High rejection rate
                    if total_count > 0 and (rejected_count / total_count) > 0.3:
                        risk_score += 15

                else:
                    historical_context = {
                        "recent_30d_total": 0,
                        "recent_30d_same_type": 0,
                        "avg_amount": 0,
                        "max_amount": 0,
                        "rejected_count": 0,
                    }

            except Exception as e:
                logger.warning(f"Historical patterns check failed: {e}")

            # ============ 3. Amount-based risk ============
            # Large amounts inherently carry more risk
            if amount > 100000:
                risk_score += 20
            elif amount > 50000:
                risk_score += 10
            elif amount > 10000:
                risk_score += 5

            # Ensure risk_score stays within 0-100
            risk_score = max(0, min(100, risk_score))

            # ============ 4. Generate Recommendation ============
            if risk_score >= 70:
                recommendation = "高风险：建议仔细审核，关注合规问题和异常模式"
            elif risk_score >= 40:
                recommendation = "中等风险：建议核实申请详情，关注金额合理性"
            elif risk_score >= 20:
                recommendation = "低风险：可按正常流程审批，无明显异常"
            else:
                recommendation = "极低风险：申请正常，可快速审批"

        except Exception as e:
            logger.error(f"Risk analysis failed: {e}")
            # Return a default result on failure rather than raising
            return {
                "risk_score": 0,
                "compliance_flags": [],
                "historical_context": {},
                "recommendation": "风险分析暂不可用，请按常规流程审批",
            }

        return {
            "risk_score": risk_score,
            "compliance_flags": compliance_flags,
            "historical_context": historical_context,
            "recommendation": recommendation,
        }

    # ==========================
    # P1: Urgency & Timeouts
    # ==========================

    @staticmethod
    async def urge_approval(approval_id: str, user_id: str, reason: str, db=None) -> dict:
        """
        P1-5: Urge an existing pending approval.
        Updates the urgency indicator and logs the reason.
        """
        if not db:
            raise RuntimeError("Database client is required to urge an approval")

        res = await db.table("approval_requests").select("*").eq("id", approval_id).execute()
        if not res.data:
            raise ValueError(f"ID为 {approval_id} 的审批请求未找到")

        req = res.data[0]
        if req.get("status") != "pending":
            raise ValueError(f"只能催办待处理的审批，该审批当前状态为：{req.get('status')}")

        # In a full data model, we might have an `urgency_level` or `comments` JSON field.
        # Here we bump the `updated_at` time to push it up in the queue, and could store context.
        # We will assume a `metadata` JSONB column exists, or just use `updated_at`.
        current_metadata = req.get("metadata") or {}
        urgency_count = current_metadata.get("urgency_count", 0) + 1
        current_metadata["urgency_count"] = urgency_count
        current_metadata["last_urgency_reason"] = reason
        current_metadata["last_urgency_time"] = datetime.now(UTC).isoformat()
        current_metadata["last_urged_by"] = user_id

        update_res = (
            await db.table("approval_requests")
            .update({"metadata": current_metadata, "updated_at": datetime.now(UTC).isoformat()})
            .eq("id", approval_id)
            .execute()
        )

        # Emit business event for notifications
        try:
            from app.services.event_bus import EventType, event_bus

            await event_bus.emit(
                EventType.SYSTEM_ALERT.value,
                {
                    "source": "approval_service",
                    "message": f"审批被催办: {req.get('type')} / {req.get('details')}",
                    "approval_id": approval_id,
                    "urgency_count": urgency_count,
                },
            )
        except Exception as e:
            logger.error(f"Event bus error while urging: {e}")

        return {"success": True, "message": f"成功催办审批", "urgency_count": urgency_count}

    @staticmethod
    async def check_approval_timeouts(db=None) -> list[dict]:
        """
        P1-5: Proactive timeout detection logic.
        Scans for pending approvals older than 24 hours (or SLA) and escalates them.
        """
        if not db:
            raise RuntimeError("Database client is required to check timeouts")

        timeout_threshold = (datetime.now(UTC) - timedelta(hours=24)).isoformat()

        res = (
            await db.table("approval_requests")
            .select("*")
            .eq("status", "pending")
            .lt("created_at", timeout_threshold)
            .execute()
        )

        escalated = []
        for req in res.data or []:
            current_metadata = req.get("metadata") or {}
            if current_metadata.get("is_escalated"):
                continue  # Already escalated

            current_metadata["is_escalated"] = True
            current_metadata["escalation_time"] = datetime.now(UTC).isoformat()

            await db.table("approval_requests").update({"metadata": current_metadata}).eq("id", req["id"]).execute()

            escalated.append({"id": req["id"], "type": req.get("type"), "details": req.get("details")})

            # Send escalation alert
            try:
                from app.services.event_bus import EventType, event_bus

                await event_bus.emit(
                    EventType.SYSTEM_ALERT.value,
                    {
                        "source": "approval_service",
                        "level": "warning",
                        "message": f"⚠️ 审批已超时 24 小时并被升级: {req.get('type')}",
                        "approval_id": req["id"],
                    },
                )
            except Exception as e:
                logger.error(f"Event bus error during timeout check: {e}")

        return escalated
