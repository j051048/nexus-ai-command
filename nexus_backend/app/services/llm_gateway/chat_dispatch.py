"""
LLM Gateway - Chat Dispatch Module

Contains the public chat(), stream_chat(), and embedding() methods that
orchestrate model resolution, quota checks, circuit breakers, adapter
calls, and usage recording.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator

from app.core.config import settings
from app.core.model_pricing import estimate_cost
from app.core.tenant_throttle import tenant_throttle
from app.core.token_budget import token_budget_manager
from app.services.ai_execution_policy_service import (
    AIExecutionPolicy,
    ai_execution_policy_service,
)
from app.services.llm_adapters.base import (
    ChatRequest,
    ChatResponse,
    EmbeddingResponse,
)
from app.services.llm_circuit_breaker import circuit_breaker_manager
from app.services.llm_gateway.routing_policy import choose_model_variant
from app.services.llm_quota_service import check_quota, record_usage

logger = logging.getLogger(__name__)

_TRANSIENT_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "429",
    "rate limit",
    "rate_limit",
    "too many requests",
    "500",
    "502",
    "503",
    "504",
    "connection",
    "connect",
    "temporarily unavailable",
)


def _is_transient_llm_error(error: Exception) -> bool:
    if isinstance(error, TimeoutError | asyncio.TimeoutError):
        return True
    message = str(error).lower()
    return any(marker in message for marker in _TRANSIENT_ERROR_MARKERS)


def _extract_user_query(messages: list[dict]) -> str:
    for message in reversed(messages or []):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def _estimate_chat_usage(
    *,
    model_code: str,
    system_prompt: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    output_text: str = "",
    max_tokens: int | None = None,
) -> dict:
    try:
        from app.services.token_service import token_counter

        input_tokens = token_counter.estimate_prompt_tokens(
            system_prompt=system_prompt or "",
            messages=messages,
            tools=tools,
            model=model_code,
        )
        output_tokens = token_counter.count_tokens(output_text or "", model_code)
    except Exception:
        input_chars = len(system_prompt or "") + sum(
            len(str(message.get("content") or "")) for message in messages
        )
        if tools:
            input_chars += sum(len(str(tool)) for tool in tools)
        input_tokens = max(1, input_chars // 4)
        output_tokens = max(1, len(output_text or "") // 4) if output_text else 0

    if output_tokens == 0 and max_tokens:
        output_tokens = max(1, min(max_tokens, 1024))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "call_cost": estimate_cost(input_tokens, output_tokens, model_code),
    }


async def _prune_runtime_tools(
    tools: list[dict] | None,
    *,
    messages: list[dict],
    scene_code: str,
    agent_code: str,
    tool_limit: int | None = None,
) -> list[dict] | None:
    """Prune large tool lists before direct gateway calls to avoid context bloat."""
    limit = min(tool_limit or settings.TOOL_MAX_TOOLS, settings.TOOL_MAX_TOOLS)
    if not tools:
        return tools
    if len(tools) <= min(settings.TOOL_EMBEDDING_GATE, limit):
        return tools[:limit]

    query = _extract_user_query(messages)
    if not query:
        return tools[: settings.TOOL_MAX_TOOLS]

    try:
        from app.agent.tool_embedding_index import tool_embedding_index

        def _tool_name(schema: dict) -> str:
            return schema.get("function", {}).get("name", "")

        candidate_names = {_tool_name(tool) for tool in tools if _tool_name(tool)}
        ranked = await tool_embedding_index.retrieve(
            query=query,
            top_k=settings.TOOL_EMBEDDING_TOP_K,
            min_score=settings.TOOL_EMBEDDING_MIN_SCORE,
            candidate_names=candidate_names,
        )
        if ranked:
            keep_names = {name for name, _score in ranked}
            pruned = [tool for tool in tools if _tool_name(tool) in keep_names]
            if pruned:
                logger.info(
                    "[ToolRAG] runtime pruned tools %d -> %d scene=%s agent=%s",
                    len(tools),
                    len(pruned),
                    scene_code,
                    agent_code,
                )
                return pruned[:limit]
    except Exception as exc:
        logger.debug("[ToolRAG] runtime pruning skipped: %s", exc)

    return tools[:limit]


class ChatDispatchMixin:
    """
    Mixin providing chat(), stream_chat(), and embedding() public methods.

    Requires (from ModelResolutionMixin):
        _resolve_model, _create_adapter, _maybe_upgrade_for_context,
        _get_backup_model

    Requires (from CallLoggingMixin):
        _log_call

    Requires:
        _error_response (static method)
    """

    async def chat(
        self,
        scene_code: str,
        agent_code: str,
        user_id: str,
        org_id: str,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        request_id: str | None = None,
    ) -> ChatResponse:
        """
        Main entry point for chat completions.

        Resolves the target model via schedule rules, checks quota,
        verifies the circuit breaker, dispatches through the adapter,
        records usage, and logs the call.  On failure the backup model
        is attempted automatically.
        """
        request_id = request_id or str(uuid.uuid4())
        start_ts = time.monotonic()
        policy = await ai_execution_policy_service.get_policy(org_id)
        max_tokens = min(
            max_tokens or policy.max_output_tokens,
            policy.max_output_tokens,
        )

        # --- Resolve model ---
        model_code = await self._resolve_model(scene_code, agent_code, org_id)
        if not model_code:
            return self._error_response(
                request_id, "", "No model configured for this scene/agent"
            )

        # --- Try primary model, then backup on failure ---
        response = await self._try_chat_with_model(
            model_code=model_code,
            org_id=org_id,
            user_id=user_id,
            scene_code=scene_code,
            agent_code=agent_code,
            system_prompt=system_prompt,
            messages=messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            request_id=request_id,
            start_ts=start_ts,
            policy=policy,
        )

        if response.finish_reason == "error":
            fallback_codes: list[str] = []
            backup_code = await self._get_backup_model(
                scene_code, agent_code, org_id, exclude=model_code
            )
            if backup_code:
                fallback_codes.append(backup_code)
            mini_code = settings.AI_MINI_MODEL
            if mini_code and mini_code not in {model_code, *fallback_codes}:
                fallback_codes.append(mini_code)

            for fallback_code in fallback_codes:
                logger.info(
                    "Retrying with fallback model '%s' after '%s' failed",
                    fallback_code,
                    model_code,
                )
                backup_response = await self._try_chat_with_model(
                    model_code=fallback_code,
                    org_id=org_id,
                    user_id=user_id,
                    scene_code=scene_code,
                    agent_code=agent_code,
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    request_id=request_id,
                    start_ts=start_ts,
                    policy=policy,
                )
                if backup_response.finish_reason != "error":
                    return backup_response

        return response

    async def _try_chat_with_model(
        self,
        model_code: str,
        org_id: str,
        user_id: str,
        scene_code: str,
        agent_code: str,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        request_id: str,
        start_ts: float,
        policy: AIExecutionPolicy,
    ) -> ChatResponse:
        """Execute a chat call against a single model with all guardrails."""

        estimated_tokens = (
            sum(len(m.get("content", "")) // 4 for m in messages)
            + len(system_prompt) // 4
            + (max_tokens or 4096)
        )

        if not policy.premium_manual_only:
            routing_decision = choose_model_variant(
                primary_model=model_code,
                scene_code=scene_code,
                agent_code=agent_code,
                org_id=org_id,
                user_id=user_id,
                estimated_tokens=estimated_tokens,
                has_tools=bool(tools),
            )
            if routing_decision.changed:
                logger.info(
                    "[LLMRouting] %s -> %s reason=%s bucket=%s",
                    model_code,
                    routing_decision.model_code,
                    routing_decision.reason,
                    routing_decision.bucket,
                )
                model_code = routing_decision.model_code

        # --- Quota check ---
        quota_result = await check_quota(
            tenant_id=org_id,
            model_code=model_code,
            user_id=user_id,
            estimated_tokens=estimated_tokens,
        )
        if not quota_result.allowed:
            latency = int((time.monotonic() - start_ts) * 1000)
            await self._log_call(
                org_id=org_id,
                model_code=model_code,
                scene_code=scene_code,
                agent_code=agent_code,
                user_id=user_id,
                request_id=request_id,
                status="quota_blocked",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                latency_ms=latency,
                error_msg=quota_result.reason,
            )
            return self._error_response(
                request_id,
                model_code,
                f"Quota exceeded: {quota_result.reason}",
            )

        if quota_result.warning:
            logger.warning(
                f"Quota warning for org={org_id}, model={model_code}: {quota_result.reason}"
            )

        # --- P0: Hard cost gate per request ---
        # Estimate cost based on message lengths and model pricing
        try:
            est_input_tokens = estimated_tokens - (max_tokens or 4096)
            est_output_tokens = max_tokens or 4096
            est_cost = estimate_cost(est_input_tokens, est_output_tokens, model_code)
            if est_cost > policy.max_task_cost_usd:
                return self._error_response(
                    request_id,
                    model_code,
                    "Execution policy cost budget exceeded",
                )
            if estimated_tokens > (policy.max_input_tokens + policy.max_output_tokens):
                return self._error_response(
                    request_id,
                    model_code,
                    "Execution policy token budget exceeded",
                )
            if not await token_budget_manager.check_request_cost(est_cost):
                logger.warning(
                    f"[CostGate] Estimated cost ${est_cost:.4f} exceeds per-request cap "
                    f"${settings.LLM_MAX_COST_PER_REQUEST:.2f}. Downgrading to mini model."
                )
                # Auto-downgrade to mini model
                mini_model = settings.AI_MINI_MODEL
                if mini_model and mini_model != model_code:
                    model_code = mini_model
                    adapter, config = await self._create_adapter(model_code, org_id)
                    if not adapter or not config:
                        return self._error_response(
                            request_id, model_code, "Cost gate: mini model unavailable"
                        )
        except Exception as e:
            logger.debug(f"[CostGate] Pre-call cost estimation skipped: {e}")

        # --- Circuit breaker check ---
        if not circuit_breaker_manager.is_allowed(model_code):
            latency = int((time.monotonic() - start_ts) * 1000)
            await self._log_call(
                org_id=org_id,
                model_code=model_code,
                scene_code=scene_code,
                agent_code=agent_code,
                user_id=user_id,
                request_id=request_id,
                status="circuit_open",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                latency_ms=latency,
                error_msg="Circuit breaker is open",
            )
            return self._error_response(
                request_id, model_code, "Model circuit breaker is open"
            )

        # --- Create adapter ---
        adapter, config = await self._create_adapter(model_code, org_id)
        if not adapter or not config:
            return self._error_response(
                request_id,
                model_code,
                f"Failed to load adapter for model {model_code}",
            )

        # --- Context window check: auto-upgrade if prompt is too large ---
        model_code, config = await self._maybe_upgrade_for_context(
            model_code, org_id, config, system_prompt, messages, tools
        )
        if adapter.config.model_code != config.model_code:
            adapter, config = await self._create_adapter(model_code, org_id)
            if not adapter or not config:
                return self._error_response(
                    request_id,
                    model_code,
                    f"Failed to load upgraded model {model_code}",
                )

        tools = await _prune_runtime_tools(
            tools,
            messages=messages,
            scene_code=scene_code,
            agent_code=agent_code,
            tool_limit=policy.context_tool_limit,
        )

        # --- Build request ---
        chat_request = ChatRequest(
            scene_code=scene_code,
            agent_code=agent_code,
            user_id=user_id,
            system_prompt=system_prompt,
            messages=messages,
            tools=tools if config.supports_tools else None,
            temperature=temperature or config.default_temperature,
            max_tokens=max_tokens or config.max_tokens,
            stream=stream,
            request_id=request_id,
        )

        # --- Call adapter (with timeout protection and retry budget) ---
        llm_call_timeout = max(
            5.0,
            min(
                (config.timeout_ms or 60000) / 1000.0,
                policy.max_latency_ms / 1000.0,
                120.0,
            ),
        )
        max_attempts = max(1, min((config.max_retries or 0) + 1, 3))
        try:
            response = None
            last_error: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    async with tenant_throttle.acquire(org_id or "default"):
                        response = await asyncio.wait_for(
                            adapter.chat(chat_request),
                            timeout=llm_call_timeout,
                        )
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt >= max_attempts - 1 or not _is_transient_llm_error(exc):
                        raise
                    sleep_s = min(0.5 * (2**attempt), 2.0)
                    logger.warning(
                        "[LLMRetry] transient failure model=%s attempt=%d/%d sleep=%.1fs error=%s",
                        model_code,
                        attempt + 1,
                        max_attempts,
                        sleep_s,
                        str(exc)[:160],
                    )
                    await asyncio.sleep(sleep_s)

            if response is None:
                raise last_error or RuntimeError("LLM call failed without response")

            latency = int((time.monotonic() - start_ts) * 1000)
            response.exec_time_ms = latency

            # Record success with circuit breaker
            circuit_breaker_manager.record_success(model_code)

            input_tokens = response.usage.get("input_tokens", 0)
            output_tokens = response.usage.get("output_tokens", 0)
            cost = response.usage.get("call_cost", 0.0)
            if not input_tokens or not output_tokens or not cost:
                estimated_usage = _estimate_chat_usage(
                    model_code=model_code,
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools if config.supports_tools else None,
                    output_text=response.content,
                    max_tokens=chat_request.max_tokens,
                )
                input_tokens = input_tokens or estimated_usage["input_tokens"]
                output_tokens = output_tokens or estimated_usage["output_tokens"]
                cost = cost or estimated_usage["call_cost"]
                response.usage = {
                    **response.usage,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "call_cost": cost,
                    "estimated": True,
                }

            # Record quota usage
            await record_usage(
                tenant_id=org_id,
                model_code=model_code,
                user_id=user_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
            )

            # Log the call
            await self._log_call(
                org_id=org_id,
                model_code=model_code,
                scene_code=scene_code,
                agent_code=agent_code,
                user_id=user_id,
                request_id=request_id,
                status="success",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                latency_ms=latency,
            )

            return response

        except Exception as e:
            latency = int((time.monotonic() - start_ts) * 1000)
            error_msg = str(e)
            logger.error(
                f"LLM call failed for model={model_code}, request_id={request_id}: {error_msg}",
                exc_info=True,
            )

            # Record failure with circuit breaker
            circuit_breaker_manager.record_failure(model_code)

            await self._log_call(
                org_id=org_id,
                model_code=model_code,
                scene_code=scene_code,
                agent_code=agent_code,
                user_id=user_id,
                request_id=request_id,
                status="error",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                latency_ms=latency,
                error_msg=error_msg,
            )

            return self._error_response(request_id, model_code, error_msg)

    async def stream_chat(
        self,
        scene_code: str,
        agent_code: str,
        user_id: str,
        org_id: str,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = True,
        request_id: str | None = None,
    ) -> AsyncIterator[ChatResponse]:
        """
        Streaming chat completion.

        Yields partial ChatResponse objects as they arrive from the
        provider.  Quota is checked up front; usage is recorded after
        the stream completes.
        """
        request_id = request_id or str(uuid.uuid4())
        start_ts = time.monotonic()
        policy = await ai_execution_policy_service.get_policy(org_id)
        max_tokens = min(
            max_tokens or policy.max_output_tokens,
            policy.max_output_tokens,
        )

        # --- Resolve model ---
        model_code = await self._resolve_model(scene_code, agent_code, org_id)
        if not model_code:
            yield self._error_response(
                request_id, "", "No model configured for this scene/agent"
            )
            return

        # --- Quota check ---
        estimated_tokens = (
            sum(len(m.get("content", "")) // 4 for m in messages)
            + len(system_prompt) // 4
            + (max_tokens or 4096)
        )
        if estimated_tokens > policy.max_input_tokens + policy.max_output_tokens:
            yield self._error_response(
                request_id,
                model_code,
                "Execution policy token budget exceeded",
            )
            return
        estimated_cost = estimate_cost(
            max(0, estimated_tokens - max_tokens), max_tokens, model_code
        )
        if (
            estimated_cost > policy.max_task_cost_usd
            or not await token_budget_manager.check_request_cost(estimated_cost)
        ):
            yield self._error_response(
                request_id,
                model_code,
                "Execution policy cost budget exceeded",
            )
            return
        quota_result = await check_quota(
            tenant_id=org_id,
            model_code=model_code,
            user_id=user_id,
            estimated_tokens=estimated_tokens,
        )
        if not quota_result.allowed:
            yield self._error_response(
                request_id,
                model_code,
                f"Quota exceeded: {quota_result.reason}",
            )
            return

        if quota_result.warning:
            logger.warning(
                f"Quota warning for org={org_id}, model={model_code}: {quota_result.reason}"
            )

        # --- Circuit breaker check ---
        if not circuit_breaker_manager.is_allowed(model_code):
            yield self._error_response(
                request_id, model_code, "Model circuit breaker is open"
            )
            return

        # --- Create adapter ---
        adapter, config = await self._create_adapter(model_code, org_id)
        if not adapter or not config:
            yield self._error_response(
                request_id,
                model_code,
                f"Failed to load adapter for model {model_code}",
            )
            return

        # --- Context window check: auto-upgrade if prompt is too large ---
        model_code, config = await self._maybe_upgrade_for_context(
            model_code, org_id, config, system_prompt, messages, tools
        )
        if adapter.config.model_code != config.model_code:
            adapter, config = await self._create_adapter(model_code, org_id)
            if not adapter or not config:
                yield self._error_response(
                    request_id,
                    model_code,
                    f"Failed to load upgraded model {model_code}",
                )
                return

        tools = await _prune_runtime_tools(
            tools,
            messages=messages,
            scene_code=scene_code,
            agent_code=agent_code,
            tool_limit=policy.context_tool_limit,
        )

        # --- Build request ---
        chat_request = ChatRequest(
            scene_code=scene_code,
            agent_code=agent_code,
            user_id=user_id,
            system_prompt=system_prompt,
            messages=messages,
            tools=tools if config.supports_tools else None,
            temperature=temperature or config.default_temperature,
            max_tokens=min(max_tokens, config.max_tokens),
            stream=True,
            request_id=request_id,
        )

        # --- Stream from adapter ---
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0
        streamed_content_parts: list[str] = []

        try:
            async with tenant_throttle.acquire(org_id or "default"):
                async for chunk in adapter.stream_chat(chat_request):
                    if (time.monotonic() - start_ts) * 1000 > policy.max_latency_ms:
                        raise TimeoutError("Execution policy deadline exceeded")
                    chunk.exec_time_ms = int((time.monotonic() - start_ts) * 1000)

                    total_input_tokens = chunk.usage.get(
                        "input_tokens", total_input_tokens
                    )
                    total_output_tokens = chunk.usage.get(
                        "output_tokens", total_output_tokens
                    )
                    total_cost = chunk.usage.get("call_cost", total_cost)
                    if chunk.content:
                        streamed_content_parts.append(chunk.content)

                    yield chunk

            # --- Post-stream bookkeeping ---
            circuit_breaker_manager.record_success(model_code)
            if not total_input_tokens or not total_output_tokens or not total_cost:
                estimated_usage = _estimate_chat_usage(
                    model_code=model_code,
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools if config.supports_tools else None,
                    output_text="".join(streamed_content_parts),
                    max_tokens=chat_request.max_tokens,
                )
                total_input_tokens = (
                    total_input_tokens or estimated_usage["input_tokens"]
                )
                total_output_tokens = (
                    total_output_tokens or estimated_usage["output_tokens"]
                )
                total_cost = total_cost or estimated_usage["call_cost"]
                logger.warning(
                    "[LLMUsage] Streaming usage missing for model=%s request=%s; estimated tokens input=%s output=%s cost=%.6f",
                    model_code,
                    request_id,
                    total_input_tokens,
                    total_output_tokens,
                    total_cost,
                )

            await record_usage(
                tenant_id=org_id,
                model_code=model_code,
                user_id=user_id,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                cost=total_cost,
            )

            latency = int((time.monotonic() - start_ts) * 1000)
            await self._log_call(
                org_id=org_id,
                model_code=model_code,
                scene_code=scene_code,
                agent_code=agent_code,
                user_id=user_id,
                request_id=request_id,
                status="success",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                cost=total_cost,
                latency_ms=latency,
            )

        except Exception as e:
            latency = int((time.monotonic() - start_ts) * 1000)
            error_msg = str(e)
            logger.error(
                f"Streaming LLM call failed for model={model_code}, request_id={request_id}: {error_msg}",
                exc_info=True,
            )

            circuit_breaker_manager.record_failure(model_code)

            await self._log_call(
                org_id=org_id,
                model_code=model_code,
                scene_code=scene_code,
                agent_code=agent_code,
                user_id=user_id,
                request_id=request_id,
                status="error",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                cost=total_cost,
                latency_ms=latency,
                error_msg=error_msg,
            )

            # --- Backup model retry ---
            backup_code = await self._get_backup_model(
                scene_code, agent_code, org_id, exclude=model_code
            )
            if backup_code:
                logger.info(
                    f"Stream retrying with backup model '{backup_code}' after primary '{model_code}' failed"
                )
                backup_adapter, backup_config = await self._create_adapter(
                    backup_code, org_id
                )
                if backup_adapter and backup_config:
                    backup_request = ChatRequest(
                        scene_code=scene_code,
                        agent_code=agent_code,
                        user_id=user_id,
                        system_prompt=system_prompt,
                        messages=messages,
                        tools=tools if backup_config.supports_tools else None,
                        temperature=temperature or backup_config.default_temperature,
                        max_tokens=max_tokens or backup_config.max_tokens,
                        stream=True,
                        request_id=request_id,
                    )
                    try:
                        backup_start = time.monotonic()
                        async for chunk in backup_adapter.stream_chat(backup_request):
                            chunk.exec_time_ms = int(
                                (time.monotonic() - backup_start) * 1000
                            )
                            yield chunk
                        circuit_breaker_manager.record_success(backup_code)
                        return
                    except Exception as backup_e:
                        logger.error(
                            f"Backup stream also failed for model={backup_code}: {backup_e}"
                        )
                        circuit_breaker_manager.record_failure(backup_code)

            yield self._error_response(request_id, model_code, error_msg)

    async def embedding(
        self,
        texts: list[str],
        org_id: str,
        model_code: str | None = None,
    ) -> EmbeddingResponse:
        """
        Generate embeddings for a list of texts.

        If model_code is not provided, looks for a schedule rule with
        scene_code='embedding'.
        """
        request_id = str(uuid.uuid4())
        start_ts = time.monotonic()

        # Resolve model code
        if not model_code:
            model_code = await self._resolve_model("embedding", "*", org_id)
        if not model_code:
            logger.error(f"No embedding model configured for org={org_id}")
            return EmbeddingResponse(
                request_id=request_id,
                model_code="",
                embeddings=[],
                usage={"input_tokens": 0, "total_tokens": 0, "call_cost": 0.0},
            )

        # Create adapter
        adapter, config = await self._create_adapter(model_code, org_id)
        if not adapter or not config:
            logger.error(f"Failed to create embedding adapter for {model_code}")
            return EmbeddingResponse(
                request_id=request_id,
                model_code=model_code,
                embeddings=[],
                usage={"input_tokens": 0, "total_tokens": 0, "call_cost": 0.0},
            )

        try:
            response = await adapter.embedding(texts)
            response.request_id = request_id
            response.exec_time_ms = int((time.monotonic() - start_ts) * 1000)

            circuit_breaker_manager.record_success(model_code)

            total_tokens = response.usage.get("total_tokens", 0)
            cost = response.usage.get("call_cost", 0.0)

            await record_usage(
                tenant_id=org_id,
                model_code=model_code,
                user_id="system",
                input_tokens=total_tokens,
                output_tokens=0,
                cost=cost,
            )

            await self._log_call(
                org_id=org_id,
                model_code=model_code,
                scene_code="embedding",
                agent_code="*",
                user_id="system",
                request_id=request_id,
                status="success",
                input_tokens=response.usage.get("input_tokens", 0),
                output_tokens=0,
                cost=cost,
                latency_ms=response.exec_time_ms,
            )

            return response

        except Exception as e:
            latency = int((time.monotonic() - start_ts) * 1000)
            error_msg = str(e)
            logger.error(
                f"Embedding call failed for model={model_code}: {error_msg}",
                exc_info=True,
            )

            circuit_breaker_manager.record_failure(model_code)

            await self._log_call(
                org_id=org_id,
                model_code=model_code,
                scene_code="embedding",
                agent_code="*",
                user_id="system",
                request_id=request_id,
                status="error",
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                latency_ms=latency,
                error_msg=error_msg,
            )

            return EmbeddingResponse(
                request_id=request_id,
                model_code=model_code,
                embeddings=[],
                usage={"input_tokens": 0, "total_tokens": 0, "call_cost": 0.0},
                exec_time_ms=latency,
            )
