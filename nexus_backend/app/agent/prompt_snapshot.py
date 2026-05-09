"""Prompt snapshot utilities for regression gates and trace metadata."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.agent.context_ledger import MOJIBAKE_MARKERS


@dataclass
class PromptBlockSnapshot:
    index: int
    role: str
    block_name: str
    tokens_estimated: int
    sha256: str
    chars: int
    mojibake_risk: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PromptSnapshot:
    prompt_version: str
    total_tokens_estimated: int
    total_chars: int
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    blocks: list[PromptBlockSnapshot] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        for block in self.blocks:
            digest.update(block.sha256.encode("ascii"))
        return digest.hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_version": self.prompt_version,
            "fingerprint": self.fingerprint,
            "total_tokens_estimated": self.total_tokens_estimated,
            "total_chars": self.total_chars,
            "created_at": self.created_at,
            "warnings": self.warnings,
            "blocks": [block.to_dict() for block in self.blocks],
        }


def _estimate_tokens(text: str) -> int:
    try:
        from app.services.token_service import token_counter

        return token_counter.count_tokens(text)
    except Exception:
        return max(1, len(text) // 4)


def _message_role(message: Any) -> str:
    role = getattr(message, "type", None) or getattr(message, "role", None)
    if role:
        return str(role)
    return message.__class__.__name__.replace("Message", "").lower()


def _message_content(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    return str(content)


def _block_name(text: str, fallback: str) -> str:
    stripped = text.strip()
    if stripped.startswith("[") and "]" in stripped[:80]:
        return stripped[1 : stripped.index("]")]
    if stripped.startswith("##"):
        return stripped.splitlines()[0].lstrip("# ").strip()[:80]
    return fallback


def build_prompt_snapshot(
    messages: list[Any],
    *,
    prompt_version: str = "runtime",
    max_total_tokens: int | None = None,
) -> PromptSnapshot:
    blocks: list[PromptBlockSnapshot] = []
    total_tokens = 0
    total_chars = 0
    seen_hashes: dict[str, int] = {}
    warnings: list[str] = []

    for idx, message in enumerate(messages):
        text = _message_content(message)
        tokens = _estimate_tokens(text)
        digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
        mojibake_risk = any(marker in text for marker in MOJIBAKE_MARKERS)
        if mojibake_risk:
            warnings.append(f"block[{idx}] has mojibake markers")
        if digest in seen_hashes:
            warnings.append(f"block[{idx}] duplicates block[{seen_hashes[digest]}]")
        else:
            seen_hashes[digest] = idx

        blocks.append(
            PromptBlockSnapshot(
                index=idx,
                role=_message_role(message),
                block_name=_block_name(text, f"message_{idx}"),
                tokens_estimated=tokens,
                sha256=digest,
                chars=len(text),
                mojibake_risk=mojibake_risk,
            )
        )
        total_tokens += tokens
        total_chars += len(text)

    if max_total_tokens is not None and total_tokens > max_total_tokens:
        warnings.append(
            f"prompt token budget exceeded: {total_tokens}>{max_total_tokens}"
        )

    return PromptSnapshot(
        prompt_version=prompt_version,
        total_tokens_estimated=total_tokens,
        total_chars=total_chars,
        blocks=blocks,
        warnings=warnings,
    )
