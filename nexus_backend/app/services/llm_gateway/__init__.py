"""
LLM Gateway Package

Composed from split modules:
- model_resolution: Config loading, schedule rule resolution, circuit breaker
- chat_dispatch: chat(), stream_chat(), embedding() public methods
- call_logging: Buffered batch-insert of call logs

The LLMGatewayService class uses cooperative multiple inheritance (mixins)
to combine all functionality into a single class with the same public API
as the original monolithic module.
"""

import time

from app.services.llm_adapters.base import ChatResponse, ModelConfig
from app.services.llm_gateway.call_logging import CallLoggingMixin
from app.services.llm_gateway.chat_dispatch import ChatDispatchMixin
from app.services.llm_gateway.model_resolution import ModelResolutionMixin


class LLMGatewayService(ModelResolutionMixin, ChatDispatchMixin, CallLoggingMixin):
    """
    Central hub for all LLM interactions.

    Resolves which model to use based on scene/agent schedule rules,
    manages caching, quota enforcement, circuit breaking, and logging.
    """

    # Batch log buffer settings
    _LOG_BATCH_SIZE = 10
    _LOG_FLUSH_INTERVAL = 5.0  # seconds

    def __init__(self):
        # Cache: key -> (value, loaded_at_timestamp)
        self._model_cache: dict[str, tuple[ModelConfig, float]] = {}
        self._schedule_cache: dict[str, tuple[dict, float]] = {}
        self._CACHE_TTL: int = 300  # 5 minutes
        # Batch log buffer
        self._log_buffer: list[dict] = []
        self._log_last_flush: float = time.time()

    @staticmethod
    def _error_response(
        request_id: str, model_code: str, error_msg: str
    ) -> ChatResponse:
        """Build a ChatResponse representing an error."""
        return ChatResponse(
            request_id=request_id,
            model_code=model_code,
            content="",
            tool_calls=None,
            usage={
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "call_cost": 0.0,
            },
            finish_reason="error",
            raw_response={"error": error_msg},
        )


# Module-level singleton
llm_gateway = LLMGatewayService()


def get_llm(org_id: str = None, model: str = None, model_tier: str = None, **kwargs):
    """
    Provide a LangChain-compatible LLM instance with multi-tenant isolation.

    When *org_id* is supplied, attempts to load the tenant-specific API key
    and base URL from the ``llm_model_config`` table via the gateway cache.
    Falls back to global settings only when tenant config is unavailable.

    Args:
        org_id: Tenant organization ID for config resolution.
        model: Explicit model code (e.g. ``gpt-4o-mini``).
        model_tier: Shorthand tier — ``"mini"`` maps to ``gpt-4o-mini``,
                    ``"power"`` maps to ``gpt-4o``.  Ignored when *model*
                    is explicitly provided.
        **kwargs: Passed through to ``ChatOpenAI`` (e.g. ``temperature``,
                  ``timeout``, ``streaming``).
    """
    from langchain_openai import ChatOpenAI

    from app.core.config import settings

    # Resolve model_tier shorthand
    _TIER_MAP = {"mini": "gpt-4o-mini", "economy": "gpt-4o-mini",
                 "balanced": "gpt-4o", "power": "gpt-4o",
                 "flagship": "gpt-4-turbo"}
    resolved_model = model or _TIER_MAP.get(model_tier or "", None) or "gpt-4o-mini"

    # Attempt tenant-specific config resolution (best-effort, sync-safe)
    api_key = settings.OPENAI_API_KEY
    base_url = settings.AI_BASE_URL

    if org_id:
        try:
            cache_key = f"{org_id}:{resolved_model}"
            cached = llm_gateway._model_cache.get(cache_key)
            if cached:
                config_obj, _loaded_at = cached
                if time.time() - _loaded_at < llm_gateway._CACHE_TTL:
                    api_key = config_obj.api_key or api_key
                    base_url = config_obj.api_base_url or base_url
                    resolved_model = config_obj.model_id or resolved_model
        except Exception:
            pass  # Fall through to global defaults

    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=resolved_model,
        **kwargs
    )
