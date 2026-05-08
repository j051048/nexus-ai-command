"""Unified PII redaction helpers for logs, LLM input, traces, and tool output."""

from __future__ import annotations

import re
from typing import Any

_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_CN_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")
_CN_ID_CARD_RE = re.compile(r"(?<!\d)(\d{3})\d{11}(\d{3}[\dXx])(?!\d)")
_BANK_CARD_RE = re.compile(r"(?<!\d)(\d{4})\d{8,11}(\d{4})(?!\d)")
_US_SSN_RE = re.compile(r"(?<!\d)(\d{3})-\d{2}-(\d{4})(?!\d)")
_API_KEY_RE = re.compile(
    r"(?i)\b((?:sk|api|token|key|secret)[-_]?[A-Za-z0-9]{12,})\b"
)

_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "secret",
    "credential",
    "authorization",
    "cookie",
}


def redact_text(text: str) -> str:
    """Mask common PII and credential patterns in free text."""
    if not text:
        return text
    redacted = _EMAIL_RE.sub(r"\1***@\2", text)
    redacted = _CN_PHONE_RE.sub(r"\1****\2", redacted)
    redacted = _CN_ID_CARD_RE.sub(r"\1***********\2", redacted)
    redacted = _BANK_CARD_RE.sub(r"\1********\2", redacted)
    redacted = _US_SSN_RE.sub(r"\1-**-\2", redacted)
    redacted = _API_KEY_RE.sub("[REDACTED_SECRET]", redacted)
    return redacted


def redact_value(value: Any) -> Any:
    """Recursively redact strings inside JSON-like values."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, dict):
        safe: dict[Any, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in _SENSITIVE_KEYS or any(k in key_text for k in _SENSITIVE_KEYS):
                safe[key] = "[REDACTED_SECRET]"
            else:
                safe[key] = redact_value(item)
        return safe
    return value


def redact_messages(messages: list[Any]) -> list[Any]:
    """Return redacted message copies when possible; mutate message objects only as fallback."""
    redacted: list[Any] = []
    for msg in messages:
        if isinstance(msg, dict):
            redacted.append(redact_value(msg))
            continue
        content = getattr(msg, "content", None)
        if isinstance(content, str):
            try:
                msg = msg.copy(update={"content": redact_text(content)})
            except Exception:
                try:
                    msg.content = redact_text(content)
                except Exception:
                    pass
        redacted.append(msg)
    return redacted
