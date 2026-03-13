"""
Agent Failure Log Service — records AI agent failures for analysis and learning.
"""

import logging

from app.core.database import supabase

logger = logging.getLogger(__name__)


class FailureLogService:
    """Persist agent failure cases to agent_failure_logs table."""

    async def log_failure(
        self,
        *,
        org_id: str | None = None,
        user_id: str | None = None,
        conversation_id: str | None = None,
        user_message: str,
        intent_summary: str | None = None,
        complexity: str | None = None,
        tool_calls: list | None = None,
        error_type: str,
        error_detail: str | None = None,
        severity: str = "medium",
    ) -> None:
        """Write a failure record. Fire-and-forget — never raises."""
        try:
            db = supabase
            if not db:
                logger.debug("[FailureLog] No DB connection, skipping")
                return

            row = {
                "user_message": user_message[:2000],  # truncate to avoid oversized rows
                "error_type": error_type,
                "severity": severity,
            }
            if org_id:
                row["organization_id"] = org_id
            if user_id:
                row["user_id"] = user_id
            if conversation_id:
                row["conversation_id"] = conversation_id
            if intent_summary:
                row["intent_summary"] = intent_summary[:500]
            if complexity:
                row["complexity"] = complexity
            if tool_calls:
                row["tool_calls"] = tool_calls[:20]  # cap at 20 entries
            if error_detail:
                row["error_detail"] = error_detail[:2000]

            db.table("agent_failure_logs").insert(row).execute()
            logger.info(f"[FailureLog] Recorded {error_type} failure (severity={severity})")
        except Exception as e:
            # Never let logging failures crash the agent
            logger.warning(f"[FailureLog] Failed to write failure log: {e}")

    async def get_top_failures(
        self, org_id: str, days: int = 7, limit: int = 10
    ) -> list[dict]:
        """Get top failure types for an org in the last N days."""
        try:
            db = supabase
            if not db:
                return []

            from datetime import UTC, datetime, timedelta

            since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
            result = (
                db.table("agent_failure_logs")
                .select("error_type, severity, user_message, error_detail, created_at")
                .eq("organization_id", org_id)
                .gte("created_at", since)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.warning(f"[FailureLog] Failed to query failure logs: {e}")
            return []


# Singleton
failure_log_service = FailureLogService()
