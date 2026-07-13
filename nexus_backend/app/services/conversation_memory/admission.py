"""Admission policy for durable, trustworthy long-term memories."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

_SECRET_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|private[_-]?key|authorization|cookie)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|bearer\s+[A-Za-z0-9._-]{12,}|-----BEGIN [A-Z ]+PRIVATE KEY-----)",
    re.IGNORECASE,
)

SCIENTIFIC_MEMORY_CATEGORIES = frozenset(
    {
        "instrument_identity",
        "calibration_baseline",
        "maintenance_episode",
        "experiment_method",
        "compliance_evidence",
    }
)

_TTL_DAYS = {
    "preference": 365,
    "explicit_memory": 730,
    "personal_info": 365,
    "episodic": 180,
    "completed_task": 90,
    "tool_correction": 90,
    "maintenance_episode": 3650,
    "calibration_baseline": 1095,
    "experiment_method": 1095,
    "instrument_identity": 3650,
    "compliance_evidence": 3650,
}


@dataclass(frozen=True)
class MemoryAdmissionDecision:
    allowed: bool
    lifecycle_state: str
    sensitivity: str
    expires_at: str | None
    provenance: dict[str, Any]
    reason: str | None = None


def sanitize_tool_arguments(value: Any) -> Any:
    """Keep useful argument shape while removing credentials and bulky payloads."""
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            if _SECRET_KEY_RE.search(str(key)):
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = sanitize_tool_arguments(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_tool_arguments(item) for item in value[:20]]
    if isinstance(value, str):
        if _SECRET_VALUE_RE.search(value):
            return "[REDACTED]"
        return value[:500]
    return value


def evaluate_memory_admission(
    *,
    value: str,
    category: str,
    confidence: float,
    source: str | None,
    extraction_method: str | None,
    metadata: dict[str, Any] | None,
    valid_until: str | None,
    evidence_ref: str | None,
) -> MemoryAdmissionDecision:
    """Classify sensitivity, lifecycle and retention before a memory is written."""
    explicit = extraction_method == "user_explicit" or source == "user_explicit"
    provenance = {
        "source": source or "unknown",
        "extraction_method": extraction_method or "unknown",
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    if evidence_ref:
        provenance["evidence_ref"] = evidence_ref
    if metadata and metadata.get("session_id"):
        provenance["session_id"] = metadata["session_id"]

    if _SECRET_VALUE_RE.search(value):
        return MemoryAdmissionDecision(
            allowed=False,
            lifecycle_state="rejected",
            sensitivity="restricted",
            expires_at=None,
            provenance=provenance,
            reason="credential_or_secret_detected",
        )

    if category in {"personal_info", "explicit_memory", "episodic", "tool_correction"}:
        sensitivity = "restricted"
    elif category in SCIENTIFIC_MEMORY_CATEGORIES:
        sensitivity = "confidential"
    else:
        sensitivity = "internal"

    if category in {"compliance_evidence", "calibration_baseline"} and not evidence_ref:
        lifecycle_state = "pending_review"
    elif explicit:
        lifecycle_state = "confirmed"
    elif confidence < 0.72:
        lifecycle_state = "pending_review"
    else:
        lifecycle_state = "active"

    expires_at = valid_until
    if not expires_at:
        ttl_days = _TTL_DAYS.get(category, 180)
        expires_at = (datetime.now(UTC) + timedelta(days=ttl_days)).isoformat()

    return MemoryAdmissionDecision(
        allowed=True,
        lifecycle_state=lifecycle_state,
        sensitivity=sensitivity,
        expires_at=expires_at,
        provenance=provenance,
    )
