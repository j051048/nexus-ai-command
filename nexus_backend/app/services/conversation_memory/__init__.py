"""
Conversation Memory package.

Re-exports ConversationMemoryService and EpisodicMemoryService along with
their singleton instances, so all existing imports continue to work.
"""

from .episodic import EpisodicMemoryService
from .service import ConversationMemoryService

# Global service instances
conversation_memory_service = ConversationMemoryService()
episodic_memory_service = EpisodicMemoryService()

__all__ = [
    "ConversationMemoryService",
    "EpisodicMemoryService",
    "conversation_memory_service",
    "episodic_memory_service",
]

