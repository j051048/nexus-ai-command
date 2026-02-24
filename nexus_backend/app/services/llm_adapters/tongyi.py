"""
LLM Model Adaptation Gateway - Alibaba Tongyi (DashScope) Adapter

Tongyi Qianwen models via Alibaba Cloud DashScope API.
Key differences from OpenAI:
- API endpoint: https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation
- Auth via Authorization: Bearer <api-key>
- Different request/response structure with input/parameters/output nesting
- SSE streaming with slightly different format
"""

import json
import logging
import time
import uuid
from typing import AsyncIterator

import httpx

from app.services.llm_adapters.base import (
    BaseModelAdapter,
    ChatRequest,
    ChatResponse,
    EmbeddingResponse,
    ModelConfig,
)

logger = logging.getLogger(__name__)

DASHSCOPE_CHAT_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
DASHSCOPE_EMBEDDING_URL = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"


class TongyiAdapter(BaseModelAdapter):
    """
    Adapter for Alibaba Tongyi Qianwen (DashScope) API.

    Supports:
    - qwen-turbo, qwen-plus, qwen-max, qwen-long series
    - Tool/function calling
    - Streaming via SSE
    - Text embeddings
    """

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        # Allow overriding base URL for private deployments
        self.chat_url = config.api_base_url.rstrip("/") if config.api_base_url else DASHSCOPE_CHAT_URL
        self.embedding_url = DASHSCOPE_EMBEDDING_URL

    def _build_headers(self, streaming: bool = False) -> dict:
        """Build HTTP headers for DashScope API."""
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if streaming:
            headers["X-DashScope-SSE"] = "enable"
        return headers

    def _build_chat_payload(self, request: ChatRequest) -> dict:
        """Build DashScope chat generation payload."""
        messages = []

        # System prompt as first message
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})

        # Conversation messages
        messages.extend(request.messages)

        payload = {
            "model": self.config.model_id or self.config.model_code,
            "input": {
                "messages": messages,
            },
            "parameters": {},
        }

        # Parameters
        params = payload["parameters"]
        temperature = request.temperature if request.temperature is not None else self.config.default_temperature
        params["temperature"] = max(0.0, min(2.0, temperature))

        top_p = request.top_p if request.top_p is not None else self.config.default_top_p
        params["top_p"] = max(0.0, min(1.0, top_p))

        max_tokens = request.max_tokens or self.config.max_tokens
        if max_tokens:
            params["max_tokens"] = max_tokens

        # Result format - use "message" for OpenAI-compatible response
        params["result_format"] = "message"

        # Tools / function calling
        if request.tools and self.config.supports_tools:
            payload["input"]["tools"] = request.tools

        return payload

    def _parse_usage(self, usage_data: dict | None) -> dict:
        """Parse DashScope usage info."""
        if not usage_data:
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "call_cost": 0.0}

        input_tokens = usage_data.get("input_tokens", 0)
        output_tokens = usage_data.get("output_tokens", 0)
        total_tokens = usage_data.get("total_tokens", input_tokens + output_tokens)

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "call_cost": 0.0,
        }

    def _parse_tool_calls_from_message(self, message: dict) -> list[dict] | None:
        """Extract tool_calls from DashScope message format."""
        raw_tool_calls = message.get("tool_calls")
        if not raw_tool_calls:
            return None

        parsed = []
        for tc in raw_tool_calls:
            parsed.append({
                "id": tc.get("id", f"tongyi_{uuid.uuid4().hex[:8]}"),
                "type": tc.get("type", "function"),
                "function": {
                    "name": tc.get("function", {}).get("name", ""),
                    "arguments": tc.get("function", {}).get("arguments", "{}"),
                },
            })
        return parsed

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a non-streaming chat request to DashScope."""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = time.monotonic()

        payload = self._build_chat_payload(request)
        headers = self._build_headers(streaming=False)
        timeout = self._build_timeout()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.chat_url, headers=headers, json=payload)

                if response.status_code != 200:
                    error_text = response.text[:500]
                    logger.error(f"DashScope API error ({response.status_code}): {error_text}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return ChatResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        content=f"API Error {response.status_code}: {error_text}",
                        finish_reason="error",
                        exec_time_ms=exec_time_ms,
                    )

                data = response.json()

                # DashScope error format
                if data.get("code"):
                    error_msg = data.get("message", "Unknown error")
                    logger.error(f"DashScope API error: {data['code']} - {error_msg}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return ChatResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        content=f"DashScope Error: {error_msg}",
                        finish_reason="error",
                        exec_time_ms=exec_time_ms,
                    )

                output = data.get("output", {})
                usage = self._parse_usage(data.get("usage"))

                # With result_format="message", output has choices
                choices = output.get("choices", [])
                if choices:
                    choice = choices[0]
                    message = choice.get("message", {})
                    content = message.get("content", "") or ""
                    tool_calls = self._parse_tool_calls_from_message(message)
                    finish_reason = choice.get("finish_reason", "stop")
                else:
                    # Fallback: direct text output
                    content = output.get("text", "")
                    tool_calls = None
                    finish_reason = output.get("finish_reason", "stop")

                if tool_calls:
                    finish_reason = "tool_calls"

                exec_time_ms = int((time.monotonic() - start_time) * 1000)
                return ChatResponse(
                    request_id=request_id,
                    model_code=self.config.model_code,
                    content=content,
                    tool_calls=tool_calls,
                    usage=usage,
                    exec_time_ms=exec_time_ms,
                    finish_reason=finish_reason,
                    raw_response=data,
                )

        except httpx.TimeoutException:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"DashScope API timeout after {exec_time_ms}ms")
            return ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content="Request timed out",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Tongyi adapter error: {e}")
            return ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content=f"Adapter error: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatResponse]:
        """Send a streaming chat request to DashScope using SSE."""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = time.monotonic()

        payload = self._build_chat_payload(request)
        # DashScope streaming is enabled via header, not payload
        params = payload.setdefault("parameters", {})
        params["incremental_output"] = True

        headers = self._build_headers(streaming=True)
        timeout = self._build_timeout()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", self.chat_url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        error_text = ""
                        async for chunk in response.aiter_text():
                            error_text += chunk
                        error_text = error_text[:500]
                        exec_time_ms = int((time.monotonic() - start_time) * 1000)
                        yield ChatResponse(
                            request_id=request_id,
                            model_code=self.config.model_code,
                            content=f"API Error {response.status_code}: {error_text}",
                            finish_reason="error",
                            exec_time_ms=exec_time_ms,
                        )
                        return

                    buffer = ""
                    async for raw_chunk in response.aiter_text():
                        buffer += raw_chunk
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()

                            if not line or line.startswith(":"):
                                continue

                            # DashScope SSE format: "id:", "event:", "data:" lines
                            if not line.startswith("data:"):
                                continue

                            json_str = line[5:].strip()
                            if not json_str:
                                continue

                            try:
                                chunk_data = json.loads(json_str)
                            except json.JSONDecodeError:
                                continue

                            # Check for errors
                            if chunk_data.get("code"):
                                exec_time_ms = int((time.monotonic() - start_time) * 1000)
                                yield ChatResponse(
                                    request_id=request_id,
                                    model_code=self.config.model_code,
                                    content=chunk_data.get("message", "Stream error"),
                                    finish_reason="error",
                                    exec_time_ms=exec_time_ms,
                                )
                                return

                            output = chunk_data.get("output", {})
                            usage = self._parse_usage(chunk_data.get("usage"))

                            choices = output.get("choices", [])
                            if choices:
                                choice = choices[0]
                                message = choice.get("message", {})
                                delta_content = message.get("content", "") or ""
                                chunk_finish = choice.get("finish_reason")
                            else:
                                delta_content = output.get("text", "")
                                chunk_finish = output.get("finish_reason")

                            exec_time_ms = int((time.monotonic() - start_time) * 1000)
                            yield ChatResponse(
                                request_id=request_id,
                                model_code=self.config.model_code,
                                content=delta_content,
                                usage=usage,
                                exec_time_ms=exec_time_ms,
                                finish_reason=chunk_finish or "",
                            )

        except httpx.TimeoutException:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            yield ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content="Stream timed out",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Tongyi streaming error: {e}")
            yield ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content=f"Stream error: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )

    async def embedding(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings via DashScope embedding API."""
        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        model_id = self.config.model_id or "text-embedding-v2"
        headers = self._build_headers()
        timeout = self._build_timeout()

        payload = {
            "model": model_id,
            "input": {
                "texts": texts,
            },
            "parameters": {
                "text_type": "document",
            },
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.embedding_url, headers=headers, json=payload)

                if response.status_code != 200:
                    logger.error(f"DashScope embedding error ({response.status_code}): {response.text[:300]}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return EmbeddingResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        exec_time_ms=exec_time_ms,
                    )

                data = response.json()

                if data.get("code"):
                    logger.error(f"DashScope embedding API error: {data.get('message')}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return EmbeddingResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        exec_time_ms=exec_time_ms,
                    )

                output = data.get("output", {})
                embeddings_data = output.get("embeddings", [])
                embeddings = [item["embedding"] for item in embeddings_data]

                usage_raw = data.get("usage", {})
                usage = {
                    "input_tokens": usage_raw.get("total_tokens", 0),
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
            logger.error(f"Tongyi embedding request failed: {e}")
            return EmbeddingResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                exec_time_ms=exec_time_ms,
            )

    async def test_connectivity(self) -> dict:
        """Test connectivity to DashScope API."""
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
                return {"success": False, "latency_ms": latency_ms, "error": result.content}

            return {"success": True, "latency_ms": latency_ms, "error": None}

        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return {"success": False, "latency_ms": latency_ms, "error": str(e)}
