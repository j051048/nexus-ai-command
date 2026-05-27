"""
Token-window management for the Hybrid Memory Manager.

Handles context window limits, token counting, message trimming,
TurboQuant compression, and LLM-based summarization.
"""

import asyncio
import logging

from app.agent.state import AgentConfig
from app.services.token_service import token_counter

logger = logging.getLogger(__name__)

# Configurable window size
from app.core.config import settings

SHORT_TERM_WINDOW = getattr(settings, "MAX_CHAT_HISTORY", 10)

# Absolute turn limit — safety net before any LLM-based compaction.
# Prevents runaway token costs on very long sessions.
HARD_TURN_LIMIT = settings.TOKEN_HARD_TURN_LIMIT

# Quick token estimation: chars/4 + 20% safety margin (OpenClaw-inspired)
# Used as fast pre-check before expensive precise token counting
_TOKEN_ESTIMATE_RATIO = 4
_TOKEN_SAFETY_MARGIN = 1.2

# Default context window sizes per model family (in tokens)
_MODEL_CONTEXT_WINDOWS = {
    "deepseek-v4-flash": 128000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-3.5-turbo": 16385,
}
_DEFAULT_CONTEXT_WINDOW = settings.TOKEN_DEFAULT_CONTEXT_WINDOW


# ── Phase 2: TurboQuant Memory Compression ────────────────────────────────────


async def compress_old_messages(
    messages: list[dict[str, str]], preserve_recent: int = 10
) -> list[dict[str, str]]:
    """Phase 2: Compress embeddings in old messages using TurboQuant (5x memory reduction)"""
    if len(messages) <= preserve_recent:
        return messages

    try:
        from app.services.vector_service import VectorService

        compressed = []
        for i, msg in enumerate(messages):
            if i < len(messages) - preserve_recent and "embedding" in msg:
                # Quantize old message embeddings
                embedding = msg["embedding"]
                if isinstance(embedding, list) and len(embedding) == 1536:
                    quantized = VectorService.quantize_embedding(embedding)
                    msg["embedding_quantized"] = quantized
                    del msg["embedding"]  # Remove full precision
                    logger.debug(f"Compressed message {i} embedding")
            compressed.append(msg)
        return compressed
    except Exception as e:
        logger.debug(f"Memory compression skipped: {e}")
        return messages


async def decompress_message_embedding(msg: dict) -> dict:
    """Phase 2: Decompress quantized embedding when needed"""
    if "embedding_quantized" in msg and "embedding" not in msg:
        try:
            from app.services.vector_service import VectorService

            msg["embedding"] = VectorService.dequantize_embedding(
                msg["embedding_quantized"]
            )
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
    return msg


async def trim_messages_to_window(
    messages: list[dict[str, str]],
    config: AgentConfig,
    threshold_ratio: float = 0.80,
) -> list[dict[str, str]]:
    """
    Token window management: when the total token count of *messages* exceeds
    ``threshold_ratio`` (default 80 %) of the model's context window, the
    earliest non-system messages are summarised into a single compact summary
    message, keeping the conversation within budget.

    Steps:
      1. Count total tokens via ``token_counter``.
      2. If under threshold → return messages unchanged.
      3. Otherwise, split into *older* and *recent* halves, summarise the
         older portion with ``_summarize_messages``, and prepend the summary
         as a system message.

    Returns:
        A (potentially shortened) message list that fits within the window.
    """
    model = config.model or "deepseek-v4-flash"
    context_window = _MODEL_CONTEXT_WINDOWS.get(model, _DEFAULT_CONTEXT_WINDOW)
    token_limit = int(context_window * threshold_ratio)

    # Fast pre-check: estimate tokens via chars/4 + safety margin
    # Avoids expensive precise counting when clearly under budget
    total_chars = sum(len(m.get("content", "")) for m in messages)
    estimated_tokens = int(total_chars / _TOKEN_ESTIMATE_RATIO * _TOKEN_SAFETY_MARGIN)
    if estimated_tokens <= token_limit:
        return messages

    total_tokens = token_counter.count_messages_tokens(messages, model)
    if total_tokens <= token_limit:
        return messages

    logger.info(
        f"[Memory] Token window exceeded: {total_tokens}/{token_limit} "
        f"({total_tokens / context_window:.0%} of {context_window}). "
        f"Compressing early messages."
    )

    # Separate system messages (index 0 is usually the main system prompt)
    # and keep at least the last SHORT_TERM_WINDOW messages intact.
    keep_count = max(SHORT_TERM_WINDOW, 2)
    if len(messages) <= keep_count:
        return messages  # Nothing to trim

    older = messages[:-keep_count]
    recent = messages[-keep_count:]

    # Only summarise non-system older messages
    non_system_older = [m for m in older if m.get("role") != "system"]
    system_older = [m for m in older if m.get("role") == "system"]

    summary = await _summarize_messages(non_system_older, config)
    trimmed: list[dict[str, str]] = []

    # Preserve original system messages
    trimmed.extend(system_older)

    if summary:
        trimmed.append(
            {
                "role": "system",
                "content": f"[对话历史摘要 — 早期 {len(non_system_older)} 条消息已压缩] {summary}",
            }
        )

    trimmed.extend(recent)

    new_tokens = token_counter.count_messages_tokens(trimmed, model)
    logger.info(
        f"[Memory] Trimmed from {total_tokens} to {new_tokens} tokens ({len(messages)} → {len(trimmed)} messages)"
    )
    return trimmed


async def _summarize_messages(
    messages: list[dict[str, str]],
    config: AgentConfig,
) -> str | None:
    """Three-level compaction pipeline (inspired by OpenClaw compaction.ts).

    Level 1: LLM chunk summarization with retry + exponential backoff
    Level 2: Filter oversized messages → retry with smaller input
    Level 3: Simple truncation fallback (no LLM)

    Preserves active tasks and last user request across all levels.
    """
    if not messages:
        return None

    # --- Level 1: LLM summarization with retry ---
    for attempt in range(3):
        try:
            from app.services.summary_service import summary_service

            # Split into chunks if too large (OpenClaw: independent chunk summaries)
            chunk_size = 15
            if len(messages) <= chunk_size:
                result = await summary_service.summarize_messages(
                    messages,
                    config={
                        "api_key": config.api_key,
                        "base_url": config.base_url,
                        "model": config.mini_model,
                    },
                )
                if result:
                    return result
            else:
                # Stage summarization: chunk independently then merge
                chunk_summaries = []
                for i in range(0, len(messages), chunk_size):
                    chunk = messages[i : i + chunk_size]
                    chunk_result = await summary_service.summarize_messages(
                        chunk,
                        config={
                            "api_key": config.api_key,
                            "base_url": config.base_url,
                            "model": config.mini_model,
                        },
                    )
                    if chunk_result:
                        chunk_summaries.append(chunk_result)

                if chunk_summaries:
                    return " | ".join(chunk_summaries)

        except Exception as e:
            wait = 2**attempt
            logger.warning(
                f"[Memory] Summarization attempt {attempt + 1}/3 failed: {e}, retry in {wait}s"
            )
            if attempt < 2:
                await asyncio.sleep(wait)
            continue

    # --- Level 2: Filter oversized messages, retry with smaller input ---
    try:
        from app.services.summary_service import summary_service

        # Remove messages longer than 500 chars (likely tool results / RAG dumps)
        filtered = [m for m in messages if len(m.get("content", "")) <= 500]
        if filtered and len(filtered) >= 2:
            result = await summary_service.summarize_messages(
                filtered[-10:],
                config={
                    "api_key": config.api_key,
                    "base_url": config.base_url,
                    "model": config.mini_model,
                },
            )
            if result:
                return result
    except Exception as e:
        logger.warning(f"[Memory] Level-2 summarization failed: {e}")

    # --- Level 3: Simple truncation (no LLM, never fails) ---
    try:
        texts = []
        for msg in messages[-5:]:
            role_label = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")[:100]
            texts.append(f"{role_label}: {content}")
        return "历史摘要(截断): " + " | ".join(texts)
    except Exception:
        return None
