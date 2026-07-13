"""Global context compiler for the final LLM request.

Every prompt block competes inside one budget. Mandatory policy/tool blocks are
reserved first; contextual blocks are selected by utility and retain source
identifiers so final answers can be traced back to evidence.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage, SystemMessage


@dataclass(frozen=True)
class ContextCompilePolicy:
    max_input_tokens: int = 32_000
    reserved_output_tokens: int = 2_000
    reserved_history_tokens: int = 4_000
    minimum_context_tokens: int = 1_000

    @property
    def system_budget(self) -> int:
        return max(
            self.minimum_context_tokens,
            self.max_input_tokens
            - self.reserved_output_tokens
            - self.reserved_history_tokens,
        )


@dataclass
class ContextCandidate:
    index: int
    content: str
    block_name: str
    tokens: int
    mandatory: bool
    utility: float
    source_ids: list[str] = field(default_factory=list)


@dataclass
class ContextCompileReport:
    budget_tokens: int
    used_tokens: int
    included_blocks: list[dict[str, Any]]
    dropped_blocks: list[dict[str, Any]]
    evidence_ids: list[str]
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


MANDATORY_BLOCK_HINTS = (
    "prompt artifact",
    "prompt registry",
    "角色与工具",
    "安全",
    "权限",
    "确认",
    "policy",
    "permission",
    "security",
)

UTILITY_HINTS: tuple[tuple[tuple[str, ...], float], ...] = (
    (("业务规则", "business rule", "permission", "权限"), 1.0),
    (("检索到的参考知识", "rag", "evidence", "证据"), 0.92),
    (("上下文引擎", "business graph", "context engine"), 0.88),
    (("当前执行步骤", "验收标准", "task step"), 0.86),
    (("槽位", "slot"), 0.82),
    (("历史失败", "correction", "failure"), 0.72),
    (("参考示例", "few-shot", "example"), 0.58),
    (("对话摘要", "compacted", "summary"), 0.55),
)

SOURCE_ID_RE = re.compile(
    r"(?:source_id|evidence_id|memory_id|document_id)\s*[:=]\s*([\w.-]+)",
    re.IGNORECASE,
)


class ContextCompiler:
    def compile(
        self,
        messages: list[BaseMessage],
        *,
        policy: ContextCompilePolicy,
        ledger: dict[str, Any] | None = None,
    ) -> tuple[list[BaseMessage], ContextCompileReport]:
        candidates = self._candidates(messages, ledger or {})
        selected: set[int] = set()
        used = 0
        dropped: list[dict[str, Any]] = []

        mandatory = sorted(
            (candidate for candidate in candidates if candidate.mandatory),
            key=lambda candidate: candidate.index,
        )
        optional = sorted(
            (candidate for candidate in candidates if not candidate.mandatory),
            key=lambda candidate: (
                -candidate.utility,
                candidate.tokens,
                candidate.index,
            ),
        )

        for candidate in [*mandatory, *optional]:
            remaining = policy.system_budget - used
            if remaining <= 0:
                dropped.append(self._block(candidate, "global_budget"))
                continue
            if candidate.tokens <= remaining:
                selected.add(candidate.index)
                used += candidate.tokens
                continue
            if candidate.mandatory:
                selected.add(candidate.index)
                used += candidate.tokens
                continue
            dropped.append(self._block(candidate, "global_budget"))

        compiled = [
            message
            for index, message in enumerate(messages)
            if not isinstance(message, SystemMessage) or index in selected
        ]
        included = [
            self._block(candidate, None)
            for candidate in candidates
            if candidate.index in selected
        ]
        evidence_ids = sorted(
            {
                source_id
                for candidate in candidates
                if candidate.index in selected
                for source_id in candidate.source_ids
            }
        )
        digest = hashlib.sha256(
            "\n".join(
                str(getattr(message, "content", "")) for message in compiled
            ).encode("utf-8")
        ).hexdigest()
        return compiled, ContextCompileReport(
            budget_tokens=policy.system_budget,
            used_tokens=used,
            included_blocks=included,
            dropped_blocks=dropped,
            evidence_ids=evidence_ids,
            fingerprint=digest,
        )

    def _candidates(
        self, messages: Iterable[BaseMessage], ledger: dict[str, Any]
    ) -> list[ContextCandidate]:
        ledger_evidence = {
            str(item)
            for entry in ledger.get("entries", [])
            if entry.get("included")
            for item in entry.get("evidence_ids", [])
        }
        candidates: list[ContextCandidate] = []
        for index, message in enumerate(messages):
            if not isinstance(message, SystemMessage):
                continue
            content = str(message.content)
            block_name = self._block_name(content)
            lowered = content.lower()
            mandatory = index == 0 or any(
                hint in lowered for hint in MANDATORY_BLOCK_HINTS
            )
            utility = 0.45
            for hints, score in UTILITY_HINTS:
                if any(hint.lower() in lowered for hint in hints):
                    utility = max(utility, score)
            source_ids = set(SOURCE_ID_RE.findall(content))
            if any(
                hint in lowered
                for hint in ("context engine", "上下文引擎", "evidence", "证据", "rag")
            ):
                source_ids.update(ledger_evidence)
            candidates.append(
                ContextCandidate(
                    index=index,
                    content=content,
                    block_name=block_name,
                    tokens=self._estimate_tokens(content),
                    mandatory=mandatory,
                    utility=utility,
                    source_ids=sorted(source_ids),
                )
            )
        return candidates

    @staticmethod
    def _block_name(content: str) -> str:
        first_line = content.strip().splitlines()[0] if content.strip() else "system"
        return first_line.strip("[]【】 ")[:80] or "system"

    @staticmethod
    def _estimate_tokens(content: str) -> int:
        return max(1, (len(content) + 3) // 4)

    @staticmethod
    def _block(candidate: ContextCandidate, reason: str | None) -> dict[str, Any]:
        return {
            "block_name": candidate.block_name,
            "tokens": candidate.tokens,
            "mandatory": candidate.mandatory,
            "utility": candidate.utility,
            "source_ids": candidate.source_ids,
            "reason": reason,
        }


context_compiler = ContextCompiler()
