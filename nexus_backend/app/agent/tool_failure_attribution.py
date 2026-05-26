"""Tool failure attribution for Agent replanning and QA dashboards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ToolFailureAttribution:
    category: str
    confidence: float
    retryable: bool
    owner: str
    suggested_action: str


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).lower()


def classify_tool_failure(tool_record: Any) -> ToolFailureAttribution:
    """Classify why a tool failed using stable, explainable rules."""
    if isinstance(tool_record, Mapping):
        name = _as_text(tool_record.get("tool_name") or tool_record.get("name"))
        result = _as_text(tool_record.get("result") or tool_record.get("error"))
        error_type = _as_text(tool_record.get("error_type") or tool_record.get("status"))
    else:
        name = _as_text(
            getattr(tool_record, "tool_name", None)
            or getattr(tool_record, "name", None)
        )
        result = _as_text(
            getattr(tool_record, "result", None)
            or getattr(tool_record, "error", None)
        )
        error_type = _as_text(
            getattr(tool_record, "error_type", None)
            or getattr(tool_record, "status", None)
        )

    haystack = " ".join([name, result, error_type])

    if "param" in error_type or any(
        token in haystack for token in ("missing", "required", "invalid", "schema")
    ):
        return ToolFailureAttribution(
            "invalid_params",
            0.9,
            True,
            "planner",
            "Repair required fields and argument shape before retrying.",
        )
    if any(
        token in haystack
        for token in ("permission", "forbidden", "unauthorized", "401", "403", "rbac")
    ):
        return ToolFailureAttribution(
            "permission_denied",
            0.9,
            False,
            "operator",
            "Ask for authorization or route to a permitted read-only alternative.",
        )
    if any(
        token in haystack
        for token in ("timeout", "timed out", "deadline", "temporarily unavailable")
    ):
        return ToolFailureAttribution(
            "timeout",
            0.85,
            True,
            "platform",
            "Retry once with smaller scope, then degrade gracefully.",
        )
    if any(
        token in haystack
        for token in (
            "connection",
            "network",
            "dns",
            "connecterror",
            "502",
            "503",
            "504",
        )
    ):
        return ToolFailureAttribution(
            "network_error",
            0.8,
            True,
            "platform",
            "Retry with backoff or use cached context when available.",
        )
    if "fatal" in error_type or any(
        token in haystack
        for token in ("business rule", "conflict", "already exists")
    ):
        return ToolFailureAttribution(
            "business_rule",
            0.75,
            False,
            "business",
            "Explain the blocker and offer the next valid business action.",
        )
    if any(token in haystack for token in ("tool not found", "unknown tool", "unsupported")):
        return ToolFailureAttribution(
            "llm_planning",
            0.8,
            True,
            "planner",
            "Choose an available tool from the registry and replan.",
        )
    return ToolFailureAttribution(
        "unknown",
        0.45,
        True,
        "platform",
        "Retry once only if the action is safe; otherwise ask for clarification.",
    )
