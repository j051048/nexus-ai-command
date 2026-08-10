"""Deterministic Markdown format linting for generated artifacts.

Checks the structural quality that a regex/character-count rule evaluator
misses: table column consistency, heading-level jumps, list marker mixing,
empty-paragraph density and citation marker shape.  Pure and side-effect
free so it can run in CI and inside the quality pipeline.
"""

from __future__ import annotations

import re
from typing import Any

FORMAT_LINT_VERSION = "artifact-format-lint.v1"

_TABLE_ROW_RE = re.compile(r"^\s*\|")
_HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
_CITATION_RE = re.compile(r"\[\[([A-Za-z0-9_-]{1,64})\]\]")
_FENCE_RE = re.compile(r"^```", re.MULTILINE)
_EMPTY_LINE_RE = re.compile(r"\n\s*\n\s*\n")


def _table_columns(line: str) -> int:
    return len([cell for cell in line.strip().strip("|").split("|")])


def lint_markdown_format(text: str) -> dict[str, Any]:
    """Return a format score (0-100) plus findings."""
    text = str(text or "")
    lines = text.splitlines()
    findings: list[dict[str, Any]] = []

    # 1. Table column consistency (skip separator rows like |---|---|).
    previous_table_columns: int | None = None
    for index, line in enumerate(lines, 1):
        if not _TABLE_ROW_RE.match(line):
            continue
        columns = _table_columns(line)
        if re.match(r"^\s*\|[\s:\-|]+\|\s*$", line):
            continue
        if previous_table_columns is not None and columns != previous_table_columns:
            findings.append(
                {
                    "severity": "medium",
                    "code": "table_column_mismatch",
                    "message": f"表格在第 {index} 行列数不一致",
                    "details": {"line": index, "columns": columns},
                }
            )
        previous_table_columns = columns

    # 2. Heading-level jumps (## -> #### without ###).
    previous_level: int | None = None
    for index, line in enumerate(lines, 1):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        level = len(match.group(1))
        if previous_level is not None and level > previous_level + 1:
            findings.append(
                {
                    "severity": "medium",
                    "code": "heading_level_jump",
                    "message": f"标题层级跳级：从 H{previous_level} 直接跳到 H{level}",
                    "details": {"line": index, "level": level},
                }
            )
        previous_level = level

    # 3. List marker mixing.
    list_markers: set[str] = set()
    for line in lines:
        stripped = line.lstrip()
        if re.match(r"^[-*+]\s+", stripped) and not re.match(r"^\*\*", stripped):
            list_markers.add(stripped[0])
    if len(list_markers) > 1:
        findings.append(
            {
                "severity": "low",
                "code": "list_marker_mixed",
                "message": f"列表符号混用：{', '.join(sorted(list_markers))}",
                "details": {"markers": sorted(list_markers)},
            }
        )

    # 4. Fenced code blocks must be balanced.
    fences = len(_FENCE_RE.findall(text))
    if fences % 2 != 0:
        findings.append(
            {
                "severity": "high",
                "code": "unbalanced_code_fence",
                "message": "代码块围栏未闭合",
            }
        )

    # 5. Triple blank lines (sign of sloppy generation).
    blank_runs = len(_EMPTY_LINE_RE.findall(text))
    if blank_runs:
        findings.append(
            {
                "severity": "low",
                "code": "excessive_blank_lines",
                "message": f"存在 {blank_runs} 处连续空行",
            }
        )

    # 6. Citation markers must follow the [[id]] shape when citations exist.
    malformed = re.findall(r"\[\[[^\]]{0,1}\]\]", text)
    if malformed:
        findings.append(
            {
                "severity": "medium",
                "code": "malformed_citation_marker",
                "message": f"发现 {len(malformed)} 处格式异常的引用标记",
            }
        )

    deductions: dict[str, float] = {
        "high": 25.0,
        "medium": 10.0,
        "low": 4.0,
    }
    score = max(0.0, 100.0 - sum(deductions[f["severity"]] for f in findings))
    return {
        "evaluator_version": FORMAT_LINT_VERSION,
        "score": round(score, 2),
        "findings": findings,
    }
