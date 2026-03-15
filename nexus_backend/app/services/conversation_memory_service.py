"""
Backward-compatible shim.

All implementation has moved to ``app.services.conversation_memory`` package.
This module re-exports the service classes and singleton instances so that
existing ``from app.services.conversation_memory_service import ...`` imports
continue to work without modification.
"""

from app.services.conversation_memory import (  # noqa: F401
    ConversationMemoryService,
    EpisodicMemoryService,
    conversation_memory_service,
    episodic_memory_service,
)
