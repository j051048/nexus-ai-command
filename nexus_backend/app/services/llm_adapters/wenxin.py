"""
LLM Model Adaptation Gateway - Baidu Wenxin (ERNIE Bot) Adapter

Key differences from OpenAI:
- Uses access_token authentication (OAuth2 client_credentials flow)
- API key + secret_key -> access_token via oauth endpoint
- Different endpoint URL structure
- Slightly different request/response format
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

# Wenxin OAuth endpoint
WENXIN_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"

# Default Wenxin chat API base
WENXIN_API_BASE = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop"


class WenxinAdapter(BaseModelAdapter):
    """
    Adapter for Baidu Wenxin (ERNIE Bot) API.

    Authentication flow:
    1. POST to OAuth endpoint with api_key (client_id) + secret_key (client_secret)
    2. Receive access_token (valid for 30 days, cached locally)
    3. Use access_token as query parameter in API calls
    """

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._access_token: str | None = None
        self._token_expires_at: float = 0
        # Use custom base URL if provided, otherwise default
        self.api_base = config.api_base_url.rstrip("/") if config.api_base_url else WENXIN_API_BASE

    async def _ensure_access_token(self) -> str:
        """Obtain or refresh the Wenxin access_token."""
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        if not self.config.secret_key:
            raise ValueError("Wenxin adapter requires secret_key (client_secret) for authentication")

        params = {
            "grant_type": "client_credentials",
            "client_id": self.config.api_key,
            "client_secret": self.config.secret_key,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(WENXIN_TOKEN_URL, params=params)
                if response.status_code != 200:
                    raise ValueError(f"Wenxin OAuth failed ({response.status_code}): {response.text[:300]}")

                data = response.json()
                if "access_token" not in data:
                    raise ValueError(f"Wenxin OAuth response missing access_token: {data}")

                self._access_token = data["access_token"]
                # Token is valid for expires_in seconds (usually 2592000 = 30 days)
                # Refresh 1 hour early to avoid edge cases
                expires_in = data.get("expires_in", 2592000)
                self._token_expires_at = now + expires_in - 3600

                logger.info("Wenxin access_token refreshed successfully")
                return self._access_token

        except httpx.TimeoutException:
            raise ValueError("Wenxin OAuth request timed out")

    def _build_chat_payload(self, request: ChatRequest) -> dict:
        """Build Wenxin chat payload from unified ChatRequest."""
        messages = []

        # Wenxin uses system field separately, not in messages
        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            # Wenxin only supports user/assistant roles in messages
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})

        payload: dict = {"messages": messages}

        # System prompt as top-level field
        if request.system_prompt:
            payload["system"] = request.system_prompt

        # Temperature (Wenxin range: 0.01 ~ 1.0)
        temperature = request.temperature if request.temperature is not None else self.config.default_temperature
        payload["temperature"] = max(0.01, min(1.0, temperature))

        # Top-p
        top_p = request.top_p if request.top_p is not None else self.config.default_top_p
        payload["top_p"] = max(0.0, min(1.0, top_p))

        # Max output tokens
        max_tokens = request.max_tokens or self.config.max_tokens
        if max_tokens:
            payload["max_output_tokens"] = max_tokens

        # Tools / function calling (Wenxin supports it for ERNIE 4.0+)
        if request.tools and self.config.supports_tools:
            payload["functions"] = []
            for tool in request.tools:
                fn = tool.get("function", tool)
                payload["functions"].append({
                    "name": fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                })

        if request.stream:
            payload["stream"] = True

        return payload

    def _get_chat_url(self) -> str:
        """Build the chat endpoint URL based on model_id."""
        model_id = self.config.model_id or "completions_pro"  # Default to ERNIE 4.0
        return f"{self.api_base}/chat/{model_id}"

    def _parse_usage(self, usage_data: dict | None) -> dict:
        """Parse Wenxin usage info."""
        if not usage_data:
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "call_cost": 0.0}

        input_tokens = usage_data.get("prompt_tokens", 0)
        output_tokens = usage_data.get("completion_tokens", 0)
        total_tokens = usage_data.get("total_tokens", input_tokens + output_tokens)

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "call_cost": 0.0,  # Wenxin pricing varies by model
        }

    def _parse_tool_calls(self, result: dict) -> list[dict] | None:
        """Extract function_call from Wenxin response."""
        function_call = result.get("function_call")
        if not function_call:
            return None

        return [{
            "id": f"wenxin_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {
                "name": function_call.get("name", ""),
                "arguments": function_call.get("arguments", "{}"),
            },
        }]

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a non-streaming chat request to Wenxin."""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = time.monotonic()

        try:
            access_token = await self._ensure_access_token()
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Wenxin auth failed: {e}")
            return ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content=f"Authentication failed: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )

        payload = self._build_chat_payload(request)
        payload.pop("stream", None)

        url = f"{self._get_chat_url()}?access_token={access_token}"
        headers = {"Content-Type": "application/json"}
        timeout = self._build_timeout()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    error_text = response.text[:500]
                    logger.error(f"Wenxin API error ({response.status_code}): {error_text}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return ChatResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        content=f"API Error {response.status_code}: {error_text}",
                        finish_reason="error",
                        exec_time_ms=exec_time_ms,
                    )

                data = response.json()

                # Wenxin returns error in response body with error_code field
                if data.get("error_code"):
                    error_msg = data.get("error_msg", "Unknown error")
                    logger.error(f"Wenxin API error: {data['error_code']} - {error_msg}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return ChatResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        content=f"Wenxin Error {data['error_code']}: {error_msg}",
                        finish_reason="error",
                        exec_time_ms=exec_time_ms,
                    )

                content = data.get("result", "")
                tool_calls = self._parse_tool_calls(data)
                usage = self._parse_usage(data.get("usage"))
                finish_reason = "tool_calls" if tool_calls else "stop"

                # Check if output was truncated
                if data.get("is_truncated"):
                    finish_reason = "length"

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
            logger.error(f"Wenxin API timeout after {exec_time_ms}ms")
            return ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content="Request timed out",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Wenxin adapter error: {e}")
            return ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content=f"Adapter error: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatResponse]:
        """Send a streaming chat request to Wenxin."""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = time.monotonic()

        try:
            access_token = await self._ensure_access_token()
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            yield ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content=f"Authentication failed: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )
            return

        payload = self._build_chat_payload(request)
        payload["stream"] = True

        url = f"{self._get_chat_url()}?access_token={access_token}"
        headers = {"Content-Type": "application/json"}
        timeout = self._build_timeout()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
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

                            if not line.startswith("data: "):
                                continue

                            json_str = line[6:]
                            try:
                                chunk_data = json.loads(json_str)
                            except json.JSONDecodeError:
                                continue

                            if chunk_data.get("error_code"):
                                exec_time_ms = int((time.monotonic() - start_time) * 1000)
                                yield ChatResponse(
                                    request_id=request_id,
                                    model_code=self.config.model_code,
                                    content=chunk_data.get("error_msg", "Stream error"),
                                    finish_reason="error",
                                    exec_time_ms=exec_time_ms,
                                )
                                return

                            delta_content = chunk_data.get("result", "")
                            is_end = chunk_data.get("is_end", False)
                            usage = self._parse_usage(chunk_data.get("usage"))

                            exec_time_ms = int((time.monotonic() - start_time) * 1000)
                            yield ChatResponse(
                                request_id=request_id,
                                model_code=self.config.model_code,
                                content=delta_content,
                                usage=usage,
                                exec_time_ms=exec_time_ms,
                                finish_reason="stop" if is_end else "",
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
            logger.error(f"Wenxin streaming error: {e}")
            yield ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content=f"Stream error: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )

    async def embedding(self, texts: list[str]) -> EmbeddingResponse:
        """Generate embeddings via Wenxin embedding API."""
        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        try:
            access_token = await self._ensure_access_token()
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Wenxin embedding auth failed: {e}")
            return EmbeddingResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                exec_time_ms=exec_time_ms,
            )

        model_id = self.config.model_id or "embedding-v1"
        url = f"{self.api_base}/embeddings/{model_id}?access_token={access_token}"
        headers = {"Content-Type": "application/json"}
        timeout = self._build_timeout()

        payload = {"input": texts}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.error(f"Wenxin embedding error ({response.status_code}): {response.text[:300]}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return EmbeddingResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        exec_time_ms=exec_time_ms,
                    )

                data = response.json()
                if data.get("error_code"):
                    logger.error(f"Wenxin embedding API error: {data.get('error_msg')}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return EmbeddingResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        exec_time_ms=exec_time_ms,
                    )

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
            logger.error(f"Wenxin embedding request failed: {e}")
            return EmbeddingResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                exec_time_ms=exec_time_ms,
            )

    async def test_connectivity(self) -> dict:
        """Test connectivity to Wenxin API."""
        start_time = time.monotonic()
        try:
            # First test OAuth
            await self._ensure_access_token()

            # Then test a minimal chat request
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
