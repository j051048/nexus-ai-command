"""
Micro-Compaction utilities for the Hybrid Memory Manager.

Proactively shrink old tool outputs and long code blocks BEFORE the
expensive token-window trim kicks in.  This is the first line of
defence against context bloat.

Inspired by Claude Code S06: proactive context compaction.
"""

import logging
import re

logger = logging.getLogger(__name__)

# ─── Micro-Compaction (P0) ────────────────────────────────────────────────

# Messages within the most recent N turns are never micro-compacted.
MICRO_COMPACT_PRESERVE_RECENT = 3  # keep last 3 user-assistant pairs intact

# Per-message content thresholds (characters)
_TOOL_RESULT_TRUNCATE_THRESHOLD = 2000  # single tool_result max chars
_CODE_BLOCK_TRUNCATE_THRESHOLD = 1500  # code block max chars
_ASSISTANT_MSG_TRUNCATE_THRESHOLD = 3000  # assistant message max chars

# Regex patterns for micro-compaction
_CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)

# Regex to strip <think>...</think> blocks from historical assistant messages
_THINK_BLOCK_RE = re.compile(r"<think>[\s\S]*?</think>", re.DOTALL)


def _count_recent_turn_boundary(messages: list[dict[str, str]]) -> int:
    """Find the index where the 'recent N turns' begin (counting from end).

    A turn = one user message + its following assistant reply.
    Returns the index into *messages* such that messages[index:] contains
    the last MICRO_COMPACT_PRESERVE_RECENT turns.
    """
    turns_found = 0
    i = len(messages) - 1
    while i >= 0 and turns_found < MICRO_COMPACT_PRESERVE_RECENT:
        if messages[i].get("role") == "user":
            turns_found += 1
        i -= 1
    # i+1 is the start of the protected recent window
    return max(i + 1, 0)


def _compact_tool_result(content: str) -> str:
    """Shrink a tool result to a short summary placeholder."""
    if not content:
        return content
    # Extract tool name hint from common patterns like "[工具: xxx]" or "调用了 xxx"
    lines = content.split("\n", 3)
    first_line = lines[0][:120] if lines else content[:120]
    char_count = len(content)
    line_count = content.count("\n") + 1
    return f"[已执行工具, 返回 {line_count} 行 / {char_count} 字符] {first_line}..."


def _compact_code_blocks(content: str) -> str:
    """Replace large code blocks with compact placeholders."""

    def _replacer(match):
        lang = match.group(1) or "code"
        code = match.group(2)
        if len(code) <= _CODE_BLOCK_TRUNCATE_THRESHOLD:
            return match.group(0)  # keep small blocks
        line_count = code.count("\n") + 1
        # Keep first 3 and last 2 lines
        code_lines = code.split("\n")
        preview = "\n".join(code_lines[:3])
        tail = "\n".join(code_lines[-2:])
        return f"```{lang}\n{preview}\n... ({line_count} 行, 已省略中间部分) ...\n{tail}\n```"

    return _CODE_BLOCK_RE.sub(_replacer, content)


def _compact_long_assistant_msg(content: str) -> str:
    """Truncate overly long assistant messages, keeping head + tail."""
    if len(content) <= _ASSISTANT_MSG_TRUNCATE_THRESHOLD:
        return content
    # Compact code blocks first
    content = _compact_code_blocks(content)
    if len(content) <= _ASSISTANT_MSG_TRUNCATE_THRESHOLD:
        return content
    # Still too long — hard truncate with head + tail
    head_size = _ASSISTANT_MSG_TRUNCATE_THRESHOLD * 2 // 3
    tail_size = _ASSISTANT_MSG_TRUNCATE_THRESHOLD // 3
    return (
        content[:head_size]
        + f"\n\n... (原文 {len(content)} 字符, 已省略中间部分) ...\n\n"
        + content[-tail_size:]
    )


def micro_compact_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Apply micro-compaction to older messages in the conversation.

    Rules:
    1. Messages in the most recent N turns are NEVER touched.
    2. Older assistant messages: truncate long content, compact code blocks.
    3. Older tool-result-like system messages: replace with short summaries.
    4. Single tool_result exceeding threshold: truncate even in recent window.

    This runs BEFORE trim_messages_to_window as a lightweight first pass.
    """
    if len(messages) <= MICRO_COMPACT_PRESERVE_RECENT * 2:
        return messages  # too few messages to bother

    boundary = _count_recent_turn_boundary(messages)
    result = []

    for i, msg in enumerate(messages):
        role = msg.get("role", "")
        content = msg.get("content", "")

        if i >= boundary:
            # Recent window — only apply per-message size guard
            if (
                role == "assistant"
                and len(content) > _TOOL_RESULT_TRUNCATE_THRESHOLD * 2
            ):
                # Even recent messages get code-block compaction if huge
                new_content = _compact_code_blocks(content)
                result.append({**msg, "content": new_content})
            else:
                result.append(msg)
            continue

        # --- Older messages: aggressive compaction ---
        if role == "system":
            # Tool result injections often appear as system messages
            # with patterns like "[工具结果]" or very long structured data
            if len(content) > _TOOL_RESULT_TRUNCATE_THRESHOLD:
                result.append({**msg, "content": _compact_tool_result(content)})
            else:
                result.append(msg)
        elif role == "assistant":
            new_content = _compact_long_assistant_msg(content)
            result.append({**msg, "content": new_content})
        else:
            # User messages — keep as-is (they're usually short)
            result.append(msg)

    # Log compaction stats
    original_chars = sum(len(m.get("content", "")) for m in messages)
    compacted_chars = sum(len(m.get("content", "")) for m in result)
    if compacted_chars < original_chars:
        saved = original_chars - compacted_chars
        logger.info(
            f"[MicroCompact] Compacted {len(messages)} messages: "
            f"{original_chars} → {compacted_chars} chars (saved {saved}, "
            f"{saved * 100 // original_chars}%)"
        )

    return result


def _strip_reasoning_from_history(content: str) -> str:
    """Remove reasoning/thinking artifacts from historical assistant messages.

    Handles:
    - <think>...</think> blocks (DeepSeek-R1, QwQ)
    - Orphan <think> or </think> tags (partial streaming artifacts)
    """
    if not content:
        return content
    if "<think>" not in content and "</think>" not in content:
        return content
    cleaned = _THINK_BLOCK_RE.sub("", content)
    cleaned = cleaned.replace("<think>", "").replace("</think>", "")
    return cleaned.lstrip("\n")
