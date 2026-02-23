"""
P2 Enhancement: Streaming Response Service

Implements Server-Sent Events (SSE) for real-time AI responses.
Fixes Issue #16: Poor streaming UX with no progressive rendering.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class StreamEventType(Enum):
    """Types of streaming events."""

    TOKEN = "token"
    CHUNK = "chunk"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PROGRESS = "progress"
    ERROR = "error"
    DONE = "done"
    METADATA = "metadata"


@dataclass
class StreamEvent:
    """A single streaming event."""

    event_type: StreamEventType
    data: Any
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    sequence: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        """Convert to Server-Sent Event format."""
        payload = {
            "type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "metadata": self.metadata,
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(
            {
                "type": self.event_type.value,
                "data": self.data,
                "timestamp": self.timestamp,
                "sequence": self.sequence,
                "metadata": self.metadata,
            },
            ensure_ascii=False,
        )


class StreamingService:
    """
    P2 Enhancement: Real-time streaming for AI responses.

    Features:
    - Server-Sent Events (SSE) support
    - Progressive rendering
    - Thinking state streaming
    - Tool call progress
    - Error recovery
    - Backpressure handling
    """

    def __init__(self, chunk_size: int = 10, delay_ms: int = 20, max_buffer_size: int = 10000):
        self.chunk_size = chunk_size
        self.delay_ms = delay_ms
        self.max_buffer_size = max_buffer_size
        self._active_streams: dict[str, asyncio.Queue] = {}
        self._sequence_counters: dict[str, int] = {}

    async def create_stream(
        self, stream_id: str, llm_client: Any, messages: list, model: str = "gpt-4o-mini", **kwargs
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Create a streaming response from LLM.

        Args:
            stream_id: Unique identifier for this stream
            llm_client: LLM client with streaming support
            messages: Chat messages
            model: Model to use
            **kwargs: Additional LLM parameters

        Yields:
            StreamEvent objects
        """
        # Initialize stream
        queue = asyncio.Queue(maxsize=self.max_buffer_size)
        self._active_streams[stream_id] = queue
        self._sequence_counters[stream_id] = 0

        # Yield metadata event
        yield self._create_event(stream_id, StreamEventType.METADATA, {"model": model, "stream_id": stream_id})

        try:
            # Start LLM stream
            stream = await llm_client.chat.completions.create(model=model, messages=messages, stream=True, **kwargs)

            # Process stream
            accumulated = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    accumulated += token

                    # Yield token event
                    yield self._create_event(
                        stream_id, StreamEventType.TOKEN, token, {"accumulated_length": len(accumulated)}
                    )

                    # Small delay for natural feel
                    await asyncio.sleep(self.delay_ms / 1000)

            # Yield done event
            yield self._create_event(
                stream_id, StreamEventType.DONE, {"full_response": accumulated, "total_tokens": len(accumulated)}
            )

        except Exception as e:
            yield self._create_event(stream_id, StreamEventType.ERROR, {"error": str(e), "recoverable": True})

        finally:
            self._cleanup_stream(stream_id)

    async def stream_with_thinking(
        self, stream_id: str, llm_client: Any, messages: list, model: str = "gpt-4o-mini", **kwargs
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream with thinking state visibility.
        Shows what the AI is "thinking" before responding.
        """
        yield self._create_event(
            stream_id, StreamEventType.THINKING, {"status": "analyzing", "message": "正在分析您的问题..."}
        )

        # First, get thinking/analysis (if model supports)
        thinking_prompt = [
            {"role": "system", "content": "分析用户问题，简要说明你的思路（一句话）"},
            messages[-1],  # Last user message
        ]

        try:
            thinking_response = await llm_client.chat.completions.create(
                model=model, messages=thinking_prompt, max_tokens=50, stream=False
            )

            thinking_text = thinking_response.choices[0].message.content

            yield self._create_event(
                stream_id, StreamEventType.THINKING, {"status": "planning", "message": thinking_text}
            )

        except Exception:
            pass

        # Now stream the actual response
        async for event in self.create_stream(stream_id, llm_client, messages, model, **kwargs):
            yield event

    async def stream_tool_call(
        self, stream_id: str, tool_name: str, tool_args: dict, tool_executor: Callable
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Stream tool call progress.
        """
        # Tool call started
        yield self._create_event(
            stream_id, StreamEventType.TOOL_CALL, {"tool": tool_name, "status": "started", "args": tool_args}
        )

        try:
            start_time = time.time()

            # Progress updates
            yield self._create_event(
                stream_id, StreamEventType.PROGRESS, {"tool": tool_name, "progress": 0.5, "message": "正在执行..."}
            )

            # Execute tool
            result = await tool_executor(tool_args)

            duration_ms = int((time.time() - start_time) * 1000)

            # Tool result
            yield self._create_event(
                stream_id,
                StreamEventType.TOOL_RESULT,
                {"tool": tool_name, "status": "completed", "result": result, "duration_ms": duration_ms},
            )

        except Exception as e:
            yield self._create_event(
                stream_id, StreamEventType.ERROR, {"tool": tool_name, "status": "failed", "error": str(e)}
            )

    async def stream_progress(self, stream_id: str, current: int, total: int, message: str = None) -> StreamEvent:
        """Create a progress update event."""
        return self._create_event(
            stream_id,
            StreamEventType.PROGRESS,
            {
                "current": current,
                "total": total,
                "percentage": round(current / total * 100, 1) if total > 0 else 0,
                "message": message,
            },
        )

    def _create_event(
        self, stream_id: str, event_type: StreamEventType, data: Any, metadata: dict = None
    ) -> StreamEvent:
        """Create a new stream event with sequence number."""
        if stream_id not in self._sequence_counters:
            self._sequence_counters[stream_id] = 0

        self._sequence_counters[stream_id] += 1

        return StreamEvent(
            event_type=event_type, data=data, sequence=self._sequence_counters[stream_id], metadata=metadata or {}
        )

    def _cleanup_stream(self, stream_id: str):
        """Clean up stream resources."""
        if stream_id in self._active_streams:
            del self._active_streams[stream_id]
        if stream_id in self._sequence_counters:
            del self._sequence_counters[stream_id]

    async def send_to_stream(self, stream_id: str, event: StreamEvent):
        """Send an event to an active stream."""
        if stream_id in self._active_streams:
            await self._active_streams[stream_id].put(event)

    async def get_stream_stats(self) -> dict[str, Any]:
        """Get statistics for all active streams."""
        return {
            "active_streams": len(self._active_streams),
            "streams": [{"stream_id": sid, "queue_size": queue.qsize()} for sid, queue in self._active_streams.items()],
        }

    async def close_stream(self, stream_id: str):
        """Force close a stream."""
        self._cleanup_stream(stream_id)


class SSEEncoder:
    """
    Helper class for SSE encoding.
    """

    @staticmethod
    def encode(event: StreamEvent) -> str:
        """Encode event as SSE format."""
        return event.to_sse()

    @staticmethod
    def encode_ping() -> str:
        """Encode a ping event for keep-alive."""
        return ": ping\n\n"

    @staticmethod
    def encode_comment(comment: str) -> str:
        """Encode a comment (ignored by client)."""
        return f": {comment}\n\n"


# Global instance
streaming_service = StreamingService()
