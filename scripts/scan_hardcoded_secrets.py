"""Fail CI when obvious production secrets are committed.

This intentionally stays small and deterministic. It is not a replacement for
hosted secret scanning; it catches the high-confidence patterns that should
never appear in source control while allowing test fixtures and placeholders.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {
    ".agents",
    ".codex",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "playwright-report",
    "test-results",
}

SKIP_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".lock",
    ".png",
    ".pyc",
    ".zip",
}

SKIP_FILENAMES = {
    ".env",
    ".env.local",
}

ALLOW_WORDS = (
    "dummy",
    "example",
    "fake",
    "placeholder",
    "sample",
    "test",
    "testing",
)

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_pat", re.compile(r"\bghp_[A-Za-z0-9_]{36,}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "private_key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
]


def _should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    if path.name in SKIP_FILENAMES or path.name.startswith(".env."):
        return True
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def _allowed(relative: Path, pattern_name: str, line: str) -> bool:
    lowered = line.lower()
    if any(word in lowered for word in ALLOW_WORDS):
        return True
    if pattern_name == "private_key" and "tests" in relative.parts:
        return True
    return False


def main() -> int:
    findings: list[str] = []

    for current_root, dirs, files in os.walk(ROOT):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        current = Path(current_root)
        for name in files:
            path = current / name
            relative = path.relative_to(ROOT)
            if _should_skip(relative):
                continue
            if path.stat().st_size > 1_000_000:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            except OSError:
                continue

            for line_no, line in enumerate(text.splitlines(), start=1):
                for pattern_name, pattern in PATTERNS:
                    if _allowed(relative, pattern_name, line):
                        continue
                    if pattern.search(line):
                        findings.append(f"{relative}:{line_no}: {pattern_name}")

    if findings:
        print("HARDCODED_SECRET_SCAN_FAIL")
        for finding in findings[:50]:
            print(f" - {finding}")
        if len(findings) > 50:
            print(f" - ... {len(findings) - 50} more")
        return 1

    print("HARDCODED_SECRET_SCAN_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
