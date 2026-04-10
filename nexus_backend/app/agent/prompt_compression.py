"""
Prompt Compression — Compress conversation history to reduce token usage.

When conversation history exceeds a threshold (turns > N or tokens > T),
compresses older messages into a summary while preserving recent context.

Strategy:
1. Keep the most recent K turns (default 3) intact
2. Summarize all older turns into a concise LLM-generated summary
3. Return compressed message list: [system, summary, ...recent_turns]
"""

import logging
import re

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

logger = logging.getLogger(__name__)

# Default thresholds for triggering compression
DEFAULT_MAX_TURNS_BEFORE_COMPRESS = 6
DEFAULT_MAX_TOKENS_BEFORE_COMPRESS = 4500
DEFAULT_KEEP_RECENT_TURNS = 3

# Micro-compaction thresholds for LangChain messages (P0)
_LC_TOOL_RESULT_THRESHOLD = 1200
_LC_ASSISTANT_MSG_THRESHOLD = 3000
_LC_CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
_LC_MICRO_COMPACT_RECENT_TURNS = 3


def _micro_compact_lc_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Micro-compact LangChain BaseMessage list (P0).

    Shrinks old tool outputs and long assistant messages while preserving
    the most recent N turns intact.  Operates on LangChain message types.
    """
    if len(messages) < _LC_MICRO_COMPACT_RECENT_TURNS * 2:
        return messages

    # Find boundary: protect last N turns
    turns_found = 0
    boundary = len(messages)
    for idx in range(len(messages) - 1, -1, -1):
        if isinstance(messages[idx], HumanMessage):
            turns_found += 1
            if turns_found >= _LC_MICRO_COMPACT_RECENT_TURNS:
                boundary = idx
                break

    result: list[BaseMessage] = []
    original_chars = 0
    compacted_chars = 0

    for i, msg in enumerate(messages):
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        original_chars += len(content)

        if i >= boundary:
            # Recent window — keep as-is
            result.append(msg)
            compacted_chars += len(content)
            continue

        # Older messages — compact
        if isinstance(msg, SystemMessage) and len(content) > _LC_TOOL_RESULT_THRESHOLD:
            # Tool result / context injection — summarize
            lines = content.split("\n", 3)
            first_line = lines[0][:120] if lines else content[:120]
            line_count = content.count("\n") + 1
            new_content = (
                f"[已执行, {line_count} 行 / {len(content)} 字符] {first_line}..."
            )
            result.append(SystemMessage(content=new_content))
            compacted_chars += len(new_content)
        elif isinstance(msg, AIMessage) and len(content) > _LC_ASSISTANT_MSG_THRESHOLD:
            # Long assistant message — compact code blocks + truncate
            new_content = _LC_CODE_BLOCK_RE.sub(_lc_code_replacer, content)
            if len(new_content) > _LC_ASSISTANT_MSG_THRESHOLD:
                head = _LC_ASSISTANT_MSG_THRESHOLD * 2 // 3
                tail = _LC_ASSISTANT_MSG_THRESHOLD // 3
                new_content = (
                    new_content[:head]
                    + f"\n...(原文 {len(content)} 字符, 已省略)...\n"
                    + new_content[-tail:]
                )
            result.append(AIMessage(content=new_content))
            compacted_chars += len(new_content)
        else:
            result.append(msg)
            compacted_chars += len(content)

    if compacted_chars < original_chars:
        saved = original_chars - compacted_chars
        logger.info(
            f"[MicroCompact-LC] {len(messages)} msgs: "
            f"{original_chars} → {compacted_chars} chars (saved {saved})"
        )

    return result


def _lc_code_replacer(match):
    """Replace large code blocks with compact placeholders."""
    lang = match.group(1) or "code"
    code = match.group(2)
    if len(code) <= 1500:
        return match.group(0)
    line_count = code.count("\n") + 1
    code_lines = code.split("\n")
    preview = "\n".join(code_lines[:3])
    tail = "\n".join(code_lines[-2:])
    return f"```{lang}\n{preview}\n... ({line_count} 行, 已省略) ...\n{tail}\n```"


def _count_tokens_approx(text: str) -> int:
    """Token count — delegates to the canonical TokenCounter."""
    from app.services.token_service import token_counter

    return token_counter.count_tokens(text)


def _count_messages_tokens(messages: list[BaseMessage]) -> int:
    """Count approximate tokens across all messages."""
    total = 0
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        total += _count_tokens_approx(content) + 4  # overhead per message
    return total


def _count_turns(messages: list[BaseMessage]) -> int:
    """Count conversation turns (human-AI pairs)."""
    return sum(1 for m in messages if isinstance(m, HumanMessage))


def _split_messages(
    messages: list[BaseMessage], keep_recent: int = DEFAULT_KEEP_RECENT_TURNS
) -> tuple[list[BaseMessage], list[BaseMessage], list[BaseMessage]]:
    """Split messages into system, older, and recent groups.

    Returns:
        (system_messages, older_messages, recent_messages)
    """
    system_msgs = []
    non_system = []

    for msg in messages:
        if isinstance(msg, SystemMessage):
            system_msgs.append(msg)
        else:
            non_system.append(msg)

    if not non_system:
        return system_msgs, [], []

    # Find the boundary: keep the last `keep_recent` human messages and their responses
    human_indices = [i for i, m in enumerate(non_system) if isinstance(m, HumanMessage)]

    if len(human_indices) <= keep_recent:
        # Not enough turns to split — keep everything
        return system_msgs, [], non_system

    # The cutoff: everything before the (N-keep_recent)th human message is "old"
    cutoff_idx = human_indices[-keep_recent]
    older = non_system[:cutoff_idx]
    recent = non_system[cutoff_idx:]

    return system_msgs, older, recent


def _build_conversation_text(messages: list[BaseMessage]) -> str:
    """将消息列表转换为可读的对话文本。"""
    conv_parts = []
    for msg in messages:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        if len(content) > 500:
            content = content[:500] + "..."

        if isinstance(msg, HumanMessage):
            conv_parts.append(f"用户: {content}")
        elif isinstance(msg, AIMessage):
            conv_parts.append(f"助手: {content}")
        else:
            conv_parts.append(f"[{msg.type}]: {content}")

    return "\n".join(conv_parts)


async def _update_summary(
    existing_summary: str,
    new_messages: list[BaseMessage],
    model: str = "gpt-4o-mini",
) -> str:
    """在已有摘要基础上增量更新，避免信息丢失。"""
    if not new_messages:
        return existing_summary

    new_conversation_text = _build_conversation_text(new_messages)

    update_prompt = f"""你需要在已有的对话摘要基础上进行增量更新。

已有摘要:
{existing_summary}

新增对话:
{new_conversation_text}

请按以下规则更新摘要：
1. 保留已有摘要中所有仍然相关的信息
2. 将"待处理"中已在新对话中完成的事项移到"已完成"
3. 添加新对话中出现的新信息
4. 严格使用以下格式输出：

## 目标
用户的主要目标和意图（1-2句）

## 已完成
- 已经完成的操作和获得的结果

## 关键决策
- 做出的重要决策和原因

## 待处理
- 尚未完成的事项

## 关键数据
- 重要的数字、名称、ID等不可丢失的信息

请保留所有关键事实和数字，不要遗漏。"""

    try:
        from openai import AsyncOpenAI

        from app.core.config import settings

        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.AI_BASE_URL,
        )

        import asyncio

        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": update_prompt}],
                max_tokens=500,
                temperature=0.3,
            ),
            timeout=10,
        )
        summary = response.choices[0].message.content.strip()
        logger.info(
            f"[PromptCompression] Incremental update: merged {len(new_messages)} new messages into existing summary"
        )
        return summary
    except Exception as e:
        logger.warning(
            f"[PromptCompression] Incremental update failed: {e}, appending new summary"
        )
        # Fallback: 在已有摘要后追加新消息的简单摘要
        fallback = await _summarize_messages(new_messages, model=model)
        return f"{existing_summary}\n\n[后续补充]\n{fallback}"


async def _summarize_messages(
    messages: list[BaseMessage],
    model: str = "gpt-4o-mini",
) -> str:
    """Use LLM to generate a structured summary of conversation messages."""
    if not messages:
        return ""

    conversation_text = _build_conversation_text(messages)

    summary_prompt = f"""请将以下对话历史压缩为结构化摘要。使用以下格式：

## 目标
用户的主要目标和意图（1-2句）

## 已完成
- 已经完成的操作和获得的结果

## 关键决策
- 做出的重要决策和原因

## 待处理
- 尚未完成的事项

## 关键数据
- 重要的数字、名称、ID等不可丢失的信息

对话历史:
{conversation_text}

请严格按照上述格式输出，保留所有关键事实和数字。"""

    try:
        from openai import AsyncOpenAI

        from app.core.config import settings

        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.AI_BASE_URL,
        )

        import asyncio

        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=300,
                temperature=0.3,
            ),
            timeout=10,
        )
        summary = response.choices[0].message.content.strip()
        logger.info(
            f"[PromptCompression] Compressed {len(messages)} messages "
            f"({_count_messages_tokens(messages)} tokens) → summary ({_count_tokens_approx(summary)} tokens)"
        )
        return summary
    except Exception as e:
        logger.warning(
            f"[PromptCompression] LLM summarization failed: {e}, using truncation fallback"
        )
        # Fallback: simple truncation — take first and last messages
        fallback_parts = []
        if messages:
            first_content = (
                messages[0].content
                if isinstance(messages[0].content, str)
                else str(messages[0].content)
            )
            fallback_parts.append(f"(对话开头) {first_content[:200]}")
        if len(messages) > 1:
            last_content = (
                messages[-1].content
                if isinstance(messages[-1].content, str)
                else str(messages[-1].content)
            )
            fallback_parts.append(f"(对话中间省略 {len(messages) - 2} 条消息)")
            fallback_parts.append(f"(最近一条) {last_content[:200]}")
        return " | ".join(fallback_parts)


def _deduplicate_consecutive_replies(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Collapse consecutive identical AI responses into one.

    When the LLM sees 3+ identical responses in history, it tends to repeat
    the same output (context pollution).  This function keeps only the last
    occurrence plus a short note, breaking the repetition pattern.
    """
    if len(messages) < 4:
        return messages

    result: list[BaseMessage] = []
    dup_count = 0
    prev_ai_content: str | None = None

    for msg in messages:
        if isinstance(msg, AIMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            # Normalize whitespace for comparison
            normalized = content.strip()
            if prev_ai_content is not None and normalized == prev_ai_content:
                dup_count += 1
                # Replace the previously appended duplicate with a skip note
                # (keep appending nothing — we'll add the final one at the end)
                continue
            else:
                if dup_count > 0:
                    # Insert a note about skipped duplicates before this new message
                    result.append(
                        SystemMessage(
                            content=f"[系统提示：上方助手回复重复了{dup_count}次，已折叠。请勿重复相同内容，需要生成不同的回答。]"
                        )
                    )
                    dup_count = 0
                prev_ai_content = normalized
        else:
            # Non-AI message — flush any pending duplicates
            if dup_count > 0:
                result.append(
                    SystemMessage(
                        content=f"[系统提示：上方助手回复重复了{dup_count}次，已折叠。请勿重复相同内容，需要生成不同的回答。]"
                    )
                )
                dup_count = 0
            prev_ai_content = None

        result.append(msg)

    # Flush trailing duplicates
    if dup_count > 0:
        result.append(
            SystemMessage(
                content=f"[系统提示：上方助手回复重复了{dup_count}次，已折叠。请勿重复相同内容，需要生成不同的回答。]"
            )
        )

    if len(result) < len(messages):
        logger.info(
            f"[PromptCompression] Deduplicated {len(messages) - len(result)} repeated AI messages"
        )

    return result


def _fix_orphaned_tool_pairs(messages: list[BaseMessage]) -> list[BaseMessage]:
    """移除压缩后孤立的 tool call/result 对。

    压缩可能导致 AIMessage（含 tool_calls）被摘要替换，
    但对应的 ToolMessage 仍留在 recent 区间，造成孤立。
    此函数清理这些不完整的配对。
    """
    # 收集所有 AIMessage 中的 tool_call_id
    valid_tool_call_ids: set[str] = set()
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
            for tc in msg.tool_calls or []:
                tc_id = tc.get("id", "")
                if tc_id:
                    valid_tool_call_ids.add(tc_id)

    # 过滤掉没有对应 tool_call 的 ToolMessage
    filtered = [
        msg
        for msg in messages
        if not isinstance(msg, ToolMessage)
        or getattr(msg, "tool_call_id", "") in valid_tool_call_ids
    ]

    removed = len(messages) - len(filtered)
    if removed > 0:
        logger.info(f"[PromptCompression] Removed {removed} orphaned ToolMessage(s)")

    return filtered


async def compress_conversation_history(
    messages: list[BaseMessage],
    max_tokens: int = DEFAULT_MAX_TOKENS_BEFORE_COMPRESS,
    model: str = "gpt-4o-mini",
    max_turns: int = DEFAULT_MAX_TURNS_BEFORE_COMPRESS,
    keep_recent: int = DEFAULT_KEEP_RECENT_TURNS,
) -> list[BaseMessage]:
    """
    Compress conversation history when it exceeds thresholds.

    Also deduplicates consecutive identical AI responses to prevent
    context pollution (where the LLM repeats a cached bad response).

    Args:
        messages: Full conversation message list
        max_tokens: Token threshold to trigger compression
        model: LLM model to use for summarization
        max_turns: Turn threshold to trigger compression
        keep_recent: Number of recent turns to preserve intact

    Returns:
        Compressed message list. If compression is not needed, returns original list unchanged.
    """
    if not messages:
        return messages

    # Step 0: Deduplicate consecutive identical AI responses
    messages = _deduplicate_consecutive_replies(messages)

    # Step 0b: Micro-compact old tool outputs and long assistant messages
    # (P0: lightweight first pass before expensive LLM summarization)
    messages = _micro_compact_lc_messages(messages)

    turn_count = _count_turns(messages)
    token_count = _count_messages_tokens(messages)

    # Check if compression is needed
    if turn_count <= max_turns and token_count <= max_tokens:
        return messages

    logger.info(
        f"[PromptCompression] Triggered: {turn_count} turns, ~{token_count} tokens "
        f"(thresholds: {max_turns} turns, {max_tokens} tokens)"
    )

    # Split into system, older, recent
    system_msgs, older_msgs, recent_msgs = _split_messages(messages, keep_recent)

    if not older_msgs:
        # Nothing to compress
        return messages

    # Check if there's an existing summary from a previous compression (iterative update)
    existing_summary = None
    for msg in system_msgs:
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        if "[对话历史摘要" in content:
            existing_summary = content
            break

    if existing_summary:
        # Incremental update mode: merge new messages into existing summary
        summary = await _update_summary(existing_summary, older_msgs, model=model)
        # Remove the old summary from system_msgs to avoid duplication
        system_msgs = [
            msg
            for msg in system_msgs
            if "[对话历史摘要"
            not in (msg.content if isinstance(msg.content, str) else str(msg.content))
        ]
    else:
        summary = await _summarize_messages(older_msgs, model=model)

    # Reconstruct compressed message list
    compressed = list(system_msgs)
    if summary:
        compressed.append(
            SystemMessage(
                content=f"[对话历史摘要（前 {len(older_msgs)} 条消息）]\n{summary}"
            )
        )
    compressed.extend(recent_msgs)

    new_token_count = _count_messages_tokens(compressed)
    logger.info(
        f"[PromptCompression] Compressed: {len(messages)} → {len(compressed)} messages, "
        f"~{token_count} → ~{new_token_count} tokens "
        f"(saved ~{token_count - new_token_count} tokens)"
    )

    # Fix orphaned tool call/result pairs caused by compression
    compressed = _fix_orphaned_tool_pairs(compressed)

    return compressed
