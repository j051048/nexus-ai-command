"""
LLM Model Adaptation Gateway - Tencent Hunyuan Adapter

Tencent Cloud Hunyuan API requires TC3-HMAC-SHA256 signature authentication.
Key differences:
- Authentication: TC3-HMAC-SHA256 signature (Tencent Cloud v3 signing)
- API endpoint: hunyuan.tencentcloudapi.com
- Request/response format uses Tencent Cloud API conventions
- api_key = SecretId, secret_key = SecretKey
"""

import datetime
import hashlib
import hmac
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

HUNYUAN_HOST = "hunyuan.tencentcloudapi.com"
HUNYUAN_ENDPOINT = f"https://{HUNYUAN_HOST}"
HUNYUAN_SERVICE = "hunyuan"
HUNYUAN_VERSION = "2023-09-01"


class HunyuanAdapter(BaseModelAdapter):
    """
    Adapter for Tencent Cloud Hunyuan API.

    Authentication uses TC3-HMAC-SHA256 signing process:
    1. Build canonical request
    2. Build string-to-sign
    3. Calculate signature with derived signing key
    4. Construct Authorization header

    api_key = Tencent Cloud SecretId
    secret_key = Tencent Cloud SecretKey
    """

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.host = HUNYUAN_HOST
        self.endpoint = config.api_base_url.rstrip("/") if config.api_base_url else HUNYUAN_ENDPOINT

    def _sign(self, payload_json: str, action: str, timestamp: int) -> dict:
        """
        Generate TC3-HMAC-SHA256 signed headers for Tencent Cloud API.

        Args:
            payload_json: JSON string of the request body
            action: API action name (e.g., "ChatCompletions")
            timestamp: Unix timestamp

        Returns:
            Dict of headers including Authorization
        """
        secret_id = self.config.api_key
        secret_key = self.config.secret_key
        if not secret_key:
            raise ValueError("Hunyuan adapter requires secret_key (Tencent Cloud SecretKey)")

        # Step 1: Build canonical request
        http_request_method = "POST"
        canonical_uri = "/"
        canonical_querystring = ""
        content_type = "application/json; charset=utf-8"
        canonical_headers = f"content-type:{content_type}\nhost:{self.host}\n"
        signed_headers = "content-type;host"
        hashed_payload = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        canonical_request = (
            f"{http_request_method}\n"
            f"{canonical_uri}\n"
            f"{canonical_querystring}\n"
            f"{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{hashed_payload}"
        )

        # Step 2: Build string to sign
        date = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
        credential_scope = f"{date}/{HUNYUAN_SERVICE}/tc3_request"
        hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
        string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashed_canonical}"

        # Step 3: Calculate signature
        def _hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = _hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
        secret_service = _hmac_sha256(secret_date, HUNYUAN_SERVICE)
        secret_signing = _hmac_sha256(secret_service, "tc3_request")
        signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        # Step 4: Construct Authorization header
        authorization = (
            f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        return {
            "Authorization": authorization,
            "Content-Type": content_type,
            "Host": self.host,
            "X-TC-Action": action,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": HUNYUAN_VERSION,
        }

    def _build_chat_payload(self, request: ChatRequest) -> dict:
        """Build Hunyuan ChatCompletions payload."""
        messages = []

        if request.system_prompt:
            messages.append({"Role": "system", "Content": request.system_prompt})

        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            messages.append({"Role": role, "Content": content})

        payload = {
            "Model": self.config.model_id or self.config.model_code,
            "Messages": messages,
        }

        # Temperature
        temperature = request.temperature if request.temperature is not None else self.config.default_temperature
        payload["Temperature"] = max(0.0, min(2.0, temperature))

        # TopP
        top_p = request.top_p if request.top_p is not None else self.config.default_top_p
        payload["TopP"] = max(0.0, min(1.0, top_p))

        # Streaming
        if request.stream:
            payload["Stream"] = True

        # Tools
        if request.tools and self.config.supports_tools:
            hunyuan_tools = []
            for tool in request.tools:
                fn = tool.get("function", tool)
                hunyuan_tools.append({
                    "Type": "function",
                    "Function": {
                        "Name": fn.get("name", ""),
                        "Description": fn.get("description", ""),
                        "Parameters": json.dumps(fn.get("parameters", {})),
                    },
                })
            payload["Tools"] = hunyuan_tools
            payload["ToolChoice"] = "auto"

        return payload

    def _parse_usage(self, usage_data: dict | None) -> dict:
        """Parse Hunyuan usage info (PascalCase keys)."""
        if not usage_data:
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "call_cost": 0.0}

        input_tokens = usage_data.get("PromptTokens", 0)
        output_tokens = usage_data.get("CompletionTokens", 0)
        total_tokens = usage_data.get("TotalTokens", input_tokens + output_tokens)

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "call_cost": 0.0,
        }

    def _parse_tool_calls(self, choice: dict) -> list[dict] | None:
        """Extract tool calls from Hunyuan response choice."""
        message = choice.get("Message", {})
        raw_tool_calls = message.get("ToolCalls")
        if not raw_tool_calls:
            return None

        parsed = []
        for tc in raw_tool_calls:
            fn = tc.get("Function", {})
            parsed.append({
                "id": tc.get("Id", f"hunyuan_{uuid.uuid4().hex[:8]}"),
                "type": "function",
                "function": {
                    "name": fn.get("Name", ""),
                    "arguments": fn.get("Arguments", "{}"),
                },
            })
        return parsed

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Send a non-streaming chat request to Hunyuan."""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = time.monotonic()

        payload = self._build_chat_payload(request)
        payload.pop("Stream", None)
        payload_json = json.dumps(payload)

        timestamp = int(time.time())
        try:
            headers = self._sign(payload_json, "ChatCompletions", timestamp)
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Hunyuan signing failed: {e}")
            return ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content=f"Signing failed: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )

        timeout = self._build_timeout()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.endpoint, headers=headers, content=payload_json
                )

                if response.status_code != 200:
                    error_text = response.text[:500]
                    logger.error(f"Hunyuan API error ({response.status_code}): {error_text}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return ChatResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        content=f"API Error {response.status_code}: {error_text}",
                        finish_reason="error",
                        exec_time_ms=exec_time_ms,
                    )

                data = response.json()
                resp = data.get("Response", {})

                # Check for API error
                error = resp.get("Error")
                if error:
                    error_msg = f"{error.get('Code', 'Unknown')}: {error.get('Message', '')}"
                    logger.error(f"Hunyuan API error: {error_msg}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return ChatResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        content=f"Hunyuan Error: {error_msg}",
                        finish_reason="error",
                        exec_time_ms=exec_time_ms,
                    )

                choices = resp.get("Choices", [])
                usage = self._parse_usage(resp.get("Usage"))

                if choices:
                    choice = choices[0]
                    message = choice.get("Message", {})
                    content = message.get("Content", "") or ""
                    tool_calls = self._parse_tool_calls(choice)
                    finish_reason = choice.get("FinishReason", "stop")
                else:
                    content = ""
                    tool_calls = None
                    finish_reason = "stop"

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
            logger.error(f"Hunyuan API timeout after {exec_time_ms}ms")
            return ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content="Request timed out",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Hunyuan adapter error: {e}")
            return ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content=f"Adapter error: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatResponse]:
        """Send a streaming chat request to Hunyuan."""
        request_id = request.request_id or str(uuid.uuid4())
        start_time = time.monotonic()

        payload = self._build_chat_payload(request)
        payload["Stream"] = True
        payload_json = json.dumps(payload)

        timestamp = int(time.time())
        try:
            headers = self._sign(payload_json, "ChatCompletions", timestamp)
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            yield ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content=f"Signing failed: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )
            return

        timeout = self._build_timeout()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", self.endpoint, headers=headers, content=payload_json
                ) as response:
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
                            if json_str == "[DONE]":
                                break

                            try:
                                chunk_data = json.loads(json_str)
                            except json.JSONDecodeError:
                                continue

                            resp = chunk_data.get("Response", chunk_data)
                            choices = resp.get("Choices", [])
                            usage = self._parse_usage(resp.get("Usage"))

                            if choices:
                                choice = choices[0]
                                delta = choice.get("Delta", {})
                                delta_content = delta.get("Content", "") or ""
                                chunk_finish = choice.get("FinishReason")
                            else:
                                delta_content = ""
                                chunk_finish = None

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
            logger.error(f"Hunyuan streaming error: {e}")
            yield ChatResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                content=f"Stream error: {str(e)}",
                finish_reason="error",
                exec_time_ms=exec_time_ms,
            )

    async def embedding(self, texts: list[str]) -> EmbeddingResponse:
        """
        Generate embeddings via Hunyuan Embedding API.
        Note: Hunyuan embedding uses the same TC3 signing mechanism.
        """
        request_id = str(uuid.uuid4())
        start_time = time.monotonic()

        payload = {
            "Model": self.config.model_id or "hunyuan-embedding",
            "Input": texts,
        }
        payload_json = json.dumps(payload)

        timestamp = int(time.time())
        try:
            headers = self._sign(payload_json, "GetEmbedding", timestamp)
        except Exception as e:
            exec_time_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(f"Hunyuan embedding signing failed: {e}")
            return EmbeddingResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                exec_time_ms=exec_time_ms,
            )

        timeout = self._build_timeout()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.endpoint, headers=headers, content=payload_json
                )

                if response.status_code != 200:
                    logger.error(f"Hunyuan embedding error ({response.status_code}): {response.text[:300]}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return EmbeddingResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        exec_time_ms=exec_time_ms,
                    )

                data = response.json()
                resp = data.get("Response", {})

                if resp.get("Error"):
                    logger.error(f"Hunyuan embedding API error: {resp['Error']}")
                    exec_time_ms = int((time.monotonic() - start_time) * 1000)
                    return EmbeddingResponse(
                        request_id=request_id,
                        model_code=self.config.model_code,
                        exec_time_ms=exec_time_ms,
                    )

                embedding_data = resp.get("Data", [])
                embeddings = [item.get("Embedding", []) for item in embedding_data]

                usage_raw = resp.get("Usage", {})
                usage = {
                    "input_tokens": usage_raw.get("PromptTokens", 0),
                    "total_tokens": usage_raw.get("TotalTokens", 0),
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
            logger.error(f"Hunyuan embedding request failed: {e}")
            return EmbeddingResponse(
                request_id=request_id,
                model_code=self.config.model_code,
                exec_time_ms=exec_time_ms,
            )

    async def test_connectivity(self) -> dict:
        """Test connectivity to Hunyuan API."""
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
