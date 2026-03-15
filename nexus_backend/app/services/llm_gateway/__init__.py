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
    def _error_response(request_id: str, model_code: str, error_msg: str) -> ChatResponse:
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
