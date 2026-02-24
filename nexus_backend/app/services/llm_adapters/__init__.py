"""
LLM Model Adaptation Gateway - Adapter Package

Exports the registry and base classes for all LLM adapters.
"""

from app.services.llm_adapters.base import (
    BaseModelAdapter,
    ChatRequest,
    ChatResponse,
    EmbeddingResponse,
    ModelConfig,
)
from app.services.llm_adapters.registry import adapter_registry, get_adapter

__all__ = [
    "BaseModelAdapter",
    "ModelConfig",
    "ChatRequest",
    "ChatResponse",
    "EmbeddingResponse",
    "adapter_registry",
    "get_adapter",
]
