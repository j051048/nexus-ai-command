"""
P4 Enhancement: Incentive Service

Handles business logic for:
- Calculating bonuses and rewards
- Creating incentive records in DB
- Triggering notifications
"""

import logging
import uuid
from datetime import datetime

from app.core.database import supabase
from app.core.errors import ErrorCode, api_error
from app.models.schemas import IncentiveResponse, IncentiveTrigger

logger = logging.getLogger(__name__)


class IncentiveService:
    @staticmethod
    async def trigger_incentive(trigger: IncentiveTrigger) -> IncentiveResponse:
        try:
            bonus_amount = 0.0
            reason = ""
            incentive_type = "bonus"

            # Business Logic for Incentives
            if trigger.trigger_type == "daily_target_hit":
                bonus_amount = 100.0
                reason = "Daily score > 85"
                incentive_type = "daily_bonus"

            elif trigger.trigger_type == "deal_closed":
                deal_value = float(trigger.context.get("value", 0))
                # Tiered bonus structure
                if deal_value > 50000:
                    bonus_amount = 500.0
                    reason = f"Big Deal Bonus (>50k): {deal_value}"
                elif deal_value > 10000:
                    bonus_amount = 200.0
                    reason = f"Standard Deal Bonus (>10k): {deal_value}"
                else:
                    bonus_amount = 50.0
                    reason = "Small Deal Bonus"
                incentive_type = "commission"

            elif trigger.trigger_type == "rank_top_3":
                incentive_type = "rank_reward"
                bonus_amount = 1000.0
                reason = "Monthly Top 3 Performance"

            elif trigger.trigger_type == "manual_bonus":
                bonus_amount = float(trigger.context.get("amount", 0))
                reason = trigger.context.get("reason", "Manual Bonus")
                incentive_type = "manual_bonus"

            # Create Record Payload
            record = {
                "id": str(uuid.uuid4()),
                "user_id": trigger.user_id,
                "type": incentive_type,
                "amount": bonus_amount,
                "reason": reason,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
            }

            # Persist to Supabase if configured
            if supabase:
                try:
                    await supabase.table("incentives").insert(record).execute()
                    logger.info(f"Incentive created: {record['id']} for user {trigger.user_id}")
                except Exception as db_err:
                    logger.error(f"Failed to save incentive to DB: {db_err}")
                    # Don't fail the request if DB fails, but log it criticaly
            else:
                logger.warning("Supabase not configured. Incentive record NOT saved.")

            return IncentiveResponse(
                unique_id=record["id"],
                type=incentive_type,
                amount=bonus_amount,
                reason=reason,
                status="pending",
                created_at=datetime.fromisoformat(record["created_at"]),
            )

        except Exception as e:
            logger.error(f"Error processing incentive trigger: {e}")
            raise api_error(
                ErrorCode.SYSTEM_INTERNAL_ERROR,
                message=f"Incentive calculation failed: {str(e)}",
            )
