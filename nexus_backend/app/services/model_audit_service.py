"""
P2 Enhancement: Model Output Audit Service

Implements comprehensive audit logging for LLM inputs/outputs.
Fixes Issue #34: Missing model output audit logs.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""

    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    CONTENT_FLAG = "content_flag"
    POLICY_VIOLATION = "policy_violation"
    COST_THRESHOLD = "cost_threshold"


@dataclass
class AuditEntry:
    """Audit log entry."""

    event_id: str
    event_type: AuditEventType
    timestamp: str
    user_id: str
    org_id: str | None
    session_id: str | None
    trace_id: str | None
    model: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    input_preview: str | None = None
    output_preview: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    status: str = "success"
    flags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "org_id": self.org_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "model": self.model,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "input_preview": self.input_preview,
            "output_preview": self.output_preview,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "flags": self.flags,
            "metadata": self.metadata,
        }


class ModelAuditService:
    """
    P2 Enhancement: Comprehensive audit logging for LLM operations.

    Features:
    - Full input/output tracking
    - Content hashing for privacy
    - Cost tracking
    - Policy violation detection
    - Queryable audit trail
    - Compliance support
    """

    # Cost per 1K tokens (approximate)
    MODEL_COSTS = {
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "claude-3-opus": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet": {"input": 0.003, "output": 0.015},
        "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    }

    # Content flags
    SENSITIVE_PATTERNS = [
        ("api_key", r"sk-[a-zA-Z0-9]{20,}"),
        ("password", r"password[\s]*[:=][\s]*\S+"),
        ("token", r"token[\s]*[:=][\s]*\S+"),
    ]

    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._audit_log: list[AuditEntry] = []
        self._pending_entries: list[AuditEntry] = []
        self._cost_thresholds = {
            "per_request": 1.0,  # $1 per request
            "per_hour": 10.0,  # $10 per hour
            "per_day": 100.0,  # $100 per day
        }

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        import uuid

        return f"audit_{uuid.uuid4().hex[:12]}"

    def _hash_content(self, content: str) -> str:
        """Hash content for privacy-preserving audit."""
        if not content:
            return ""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _preview_content(self, content: str, max_len: int = 100) -> str:
        """Create preview of content."""
        if not content:
            return ""
        preview = content[:max_len]
        if len(content) > max_len:
            preview += "..."
        return preview

    def _calculate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Calculate cost for LLM call."""
        costs = self.MODEL_COSTS.get(model, {"input": 0.001, "output": 0.002})
        input_cost = (tokens_in / 1000) * costs["input"]
        output_cost = (tokens_out / 1000) * costs["output"]
        return round(input_cost + output_cost, 6)

    def _check_content_flags(self, content: str) -> list[str]:
        """Check content for sensitive patterns."""
        import re

        flags = []
        for flag_name, pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                flags.append(flag_name)
        return flags

    async def log_llm_request(
        self,
        user_id: str,
        model: str,
        input_content: str,
        org_id: str = None,
        session_id: str = None,
        trace_id: str = None,
        metadata: dict = None,
    ) -> str:
        """
        Log an LLM request.
        Returns event_id for correlation with response.
        """
        entry = AuditEntry(
            event_id=self._generate_event_id(),
            event_type=AuditEventType.LLM_REQUEST,
            timestamp=datetime.utcnow().isoformat() + "Z",
            user_id=user_id,
            org_id=org_id,
            session_id=session_id,
            trace_id=trace_id,
            model=model,
            input_hash=self._hash_content(input_content),
            input_preview=self._preview_content(input_content),
            flags=self._check_content_flags(input_content),
            metadata=metadata or {},
        )

        self._add_entry(entry)
        return entry.event_id

    async def log_llm_response(
        self,
        request_event_id: str,
        user_id: str,
        model: str,
        output_content: str,
        tokens_in: int,
        tokens_out: int,
        duration_ms: int,
        status: str = "success",
        org_id: str = None,
        session_id: str = None,
        trace_id: str = None,
        metadata: dict = None,
    ) -> AuditEntry:
        """Log an LLM response."""
        cost = self._calculate_cost(model, tokens_in, tokens_out)

        entry = AuditEntry(
            event_id=self._generate_event_id(),
            event_type=AuditEventType.LLM_RESPONSE,
            timestamp=datetime.utcnow().isoformat() + "Z",
            user_id=user_id,
            org_id=org_id,
            session_id=session_id,
            trace_id=trace_id,
            model=model,
            output_hash=self._hash_content(output_content),
            output_preview=self._preview_content(output_content),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            duration_ms=duration_ms,
            status=status,
            flags=self._check_content_flags(output_content),
            metadata=metadata or {},
        )

        self._add_entry(entry)

        # Check cost thresholds
        await self._check_cost_thresholds(user_id, org_id, cost)

        return entry

    async def log_tool_call(
        self,
        user_id: str,
        tool_name: str,
        tool_args: dict,
        tool_result: str,
        status: str,
        duration_ms: int,
        org_id: str = None,
        trace_id: str = None,
    ) -> AuditEntry:
        """Log a tool call."""
        entry = AuditEntry(
            event_id=self._generate_event_id(),
            event_type=AuditEventType.TOOL_CALL,
            timestamp=datetime.utcnow().isoformat() + "Z",
            user_id=user_id,
            org_id=org_id,
            trace_id=trace_id,
            input_hash=self._hash_content(json.dumps(tool_args)),
            input_preview=self._preview_content(str(tool_args)),
            output_hash=self._hash_content(tool_result),
            output_preview=self._preview_content(tool_result),
            duration_ms=duration_ms,
            status=status,
            metadata={"tool_name": tool_name, "tool_args": tool_args},
        )

        self._add_entry(entry)
        return entry

    async def log_policy_violation(
        self, user_id: str, violation_type: str, content: str, action_taken: str, org_id: str = None
    ) -> AuditEntry:
        """Log a policy violation."""
        entry = AuditEntry(
            event_id=self._generate_event_id(),
            event_type=AuditEventType.POLICY_VIOLATION,
            timestamp=datetime.utcnow().isoformat() + "Z",
            user_id=user_id,
            org_id=org_id,
            input_preview=self._preview_content(content),
            status="blocked",
            flags=[violation_type],
            metadata={"action_taken": action_taken},
        )

        self._add_entry(entry)
        return entry

    def _add_entry(self, entry: AuditEntry):
        """Add entry to audit log."""
        self._audit_log.append(entry)

        # Trim if needed
        if len(self._audit_log) > self.max_entries:
            self._audit_log = self._audit_log[-self.max_entries :]

    async def _check_cost_thresholds(self, user_id: str, org_id: str, current_cost: float):
        """Check if cost thresholds are exceeded."""
        # Get user's total cost today
        today = datetime.utcnow().date()
        user_costs = [
            e.cost_usd
            for e in self._audit_log
            if e.user_id == user_id
            and e.event_type == AuditEventType.LLM_RESPONSE
            and datetime.fromisoformat(e.timestamp.rstrip("Z")).date() == today
        ]
        total_cost = sum(user_costs) + current_cost

        if total_cost > self._cost_thresholds["per_day"]:
            logger.warning(f"User {user_id} exceeded daily cost threshold: ${total_cost:.2f}")
            await self._log_cost_alert(user_id, org_id, total_cost, "daily")

    async def _log_cost_alert(self, user_id: str, org_id: str, total_cost: float, threshold_type: str):
        """Log cost threshold alert."""
        entry = AuditEntry(
            event_id=self._generate_event_id(),
            event_type=AuditEventType.COST_THRESHOLD,
            timestamp=datetime.utcnow().isoformat() + "Z",
            user_id=user_id,
            org_id=org_id,
            cost_usd=total_cost,
            metadata={"threshold_type": threshold_type},
        )
        self._add_entry(entry)

    def query(
        self,
        user_id: str = None,
        org_id: str = None,
        event_type: AuditEventType = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query audit log with filters."""
        results = []

        for entry in reversed(self._audit_log):
            # Apply filters
            if user_id and entry.user_id != user_id:
                continue
            if org_id and entry.org_id != org_id:
                continue
            if event_type and entry.event_type != event_type:
                continue
            if start_time:
                entry_time = datetime.fromisoformat(entry.timestamp.rstrip("Z"))
                if entry_time < start_time:
                    continue
            if end_time:
                entry_time = datetime.fromisoformat(entry.timestamp.rstrip("Z"))
                if entry_time > end_time:
                    continue

            results.append(entry.to_dict())

            if len(results) >= limit:
                break

        return results

    def get_stats(self, org_id: str = None, user_id: str = None) -> dict:
        """Get audit statistics."""
        entries = self._audit_log

        if org_id:
            entries = [e for e in entries if e.org_id == org_id]
        if user_id:
            entries = [e for e in entries if e.user_id == user_id]

        total_tokens_in = sum(e.tokens_in for e in entries if e.event_type == AuditEventType.LLM_RESPONSE)
        total_tokens_out = sum(e.tokens_out for e in entries if e.event_type == AuditEventType.LLM_RESPONSE)
        total_cost = sum(e.cost_usd for e in entries)

        return {
            "total_events": len(entries),
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_cost_usd": round(total_cost, 4),
            "by_event_type": {et.value: len([e for e in entries if e.event_type == et]) for et in AuditEventType},
            "violations": len([e for e in entries if e.event_type == AuditEventType.POLICY_VIOLATION]),
        }

    async def persist_to_db(self, db=None):
        """Persist audit logs to database."""
        if not db:
            return

        try:
            for entry in self._audit_log[-100:]:  # Persist last 100
                await db.table("model_audit_logs").upsert(entry.to_dict()).execute()
        except Exception as e:
            logger.error(f"Failed to persist audit logs: {e}")


# Global instance
model_audit_service = ModelAuditService()
