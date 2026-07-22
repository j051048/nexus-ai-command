"""Sanitize internal Agent traces before content reaches a customer artifact."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_INTERNAL_LINE_PATTERNS = (
    re.compile(
        r"^\s*\[(?:企业资料检索结果|知识检索结果|工具调用结果|TOOL_RESULT)\]\s*$", re.I
    ),
    re.compile(
        r"^\s*(?:tool_name|tool_args|tool_result|trace_id|chunk_id)\s*[:：]", re.I
    ),
    re.compile(r"^\s*```(?:json|tool|trace)\s*$", re.I),
)
_CITATION_RE = re.compile(r"\[EVID:([^:\]\s]+):([^\]\s]+)\]")
_RAW_MARKER_RE = re.compile(
    r"\[(?:企业资料检索结果|知识检索结果|工具调用结果|TOOL_RESULT)\]"
    r"|\b(?:tool_name|tool_args|tool_result|trace_id|chunk_id)\s*[:：]"
    r"|\[EVID:[^\]]+\]",
    re.I,
)
_TRACE_MARKER_RE = re.compile(
    r"\[(?:企业资料检索结果|知识检索结果|工具调用结果|TOOL_RESULT)\]"
    r"|\b(?:tool_name|tool_args|tool_result|trace_id|chunk_id)\s*[:：]",
    re.I,
)


@dataclass(frozen=True)
class SanitizedArtifact:
    content: str
    source_notes: list[dict[str, str]]
    removed_line_count: int
    duplicate_paragraph_count: int


def contains_internal_markers(text: str) -> bool:
    """Return whether text contains implementation details unsuitable for export."""

    return bool(_RAW_MARKER_RE.search(str(text or "")))


def contains_internal_trace_markers(text: str) -> bool:
    """Return whether non-citation Agent implementation details leaked."""

    return bool(_TRACE_MARKER_RE.search(str(text or "")))


def _normalized_paragraph(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE).lower()


def _evidence_lookup(
    evidence_packet: dict[str, Any] | None
) -> dict[tuple[str, str], dict[str, Any]]:
    records = (evidence_packet or {}).get("records") or []
    return {
        (str(item.get("document_id") or ""), str(item.get("chunk_id") or "")): item
        for item in records
        if item.get("document_id") and item.get("chunk_id")
    }


def sanitize_artifact_content(
    text: str,
    evidence_packet: dict[str, Any] | None = None,
    *,
    keep_citations: bool = False,
) -> SanitizedArtifact:
    """Remove trace leakage, collapse repeated passages and humanize citations.

    ``keep_citations`` is used by the deterministic quality gate. Customer-facing
    renderers use the default and receive stable ``[来源 N]`` references.
    """

    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    removed = 0
    cleaned_lines: list[str] = []
    in_internal_fence = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```") and in_internal_fence:
            in_internal_fence = False
            removed += 1
            continue
        if any(pattern.search(line) for pattern in _INTERNAL_LINE_PATTERNS):
            if stripped.startswith("```"):
                in_internal_fence = True
            removed += 1
            continue
        if in_internal_fence:
            removed += 1
            continue
        cleaned_lines.append(line.rstrip())

    # Deduplicate repeated retrieval passages while preserving headings and lists.
    paragraphs = re.split(r"\n\s*\n", "\n".join(cleaned_lines))
    seen: set[str] = set()
    deduplicated: list[str] = []
    duplicate_count = 0
    for paragraph in paragraphs:
        value = paragraph.strip()
        if not value:
            continue
        key = _normalized_paragraph(value)
        can_dedupe = len(key) >= 20 and not value.startswith(("#", "|"))
        if can_dedupe and key in seen:
            duplicate_count += 1
            continue
        if can_dedupe:
            seen.add(key)
        deduplicated.append(value)

    content = "\n\n".join(deduplicated).strip()
    lookup = _evidence_lookup(evidence_packet)
    source_numbers: dict[tuple[str, str], int] = {}
    source_notes: list[dict[str, str]] = []

    def replace_citation(match: re.Match[str]) -> str:
        key = (match.group(1), match.group(2))
        if keep_citations:
            return match.group(0)
        if key not in source_numbers:
            number = len(source_numbers) + 1
            source_numbers[key] = number
            item = lookup.get(key, {})
            source_notes.append(
                {
                    "number": str(number),
                    "document_id": key[0],
                    "chunk_id": key[1],
                    "title": str(item.get("title") or item.get("source") or "企业资料"),
                    "version": str(item.get("source_version") or "未标注版本"),
                }
            )
        return f"[来源 {source_numbers[key]}]"

    content = _CITATION_RE.sub(replace_citation, content)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    return SanitizedArtifact(
        content=content,
        source_notes=source_notes,
        removed_line_count=removed,
        duplicate_paragraph_count=duplicate_count,
    )


def duplicate_paragraph_ratio(text: str) -> float:
    paragraphs = [
        _normalized_paragraph(item)
        for item in re.split(r"\n\s*\n", str(text or ""))
        if len(_normalized_paragraph(item)) >= 20
    ]
    if not paragraphs:
        return 0.0
    return round(1.0 - len(set(paragraphs)) / len(paragraphs), 4)
