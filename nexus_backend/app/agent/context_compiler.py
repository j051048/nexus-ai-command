"""Global context compiler for the final LLM request.

Every prompt block competes inside one budget. Mandatory policy/tool blocks are
reserved first; contextual blocks are selected by utility and retain source
identifiers so final answers can be traced back to evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage, SystemMessage

from app.services.token_service import TokenCounter

_token_counter = TokenCounter()


@dataclass(frozen=True)
class ContextCompilePolicy:
    max_input_tokens: int = 32_000
    reserved_output_tokens: int = 2_000
    reserved_history_tokens: int = 4_000
    minimum_context_tokens: int = 1_000
    reserved_tool_tokens: int = 0
    model: str = "deepseek-v4-flash"

    @property
    def system_budget(self) -> int:
        return max(
            0,
            self.max_input_tokens
            - self.reserved_output_tokens
            - self.reserved_history_tokens
            - self.reserved_tool_tokens,
        )


class ContextBudgetExceeded(ValueError):  # noqa: N818 - public exception contract
    """Required instructions and the current conversation cannot fit safely."""


def context_message(
    content: str, *, kind: str, source_ids: Iterable[str] = ()
) -> SystemMessage:
    """Attach trusted producer metadata; document text never assigns authority."""
    return SystemMessage(
        content=content,
        additional_kwargs={
            "context_block": {"kind": kind, "source_ids": list(source_ids)}
        },
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
    conversation_tokens: int = 0
    tool_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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
        candidates = self._candidates(messages, ledger or {}, policy.model)
        conversation_tokens = sum(
            self._estimate_tokens(
                json.dumps(message.model_dump(), ensure_ascii=False, default=str),
                policy.model,
            )
            for message in messages
            if not isinstance(message, SystemMessage)
        )
        budget = max(
            0,
            policy.max_input_tokens
            - policy.reserved_output_tokens
            - max(policy.reserved_history_tokens, conversation_tokens)
            - policy.reserved_tool_tokens,
        )
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

        if (
            sum(candidate.tokens for candidate in mandatory) > budget
            or conversation_tokens
            + policy.reserved_output_tokens
            + policy.reserved_tool_tokens
            > policy.max_input_tokens
        ):
            raise ContextBudgetExceeded(
                "Required context exceeds the model input budget"
            )

        for candidate in [*mandatory, *optional]:
            remaining = budget - used
            if remaining <= 0:
                dropped.append(self._block(candidate, "global_budget"))
                continue
            if candidate.tokens <= remaining:
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
            budget_tokens=budget,
            used_tokens=used,
            included_blocks=included,
            dropped_blocks=dropped,
            evidence_ids=evidence_ids,
            fingerprint=digest,
            conversation_tokens=conversation_tokens,
            tool_tokens=policy.reserved_tool_tokens,
        )

    def _candidates(
        self,
        messages: Iterable[BaseMessage],
        ledger: dict[str, Any],
        model: str = "deepseek-v4-flash",
    ) -> list[ContextCandidate]:
        candidates: list[ContextCandidate] = []
        for index, message in enumerate(messages):
            if not isinstance(message, SystemMessage):
                continue
            content = str(message.content)
            block_name = self._block_name(content)
            lowered = content.lower()
            block = message.additional_kwargs.get("context_block") or {}
            kind = block.get("kind")
            # Legacy system instructions remain required until their producer is migrated.
            mandatory = kind not in {"evidence", "experience", "example", "summary"}
            utility = 0.45
            for hints, score in UTILITY_HINTS:
                if any(hint.lower() in lowered for hint in hints):
                    utility = max(utility, score)
            source_ids = set(str(item) for item in block.get("source_ids", []))
            source_ids.update(SOURCE_ID_RE.findall(content))
            candidates.append(
                ContextCandidate(
                    index=index,
                    content=content,
                    block_name=block_name,
                    tokens=self._estimate_tokens(content, model),
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
    def _estimate_tokens(content: str, model: str = "deepseek-v4-flash") -> int:
        # Reuse the warmed tokenizer, with headroom for provider-specific framing.
        return max(1, int(_token_counter.count_tokens(content, model) * 1.2) + 8)

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
