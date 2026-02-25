"""
LLM Model Adaptation Gateway - Adapter Registry

Maps provider_type codes to adapter classes.
Provides factory function to instantiate adapters from ModelConfig.
"""

import logging

from app.services.llm_adapters.base import BaseModelAdapter, ModelConfig

logger = logging.getLogger(__name__)

# Registry: provider_type -> adapter class
_ADAPTER_REGISTRY: dict[str, type[BaseModelAdapter]] = {}


def register_adapter(provider_type: str, adapter_class: type[BaseModelAdapter]):
    """Register an adapter class for a provider type."""
    _ADAPTER_REGISTRY[provider_type] = adapter_class
    logger.debug(f"Registered LLM adapter: {provider_type} -> {adapter_class.__name__}")


def get_adapter(provider_type: str, config: ModelConfig) -> BaseModelAdapter:
    """
    Instantiate and return the appropriate adapter for a provider type.

    Args:
        provider_type: The provider type code (e.g., 'openai_compatible', 'wenxin')
        config: The model configuration with decrypted API key

    Returns:
        An instance of the appropriate BaseModelAdapter subclass

    Raises:
        ValueError: If the provider_type is not registered
    """
    adapter_class = _ADAPTER_REGISTRY.get(provider_type)
    if not adapter_class:
        available = ", ".join(_ADAPTER_REGISTRY.keys()) or "(none)"
        raise ValueError(f"Unknown LLM adapter type: '{provider_type}'. " f"Available adapters: {available}")
    return adapter_class(config)


def list_adapters() -> dict[str, str]:
    """List all registered adapters. Returns {provider_type: class_name}."""
    return {k: v.__name__ for k, v in _ADAPTER_REGISTRY.items()}


# ---- Auto-register built-in adapters ----


def _auto_register():
    """Register all built-in adapters on import."""
    try:
        from app.services.llm_adapters.openai_compatible import OpenAICompatibleAdapter

        register_adapter("openai_compatible", OpenAICompatibleAdapter)
        # Also register common aliases
        register_adapter("openai", OpenAICompatibleAdapter)
        register_adapter("azure_openai", OpenAICompatibleAdapter)
        register_adapter("deepseek", OpenAICompatibleAdapter)
        register_adapter("moonshot", OpenAICompatibleAdapter)
        register_adapter("yi", OpenAICompatibleAdapter)
        register_adapter("zhipu", OpenAICompatibleAdapter)
        register_adapter("minimax", OpenAICompatibleAdapter)
    except ImportError as e:
        logger.warning(f"Failed to register OpenAI-compatible adapter: {e}")

    try:
        from app.services.llm_adapters.wenxin import WenxinAdapter

        register_adapter("wenxin", WenxinAdapter)
        register_adapter("ernie", WenxinAdapter)
        register_adapter("baidu", WenxinAdapter)
    except ImportError as e:
        logger.warning(f"Failed to register Wenxin adapter: {e}")

    try:
        from app.services.llm_adapters.tongyi import TongyiAdapter

        register_adapter("tongyi", TongyiAdapter)
        register_adapter("dashscope", TongyiAdapter)
        register_adapter("qwen", TongyiAdapter)
        register_adapter("alibaba", TongyiAdapter)
    except ImportError as e:
        logger.warning(f"Failed to register Tongyi adapter: {e}")

    try:
        from app.services.llm_adapters.hunyuan import HunyuanAdapter

        register_adapter("hunyuan", HunyuanAdapter)
        register_adapter("tencent", HunyuanAdapter)
    except ImportError as e:
        logger.warning(f"Failed to register Hunyuan adapter: {e}")


_auto_register()

# Public alias for convenience
adapter_registry = _ADAPTER_REGISTRY
