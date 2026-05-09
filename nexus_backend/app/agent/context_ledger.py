"""Context budget ledger for agent prompt assembly.

The ledger records why each context block was included or dropped. It is small
enough to attach to traces and eval snapshots, but structured enough for cost
debugging, safety review, and prompt regression tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


MOJIBAKE_MARKERS = ("锛", "鈥", "銆", "�", "鐨", "浣", "涓")


@dataclass
class ContextLedgerEntry:
    provider: str
    priority: int
    tokens_estimated: int
    included: bool
    source_ids: list[str] = field(default_factory=list)
    freshness: str | None = None
    trust_level: str = "internal"
    pii_level: str = "unknown"
    truncated_reason: str | None = None
    notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextLedger:
    request_id: str | None = None
    total_budget: int = 0
    used_tokens: int = 0
    model_context_window: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    entries: list[ContextLedgerEntry] = field(default_factory=list)

    def add(self, entry: ContextLedgerEntry) -> None:
        self.entries.append(entry)
        if entry.included:
            self.used_tokens += max(entry.tokens_estimated, 0)

    def has_mojibake_risk(self) -> bool:
        for entry in self.entries:
            text = str(entry.notes.get("sample", ""))
            if any(marker in text for marker in MOJIBAKE_MARKERS):
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "total_budget": self.total_budget,
            "used_tokens": self.used_tokens,
            "model_context_window": self.model_context_window,
            "created_at": self.created_at,
            "mojibake_risk": self.has_mojibake_risk(),
            "entries": [entry.to_dict() for entry in self.entries],
        }


def estimate_pii_level(text: str) -> str:
    """Cheap PII hint for ledger metadata; real redaction stays elsewhere."""
    if not text:
        return "none"
    import re

    if re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", text):
        return "medium"
    if re.search(r"\b1[3-9]\d{9}\b", text):
        return "high"
    if re.search(r"\b\d{15}(\d{2}[0-9Xx])?\b", text):
        return "high"
    return "low"
