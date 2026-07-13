"""Static prompt linting for prompt/context regression gates."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass
from typing import Any

MOJIBAKE_MARKERS = ("锟斤拷", "�", "浣犲ソ", "閳?")


@dataclass
class PromptLintIssue:
    code: str
    severity: str
    message: str
    location: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "location": self.location,
        }


class PromptLinter:
    PLACEHOLDER_RE = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")
    CONFLICT_PAIRS = (("必须", "不要"), ("始终", "禁止"), ("always", "never"))

    def lint_text(
        self,
        text: str,
        *,
        location: str = "prompt",
        declared_variables: set[str] | None = None,
        max_characters: int = 80_000,
    ) -> list[PromptLintIssue]:
        issues: list[PromptLintIssue] = []
        if any(marker in text for marker in MOJIBAKE_MARKERS):
            issues.append(
                PromptLintIssue(
                    "mojibake",
                    "error",
                    "Prompt contains mojibake markers; source text must be UTF-8 clean.",
                    location,
                )
            )
        for placeholder in self.PLACEHOLDER_RE.findall(text):
            if placeholder not in {"{current_time}", "{preview}", "{user_input}"}:
                issues.append(
                    PromptLintIssue(
                        "unresolved_placeholder",
                        "warning",
                        f"Potential unresolved placeholder: {placeholder}",
                        location,
                    )
                )
        lower = text.lower()
        for a, b in self.CONFLICT_PAIRS:
            if a.lower() in lower and b.lower() in lower:
                issues.append(
                    PromptLintIssue(
                        "possible_instruction_conflict",
                        "warning",
                        f"Prompt contains both '{a}' and '{b}', review for conflicts.",
                        location,
                    )
                )
        if text.count("```gen-ui") > 1:
            issues.append(
                PromptLintIssue(
                    "duplicate_genui_protocol",
                    "warning",
                    "Prompt includes multiple gen-ui blocks/protocol fragments.",
                    location,
                )
            )
        fields = {
            field_name.split(".", 1)[0].split("[", 1)[0]
            for _, field_name, _, _ in string.Formatter().parse(text)
            if field_name
        }
        if declared_variables is not None:
            for field_name in sorted(fields - declared_variables):
                issues.append(
                    PromptLintIssue(
                        "undeclared_variable",
                        "error",
                        f"Prompt variable is not declared: {field_name}",
                        location,
                    )
                )
        if len(text) > max_characters:
            issues.append(
                PromptLintIssue(
                    "prompt_size_limit",
                    "error",
                    f"Prompt exceeds character budget ({len(text)} > {max_characters}).",
                    location,
                )
            )
        if "<untrusted" in text and "</untrusted" not in text:
            issues.append(
                PromptLintIssue(
                    "unclosed_untrusted_boundary",
                    "error",
                    "Untrusted context boundary is not closed.",
                    location,
                )
            )
        return issues

    def lint_artifact(self, artifact: Any) -> dict[str, Any]:
        issues = self.lint_text(
            artifact.content,
            location=f"artifact:{artifact.agent_code}:{artifact.version}",
            declared_variables=set(artifact.variables),
            max_characters=max(4_000, artifact.model_profile.max_input_tokens * 4),
        )
        return {
            "passed": not any(issue.severity == "error" for issue in issues),
            "content_hash": artifact.content_hash,
            "issues": [issue.to_dict() for issue in issues],
        }

    def lint_registry(self) -> dict[str, Any]:
        from app.core.prompts_registry import SYSTEM_PROMPTS, TOOL_PROMPTS

        issues: list[PromptLintIssue] = []
        for key, value in SYSTEM_PROMPTS.items():
            issues.extend(self.lint_text(value, location=f"system:{key}"))
        for key, value in TOOL_PROMPTS.items():
            issues.extend(self.lint_text(value, location=f"tool:{key}"))
        return {
            "total_issues": len(issues),
            "error_count": sum(1 for i in issues if i.severity == "error"),
            "warning_count": sum(1 for i in issues if i.severity == "warning"),
            "issues": [i.to_dict() for i in issues],
        }


prompt_linter = PromptLinter()
