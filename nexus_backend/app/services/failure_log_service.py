"""
Agent Failure Log Service — records AI agent failures for analysis and learning.
"""

import logging
import re

from app.core.database import supabase

logger = logging.getLogger(__name__)

# ── Pattern-key derivation rules ────────────────────────────────
# Maps known error signatures to stable pattern keys for aggregation.

_ERROR_CODE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"PGRST204"), "supabase-column-missing"),
    (re.compile(r"PGRST301"), "supabase-rpc-not-found"),
    (re.compile(r"23502"), "not-null-violation"),
    (re.compile(r"23505"), "unique-violation"),
    (re.compile(r"23503"), "foreign-key-violation"),
    (re.compile(r"42P01"), "table-not-found"),
    (re.compile(r"42703"), "column-not-found"),
    (re.compile(r"429|rate.?limit", re.IGNORECASE), "rate-limit"),
    (re.compile(r"timeout|timed?\s*out", re.IGNORECASE), "timeout"),
    (re.compile(r"connection.?(?:refused|reset|error)", re.IGNORECASE), "connection-error"),
    (re.compile(r"permission.?denied|403|forbidden", re.IGNORECASE), "permission-denied"),
    (re.compile(r"not.?found|404", re.IGNORECASE), "not-found"),
]


def _derive_pattern_key(
    error_type: str,
    error_detail: str | None = None,
    tool_calls: list | None = None,
) -> str:
    """Derive a stable pattern_key from error context for aggregation.

    Format: {error_type}:{specific_signature}[:{tool_name}]
    Examples:
      - "hallucination:no-tool-call"
      - "wrong_params:supabase-column-missing:get_customers"
      - "timeout:timeout:web_search"
    """
    detail = error_detail or ""

    # Try to match a known error code/pattern
    signature = "unknown"
    for pattern, key in _ERROR_CODE_PATTERNS:
        if pattern.search(detail):
            signature = key
            break

    # Extract first tool name if available
    tool_suffix = ""
    if tool_calls:
        first_tool = None
        for tc in tool_calls[:3]:
            name = tc.get("tool_name") or tc.get("name") if isinstance(tc, dict) else None
            if name:
                first_tool = name
                break
        if first_tool:
            tool_suffix = f":{first_tool}"

    return f"{error_type}:{signature}{tool_suffix}"


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
        pattern_key: str | None = None,
    ) -> None:
        """Write a failure record. Fire-and-forget — never raises."""
        try:
            db = supabase
            if not db:
                logger.debug("[FailureLog] No DB connection, skipping")
                return

            # Auto-derive pattern_key if not provided
            if not pattern_key:
                pattern_key = _derive_pattern_key(error_type, error_detail, tool_calls)

            row = {
                "user_message": user_message[:2000],  # truncate to avoid oversized rows
                "error_type": error_type,
                "severity": severity,
                "pattern_key": pattern_key,
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

            await db.table("agent_failure_logs").insert(row).execute()
            logger.info(f"[FailureLog] Recorded {error_type} failure (severity={severity}, pattern={pattern_key})")
        except Exception as e:
            # Never let logging failures crash the agent
            logger.warning(f"[FailureLog] Failed to write failure log: {e}")

    async def get_top_failures(
        self, org_id: str, days: int = 7, limit: int = 10
    ) -> list[dict]:
        """Get top failure patterns for an org in the last N days.

        Groups by pattern_key for better aggregation, falls back to
        raw records if pattern_key column is not yet available.
        Also opportunistically cleans up records older than 90 days.
        """
        try:
            db = supabase
            if not db:
                return []

            from datetime import UTC, datetime, timedelta

            since = (datetime.now(UTC) - timedelta(days=days)).isoformat()

            # P0 Fix: Opportunistic TTL cleanup — delete records older than 90 days
            ttl_cutoff = (datetime.now(UTC) - timedelta(days=90)).isoformat()
            try:
                await (
                    db.table("agent_failure_logs")
                    .delete()
                    .eq("organization_id", org_id)
                    .lt("created_at", ttl_cutoff)
                    .execute()
                )
            except Exception:
                pass  # TTL cleanup is non-fatal

            # Fetch recent failures with pattern_key
            result = await (
                db.table("agent_failure_logs")
                .select("error_type, severity, user_message, error_detail, pattern_key, created_at")
                .eq("organization_id", org_id)
                .gte("created_at", since)
                .order("created_at", desc=True)
                .limit(100)  # fetch more for aggregation
                .execute()
            )
            rows = result.data or []
            if not rows:
                return []

            # Aggregate by pattern_key
            pattern_groups: dict[str, dict] = {}
            for r in rows:
                pk = r.get("pattern_key") or f"{r.get('error_type', 'unknown')}:unknown"
                if pk not in pattern_groups:
                    pattern_groups[pk] = {
                        "pattern_key": pk,
                        "error_type": r.get("error_type", "unknown"),
                        "severity": r.get("severity", "medium"),
                        "error_detail": (r.get("error_detail") or "")[:200],
                        "count": 0,
                        "latest": r.get("created_at", ""),
                        "saturated": False,
                    }
                pattern_groups[pk]["count"] += 1

            # Signal saturation detection: if a pattern appears >= 10 times
            # in the window, it's "saturated" — likely a systemic issue that
            # repeating in the prompt won't help fix. Deprioritize it.
            SATURATION_THRESHOLD = 10
            for pg in pattern_groups.values():
                if pg["count"] >= SATURATION_THRESHOLD:
                    pg["saturated"] = True

            # Sort by count desc, return top N
            sorted_patterns = sorted(pattern_groups.values(), key=lambda x: x["count"], reverse=True)
            return sorted_patterns[:limit]

        except Exception as e:
            logger.warning(f"[FailureLog] Failed to query failure logs: {e}")
            return []


# Singleton
failure_log_service = FailureLogService()
