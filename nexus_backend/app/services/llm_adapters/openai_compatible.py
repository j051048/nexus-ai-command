"""
LLM Model Adaptation Gateway - OpenAI-Compatible Adapter

Covers ~90% of models: OpenAI, Azure OpenAI, DeepSeek, Moonshot, Yi,
and any provider exposing a /chat/completions + /embeddings API.
Uses httpx for HTTP calls following the existing etl_service.py pattern.
"""

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

import httpx

from app.core.config import FORCED_CHAT_MODEL
from app.services.llm_adapters.base import (
    BaseModelAdapter,
    ChatRequest,
    ChatResponse,
    EmbeddingResponse,
    ModelConfig,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleAdapter(BaseModelAdapter):
    """
    Adapter for OpenAI-compatible APIs.
    Works with any provider that follows the OpenAI chat completions spec.
    """

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        # Normalize base URL - strip trailing slash
        self.base_url = config.api_base_url.rstrip("/")

    def _build_headers(self) -> dict:
        """Build HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def _build_chat_payload(self, request: ChatRequest) -> dict:
        """Build the chat completions request payload."""
        messages = []

        # Add system prompt as first message if present
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        # Add conversation messages
        messages.extend(request.messages)

        payload = {
            "model": FORCED_CHAT_MODEL,
            "messages": messages,
            "temperature": (
                request.temperature
                if request.temperature is not None
                else self.config.default_temperature
            ),
            "top_p": (
                request.top_p
                if request.top_p is not None
                else self.config.default_top_p
            ),
        }

        # Optional max_tokens
        max_tokens = request.max_tokens or self.config.max_tokens
        if max_tokens:
            payload["max_tokens"] = max_tokens

        # Tools / function calling
        if request.tools and self.config.supports_tools:
            payload["tools"] = request.tools
            payload["tool_choice"] = "auto"

        # Streaming
        if request.stream:
            payload["stream"] = True

        return payload

    def _parse_usage(self, usage_data: dict | None) -> dict:
        """Parse usage info from API response."""
        if not usage_data:
            return {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "call_cost": 0.0,
            }

        input_tokens = usage_data.get("prompt_tokens", 0)
        output_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", input_tokens + output_tokens)

        # Cost estimation - delegate to token_service for accurate pricing
        call_cost = 0.0
        try:
            from app.services.token_service import token_counter

            call_cost = token_counter.estimate_cost(
                input_tokens, output_tokens, FORCED_CHAT_MODEL
            )
        except Exception:
            pass

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "call_cost": call_cost,
        }

    def _estimate_stream_usage(
        self,
        request: ChatRequest,
        accumulated_content: str,
        accumulated_tool_calls: list[dict] | None = None,
    ) -> dict:
        """Estimate final stream usage when the provider omits usage metadata."""
        try:
            from app.services.token_service import token_counter

            output_text = accumulated_content or ""
            if accumulated_tool_calls:
                output_text += json.dumps(accumulated_tool_calls, ensure_ascii=False)

            input_tokens = token_counter.estimate_prompt_tokens(
                system_prompt=request.system_prompt or "",
                messages=request.messages,
                tools=request.tools,
                model=FORCED_CHAT_MODEL,
            )
            output_tokens = token_counter.count_tokens(output_text, FORCED_CHAT_MODEL)
            if output_tokens == 0 and request.max_tokens:
                output_tokens = max(1, min(request.max_tokens, 1024))
            call_cost = token_counter.estimate_cost(
                input_tokens, output_tokens, FORCED_CHAT_MODEL
            )
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "call_cost": call_cost,
                "estimated": True,
            }
        except Exception:
            input_chars = len(request.system_prompt or "") + sum(
                len(str(message.get("content") or "")) for message in request.messages
            )
            if request.tools:
                input_chars += sum(len(str(tool)) for tool in request.tools)
            output_chars = len(accumulated_content or "")
            if accumulated_tool_calls:
                output_chars += len(
                    json.dumps(accumulated_tool_calls, ensure_ascii=False)
                )
            input_tokens = max(1, input_chars // 4)
            output_tokens = max(1, output_chars // 4)
            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "call_cost": 0.0,
                "estimated": True,
            }

    def _parse_tool_calls(self, choice: dict) -> list[dict] | None:
        """Extract tool_calls from the API response choice."""
        message = choice.get("message", {})
        raw_tool_calls = message.get("tool_calls")
        if not raw_tool_calls:
            return None

        parsed = []
        for tc in raw_tool_calls:
            parsed.append(
                {
                    "id": tc.get("id", ""),
                    "type": tc.get("type", "function"),
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", "{}"),
                    },
                }
            )
        return parsed

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a non-streaming chat completion request."""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = time.monotonic()

        payload = self._build_chat_payload(request)
        payload.pop("stream", None)  # Ensure non-streaming

        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        timeout = self._build_timeout()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    error_text = response.text[:500]
                    logger.error(
                        f"OpenAI-compatible API error ({response.status_code}): {error_text}",
                        extra={
                            "model_code": FORCED_CHAT_MODEL,
                            "request_id": request_id,
                        },
                    )
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return ChatResponse(
                        request_id=request_id,
                        model_code=FORCED_CHAT_MODEL,
                        content=f"API Error {response.status_code}: {error_text}",
                        finish_reason="error",
                        exec_time_ms=exec_time_ms,
                    )

                data = response.json()
                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                content = message.get("content", "") or ""
                tool_calls = self._parse_tool_calls(choice)
                usage = self._parse_usage(data.get("usage"))
                finish_reason = choice.get("finish_reason", "stop")

                # Map provider-specific finish reasons
                if finish_reason == "tool_calls" or tool_calls:
                    finish_reason = "tool_calls"

                exec_time_ms = int((time.monotonic() - start_time) * 1000)

                return ChatResponse(
                    request_id=request_id,
                    model_code=FORCED_CHAT_MODEL,
                    content=content,
                    tool_calls=tool_calls,
                    usage=usage,
                    exec_time_ms=exec_time_ms,
                    finish_reason=finish_reason,
                    raw_response=data,
                )

        except httpx.TimeoutException:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                f"OpenAI-compatible API timeout after {exec_time_ms}ms",
                extra={"model_code": FORCED_CHAT_MODEL, "request_id": request_id},
            )
            return ChatResponse(
                request_id=request_id,
                model_code=FORCED_CHAT_MODEL,
                content="Request timed out",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                f"OpenAI-compatible adapter error: {e}",
                extra={"model_code": FORCED_CHAT_MODEL, "request_id": request_id},
            )
            return ChatResponse(
                request_id=request_id,
                model_code=FORCED_CHAT_MODEL,
                content=f"Adapter error: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatResponse]:
        """Send a streaming chat completion request via SSE."""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = time.monotonic()

        payload = self._build_chat_payload(request)
        payload["stream"] = True

        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        timeout = self._build_timeout()

        accumulated_content = ""
        accumulated_tool_calls: list[dict] = []
        usage_data = {}

        try:
            async with (
                httpx.AsyncClient(timeout=timeout) as client,
                client.stream("POST", url, headers=headers, json=payload) as response,
            ):
                if response.status_code != 200:
                    error_text = ""
                    async for chunk in response.aiter_text():
                        error_text += chunk
                    error_text = error_text[:500]
                    logger.error(
                        f"OpenAI-compatible streaming error ({response.status_code}): {error_text}"
                    )
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    yield ChatResponse(
                        request_id=request_id,
                        model_code=FORCED_CHAT_MODEL,
                        content=f"API Error {response.status_code}: {error_text}",
                        finish_reason="error",
                        exec_time_ms=exec_time_ms,
                    )
                    return

                buffer = ""
                async for raw_chunk in response.aiter_text():
                    buffer += raw_chunk
                    # Process complete SSE lines
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if not line or line.startswith(":"):
                            continue

                        if line == "data: [DONE]":
                            break

                        if not line.startswith("data: "):
                            continue

                        json_str = line[6:]  # Remove "data: " prefix
                        try:
                            chunk_data = json.loads(json_str)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk_data.get("choices", [])
                        if not choices:
                            continue

                        delta = choices[0].get("delta", {})
                        chunk_finish = choices[0].get("finish_reason")

                        # Accumulate content
                        delta_content = delta.get("content", "")
                        if delta_content:
                            accumulated_content += delta_content

                        # Accumulate tool calls
                        if delta.get("tool_calls"):
                            for tc_delta in delta["tool_calls"]:
                                idx = tc_delta.get("index", 0)
                                while len(accumulated_tool_calls) <= idx:
                                    accumulated_tool_calls.append(
                                        {
                                            "id": "",
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""},
                                        }
                                    )
                                if tc_delta.get("id"):
                                    accumulated_tool_calls[idx]["id"] = tc_delta["id"]
                                fn = tc_delta.get("function", {})
                                if fn.get("name"):
                                    accumulated_tool_calls[idx]["function"]["name"] = (
                                        fn["name"]
                                    )
                                if fn.get("arguments"):
                                    accumulated_tool_calls[idx]["function"][
                                        "arguments"
                                    ] += fn["arguments"]

                        # Check for usage in streaming response (some providers include it)
                        if chunk_data.get("usage"):
                            usage_data = chunk_data["usage"]

                        usage = (
                            self._parse_usage(usage_data)
                            if usage_data
                            else (
                                self._estimate_stream_usage(
                                    request,
                                    accumulated_content,
                                    accumulated_tool_calls,
                                )
                                if chunk_finish
                                else self._parse_usage(None)
                            )
                        )

                        # Yield partial response
                        exec_time_ms = int((time.monotonic() - start_time) * 1000)
                        yield ChatResponse(
                            request_id=request_id,
                            model_code=FORCED_CHAT_MODEL,
                            content=delta_content,
                            tool_calls=(
                                accumulated_tool_calls
                                if accumulated_tool_calls
                                else None
                            ),
                            usage=usage,
                            exec_time_ms=exec_time_ms,
                            finish_reason=chunk_finish or "",
                        )

        except httpx.TimeoutException:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"OpenAI-compatible streaming timeout after {exec_time_ms}ms")
            yield ChatResponse(
                request_id=request_id,
                model_code=FORCED_CHAT_MODEL,
                content="Stream timed out",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"OpenAI-compatible streaming error: {e}")
            yield ChatResponse(
                request_id=request_id,
                model_code=FORCED_CHAT_MODEL,
                content=f"Stream error: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )

    async def embedding(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings for a list of texts."""
        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        url = f"{self.base_url}/embeddings"
        headers = self._build_headers()
        timeout = self._build_timeout()

        payload = {
            "model": self.config.model_id or self.config.model_code,
            "input": texts,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    error_text = response.text[:500]
                    logger.error(
                        f"Embedding API error ({response.status_code}): {error_text}"
                    )
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return EmbeddingResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        exec_time_ms=exec_time_ms,
                    )

                data = response.json()
                embeddings = [item["embedding"] for item in data.get("data", [])]
                usage_raw = data.get("usage", {})
                usage = {
                    "input_tokens": usage_raw.get("prompt_tokens", 0),
                    "total_tokens": usage_raw.get("total_tokens", 0),
                    "call_cost": 0.0,
                }

                exec_time_ms = int((time.monotonic() - start_time) * 1000)
                return EmbeddingResponse(
                    request_id=request_id,
                    model_code=self.config.model_code,
                    embeddings=embeddings,
                    usage=usage,
                    exec_time_ms=exec_time_ms,
                )

        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Embedding request failed: {e}")
            return EmbeddingResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                exec_time_ms=exec_time_ms,
            )

    async def test_connectivity(self) -> dict:
        """Test connectivity with a minimal chat request."""
        start_time = time.monotonic()
        try:
            test_request = ChatRequest(
                scene_code="__test__",
                agent_code="__test__",
                user_id="__test__",
                system_prompt="",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            result = await self.chat(test_request)
            latency_ms = int((time.monotonic() - start_time) * 1000)

            if result.finish_reason == "error":
                return {
                    "success": False,
                    "latency_ms": latency_ms,
                    "error": result.content,
                }

            return {"success": True, "latency_ms": latency_ms, "error": None}

        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return {"success": False, "latency_ms": latency_ms, "error": str(e)}
