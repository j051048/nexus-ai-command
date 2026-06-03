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

from app.core.config import FORCED_CHAT_MODEL, settings
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


def get_llm(
    org_id: str = None,
    model: str = None,
    model_tier: str = None,
    resolved_config: dict | None = None,
    **kwargs,
):
    """
    Provide a LangChain-compatible LLM instance with multi-tenant isolation.

    This compatibility helper is intentionally fail-closed. It only creates
    a LangChain client from a config already resolved by the LLM Gateway, or
    from the gateway's short-lived model cache. It must not read global API
    keys directly because that can bypass tenant routing and schedule rules.

    Args:
        org_id: Tenant organization ID for config resolution.
        model: Explicit model code (e.g. ``deepseek-v4-flash``).
        model_tier: Shorthand tier — all tiers map to the configured
                    low-cost default by policy.  Ignored when *model*
                    is explicitly provided.
        resolved_config: Dict returned by ``resolve_model_config``.
        **kwargs: Passed through to ``ChatOpenAI`` (e.g. ``temperature``,
                  ``timeout``, ``streaming``).
    """
    from app.services.llm_helpers import get_langchain_llm_sync

    # Resolve model_tier shorthand
    default_model = FORCED_CHAT_MODEL
    _TIER_MAP = {
        "mini": default_model,
        "economy": default_model,
        "balanced": default_model,
        "power": default_model,
        "flagship": default_model,
    }
    resolved_model = model or _TIER_MAP.get(model_tier or "") or default_model

    if resolved_config:
        return get_langchain_llm_sync(
            api_key=resolved_config["api_key"],
            base_url=resolved_config["base_url"],
            model=FORCED_CHAT_MODEL,
            temperature=resolved_config.get(
                "temperature", kwargs.pop("temperature", 0.7)
            ),
            streaming=kwargs.pop("streaming", False),
            timeout=resolved_config.get("timeout", kwargs.pop("timeout", 60.0)),
            **kwargs,
        )

    if org_id:
        cache_key = f"{org_id}:{resolved_model}"
        cached = llm_gateway._model_cache.get(cache_key)
        if cached:
            config_obj, _loaded_at = cached
            import time

            if time.time() - _loaded_at < llm_gateway._CACHE_TTL:
                return get_langchain_llm_sync(
                    api_key=config_obj.api_key,
                    base_url=config_obj.api_base_url,
                    model=FORCED_CHAT_MODEL,
                    temperature=config_obj.default_temperature,
                    streaming=kwargs.pop("streaming", False),
                    timeout=getattr(config_obj, "timeout_ms", 60000) / 1000,
                    **kwargs,
                )

    raise RuntimeError(
        "get_llm requires resolved_config or a warm tenant model cache. "
        "Use await resolve_model_config(...) before creating LangChain clients."
    )
