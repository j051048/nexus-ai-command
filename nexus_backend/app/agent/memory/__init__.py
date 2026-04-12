"""
Hybrid Memory Manager for the LangGraph Agent.

Combines:
1. Short-term: Sliding window of recent messages (configurable size)
2. Long-term: Summary of older messages via LLM compression
3. Semantic: Vector search for relevant past context
4. Semantic Cache: Fast-path for repeated / similar queries
5. Query Transformation: HyDE and Multi-Query for better retrieval
6. Phase 2: TurboQuant compression for long conversation memory

This module is called BEFORE the graph runs to prepare the initial
message list, and AFTER the graph runs to persist results.

Sub-modules:
- compaction: Micro-compaction utilities (shrink old tool outputs / code blocks)
- token_window: Token-budget management, summarization, TurboQuant compression
- persistence: Post-graph message saving and memory extraction
- prepare: Pre-graph state building (cache, RAG, memory injection, conversion)
"""

from app.agent.memory.compaction import (
    micro_compact_messages,
    _strip_reasoning_from_history,
)
from app.agent.memory.persistence import persist_result
from app.agent.memory.prepare import prepare_initial_state

# Re-export for backward compatibility with test mocks that patch
# "app.agent.memory.ChatService" (the old flat-file location).
from app.services.chat_service import ChatService as ChatService  # noqa: F401
from app.agent.memory.token_window import (
    HARD_TURN_LIMIT,
    SHORT_TERM_WINDOW,
    compress_old_messages,
    decompress_message_embedding,
    trim_messages_to_window,
)

__all__ = [
    # Primary API (used by external modules)
    "prepare_initial_state",
    "persist_result",
    # Compaction
    "micro_compact_messages",
    "_strip_reasoning_from_history",
    # Token window
    "trim_messages_to_window",
    "compress_old_messages",
    "decompress_message_embedding",
    "SHORT_TERM_WINDOW",
    "HARD_TURN_LIMIT",
]
