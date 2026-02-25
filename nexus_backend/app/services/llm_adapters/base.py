"""
LLM Model Adaptation Gateway - Base Adapter
Defines abstract base classes and data structures for all LLM adapters.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    """Configuration for a specific LLM model instance."""

    model_code: str
    model_name: str
    provider_type: str  # openai_compatible / wenxin / tongyi / hunyuan
    api_base_url: str
    api_key: str  # Already decrypted
    secret_key: str | None = None
    model_id: str = ""
    timeout_ms: int = 60000
    max_retries: int = 2
    max_tokens: int | None = None
    context_window: int | None = None
    supports_tools: bool = True
    supports_streaming: bool = True
    default_temperature: float = 0.7
    default_top_p: float = 0.9


@dataclass
class ChatRequest:
    """Unified chat request across all adapters."""

    scene_code: str
    agent_code: str
    user_id: str
    system_prompt: str
    messages: list[dict]
    tools: list[dict] | None = None
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    request_id: str | None = None


@dataclass
class ChatResponse:
    """Unified chat response across all adapters."""

    request_id: str
    model_code: str
    content: str
    tool_calls: list[dict] | None = None
    usage: dict = field(default_factory=lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "call_cost": 0.0,
    })
    exec_time_ms: int = 0
    finish_reason: str = "stop"  # stop / tool_calls / length / error
    raw_response: dict | None = None


@dataclass
class EmbeddingResponse:
    """Unified embedding response across all adapters."""

    request_id: str
    model_code: str
    embeddings: list[list[float]] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {
        "input_tokens": 0,
        "total_tokens": 0,
        "call_cost": 0.0,
    })
    exec_time_ms: int = 0


class BaseModelAdapter(ABC):
    """
    Abstract base class for all LLM model adapters.

    Each adapter translates the unified ChatRequest/ChatResponse format
    to/from the provider-specific API format.
    """

    def __init__(self, config: ModelConfig):
        self.config = config

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a chat completion request and return the full response."""
        ...

    @abstractmethod
    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatResponse]:
        """Send a chat completion request and stream partial responses."""
        ...

    @abstractmethod
    async def embedding(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings for a list of texts."""
        ...

    @abstractmethod
    async def test_connectivity(self) -> dict:
        """
        Test connectivity to the model provider.
        Returns dict with keys: success (bool), latency_ms (int), error (str|None)
        """
        ...

    def _build_timeout(self) -> float:
        """Convert timeout_ms config to seconds for httpx."""
        return self.config.timeout_ms / 1000.0
