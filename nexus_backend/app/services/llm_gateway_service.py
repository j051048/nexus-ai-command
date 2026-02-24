"""
LLM Model Adaptation Gateway - Central Service

The gateway is the single entry point for all LLM calls in the system.
It handles:
- Model resolution via schedule rules (scene + agent -> model)
- Config loading with in-memory caching and API key decryption
- Quota checks before each call
- Circuit breaker integration for automatic failover
- Adapter instantiation and request dispatch
- Usage recording and call logging
- Automatic fallback to backup models on failure
"""

import logging
import time
import uuid
from typing import AsyncIterator

from app.core.database import supabase
from app.services.encryption_service import encryption_service
from app.services.llm_adapters.base import (
    BaseModelAdapter,
    ChatRequest,
    ChatResponse,
    EmbeddingResponse,
    ModelConfig,
)
from app.services.llm_adapters.registry import get_adapter
from app.services.llm_circuit_breaker import circuit_breaker_manager
from app.services.llm_quota_service import check_quota, record_usage

logger = logging.getLogger(__name__)


class LLMGatewayService:
    """
    Central hub for all LLM interactions.

    Resolves which model to use based on scene/agent schedule rules,
    manages caching, quota enforcement, circuit breaking, and logging.
    """

    def __init__(self):
        # Cache: key -> (value, loaded_at_timestamp)
        self._model_cache: dict[str, tuple[ModelConfig, float]] = {}
        self._schedule_cache: dict[str, tuple[dict, float]] = {}
        self._CACHE_TTL: int = 300  # 5 minutes

    # ------------------------------------------------------------------
    # Internal: Model config loading
    # ------------------------------------------------------------------

    async def _load_model_config(
        self, model_code: str, org_id: str
    ) -> ModelConfig | None:
        """
        Load a model configuration from the llm_model_config table.

        Results are cached for _CACHE_TTL seconds.  The encrypted api_key
        stored in the database is decrypted before being placed into the
        returned ModelConfig.

        Returns None if the model is not found or the database is
        unavailable.
        """
        cache_key = f"{org_id}:{model_code}"
        now = time.time()

        # Check cache
        if cache_key in self._model_cache:
            config, loaded_at = self._model_cache[cache_key]
            if now - loaded_at < self._CACHE_TTL:
                return config

        if not supabase:
            logger.warning("Database not available - cannot load model config")
            return None

        try:
            res = (
                await supabase.table("llm_model_config")
                .select("*")
                .eq("model_code", model_code)
                .eq("org_id", org_id)
                .eq("is_active", True)
                .execute()
            )

            rows = res.data or []
            if not rows:
                logger.warning(
                    "No active model config found for "
                    f"model_code={model_code}, org_id={org_id}"
                )
                return None

            row = rows[0]

            # Decrypt the API key
            raw_api_key = row.get("api_key", "")
            try:
                api_key = encryption_service.decrypt(raw_api_key)
            except Exception as e:
                logger.error(
                    f"Failed to decrypt api_key for model {model_code}: {e}"
                )
                return None

            # Decrypt optional secret_key (used by some providers like Wenxin)
            raw_secret_key = row.get("secret_key") or ""
            secret_key = None
            if raw_secret_key:
                try:
                    secret_key = encryption_service.decrypt(raw_secret_key)
                except Exception as e:
                    logger.warning(
                        f"Failed to decrypt secret_key for model {model_code}: {e}"
                    )

            config = ModelConfig(
                model_code=row.get("model_code", model_code),
                model_name=row.get("model_name", model_code),
                provider_type=row.get("provider_type", "openai_compatible"),
                api_base_url=row.get("api_base_url", ""),
                api_key=api_key,
                secret_key=secret_key,
                model_id=row.get("model_id", ""),
                timeout_ms=row.get("timeout_ms", 60000),
                max_retries=row.get("max_retries", 2),
                max_tokens=row.get("max_tokens"),
                context_window=row.get("context_window"),
                supports_tools=row.get("supports_tools", True),
                supports_streaming=row.get("supports_streaming", True),
                default_temperature=float(row.get("default_temperature", 0.7)),
                default_top_p=float(row.get("default_top_p", 0.9)),
            )

            self._model_cache[cache_key] = (config, now)
            return config

        except Exception as e:
            logger.error(
                f"Error loading model config for {model_code}/{org_id}: {e}",
                exc_info=True,
            )
            return None

    # ------------------------------------------------------------------
    # Internal: Schedule rule resolution
    # ------------------------------------------------------------------

    async def _resolve_model(
        self, scene_code: str, agent_code: str, org_id: str
    ) -> str | None:
        """
        Look up the llm_schedule_rule table to find the model assigned
        to a given scene + agent combination.

        Returns the primary model_code.  If the primary model's circuit
        breaker is open, returns the backup_model_code instead.
        Returns None when no matching rule exists.
        """
        cache_key = f"{org_id}:{scene_code}:{agent_code}"
        now = time.time()

        # Check cache
        if cache_key in self._schedule_cache:
            rule, loaded_at = self._schedule_cache[cache_key]
            if now - loaded_at < self._CACHE_TTL:
                return self._pick_healthy_model(rule)

        if not supabase:
            logger.warning(
                "Database not available - cannot resolve model schedule"
            )
            return None

        try:
            # Try exact match first: scene + agent
            res = (
                await supabase.table("llm_schedule_rule")
                .select("*")
                .eq("scene_code", scene_code)
                .eq("agent_code", agent_code)
                .eq("org_id", org_id)
                .eq("is_active", True)
                .execute()
            )

            rows = res.data or []

            # Fallback: scene-level default (agent_code = '*' or empty)
            if not rows:
                res = (
                    await supabase.table("llm_schedule_rule")
                    .select("*")
                    .eq("scene_code", scene_code)
                    .eq("org_id", org_id)
                    .eq("is_active", True)
                    .in_("agent_code", ["*", ""])
                    .execute()
                )
                rows = res.data or []

            # Fallback: org-level default (scene_code = '*')
            if not rows:
                res = (
                    await supabase.table("llm_schedule_rule")
                    .select("*")
                    .eq("org_id", org_id)
                    .eq("is_active", True)
                    .in_("scene_code", ["*", ""])
                    .execute()
                )
                rows = res.data or []

            if not rows:
                logger.warning(
                    f"No schedule rule found for scene={scene_code}, "
                    f"agent={agent_code}, org={org_id}"
                )
                return None

            rule = rows[0]
            self._schedule_cache[cache_key] = (rule, now)
            return self._pick_healthy_model(rule)

        except Exception as e:
            logger.error(
                f"Error resolving model for scene={scene_code}, "
                f"agent={agent_code}, org={org_id}: {e}",
                exc_info=True,
            )
            return None

    def _pick_healthy_model(self, rule: dict) -> str | None:
        """
        From a schedule rule row, return the primary model if its circuit
        breaker allows requests; otherwise return the backup model.
        """
        primary = rule.get("primary_model_code") or rule.get("primary_model_id")
        backup = rule.get("backup_model_code") or rule.get("backup_model_id")

        if primary and circuit_breaker_manager.is_allowed(primary):
            return primary

        if primary:
            logger.warning(
                f"Primary model '{primary}' circuit is open, "
                f"attempting backup model '{backup}'"
            )

        if backup and circuit_breaker_manager.is_allowed(backup):
            return backup

        if backup:
            logger.error(
                f"Both primary '{primary}' and backup '{backup}' "
                "circuits are open"
            )

        # Return primary anyway as last resort (circuit breaker may
        # transition to half-open by the time the actual call is made)
        return primary

    # ------------------------------------------------------------------
    # Internal: Adapter creation helper
    # ------------------------------------------------------------------

    async def _create_adapter(
        self, model_code: str, org_id: str
    ) -> tuple[BaseModelAdapter, ModelConfig] | tuple[None, None]:
        """Load config and instantiate the appropriate adapter."""
        config = await self._load_model_config(model_code, org_id)
        if not config:
            return None, None

        try:
            adapter = get_adapter(config.provider_type, config)
            return adapter, config
        except ValueError as e:
            logger.error(f"Failed to create adapter for {model_code}: {e}")
            return None, None

    # ------------------------------------------------------------------
    # Public: Chat
    # ------------------------------------------------------------------

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
        )

        if response.finish_reason == "error":
            # Attempt backup model
            backup_code = await self._get_backup_model(
                scene_code, agent_code, org_id, exclude=model_code
            )
            if backup_code:
                logger.info(
                    f"Retrying with backup model '{backup_code}' "
                    f"after primary '{model_code}' failed"
                )
                backup_response = await self._try_chat_with_model(
                    model_code=backup_code,
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
    ) -> ChatResponse:
        """Execute a chat call against a single model with all guardrails."""

        # --- Quota check ---
        quota_result = await check_quota(
            tenant_id=org_id,
            model_code=model_code,
            user_id=user_id,
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
                request_id, model_code,
                f"Quota exceeded: {quota_result.reason}",
            )

        if quota_result.warning:
            logger.warning(
                f"Quota warning for org={org_id}, model={model_code}: "
                f"{quota_result.reason}"
            )

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
                request_id, model_code,
                f"Failed to load adapter for model {model_code}",
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

        # --- Call adapter ---
        try:
            response = await adapter.chat(chat_request)
            latency = int((time.monotonic() - start_ts) * 1000)
            response.exec_time_ms = latency

            # Record success with circuit breaker
            circuit_breaker_manager.record_success(model_code)

            input_tokens = response.usage.get("input_tokens", 0)
            output_tokens = response.usage.get("output_tokens", 0)
            cost = response.usage.get("call_cost", 0.0)

            # Record quota usage
            await record_usage(
                tenant_id=org_id,
                model_code=model_code,
                user_id=user_id,
                tokens=input_tokens + output_tokens,
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
                f"LLM call failed for model={model_code}, "
                f"request_id={request_id}: {error_msg}",
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

    # ------------------------------------------------------------------
    # Public: Streaming Chat
    # ------------------------------------------------------------------

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

        # --- Resolve model ---
        model_code = await self._resolve_model(scene_code, agent_code, org_id)
        if not model_code:
            yield self._error_response(
                request_id, "", "No model configured for this scene/agent"
            )
            return

        # --- Quota check ---
        quota_result = await check_quota(
            tenant_id=org_id,
            model_code=model_code,
            user_id=user_id,
        )
        if not quota_result.allowed:
            yield self._error_response(
                request_id, model_code,
                f"Quota exceeded: {quota_result.reason}",
            )
            return

        if quota_result.warning:
            logger.warning(
                f"Quota warning for org={org_id}, model={model_code}: "
                f"{quota_result.reason}"
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
                request_id, model_code,
                f"Failed to load adapter for model {model_code}",
            )
            return

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
            stream=True,
            request_id=request_id,
        )

        # --- Stream from adapter ---
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost = 0.0

        try:
            async for chunk in adapter.stream_chat(chat_request):
                chunk.exec_time_ms = int(
                    (time.monotonic() - start_ts) * 1000
                )

                # Accumulate usage from the final chunk (providers typically
                # report usage only in the last chunk)
                total_input_tokens = chunk.usage.get(
                    "input_tokens", total_input_tokens
                )
                total_output_tokens = chunk.usage.get(
                    "output_tokens", total_output_tokens
                )
                total_cost = chunk.usage.get("call_cost", total_cost)

                yield chunk

            # --- Post-stream bookkeeping ---
            circuit_breaker_manager.record_success(model_code)

            await record_usage(
                tenant_id=org_id,
                model_code=model_code,
                user_id=user_id,
                tokens=total_input_tokens + total_output_tokens,
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
                f"Streaming LLM call failed for model={model_code}, "
                f"request_id={request_id}: {error_msg}",
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

            yield self._error_response(request_id, model_code, error_msg)

    # ------------------------------------------------------------------
    # Public: Embedding
    # ------------------------------------------------------------------

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
                usage={
                    "input_tokens": 0,
                    "total_tokens": 0,
                    "call_cost": 0.0,
                },
            )

        # Create adapter
        adapter, config = await self._create_adapter(model_code, org_id)
        if not adapter or not config:
            logger.error(
                f"Failed to create embedding adapter for {model_code}"
            )
            return EmbeddingResponse(
                request_id=request_id,
                model_code=model_code,
                embeddings=[],
                usage={
                    "input_tokens": 0,
                    "total_tokens": 0,
                    "call_cost": 0.0,
                },
            )

        try:
            response = await adapter.embedding(texts)
            response.request_id = request_id
            response.exec_time_ms = int(
                (time.monotonic() - start_ts) * 1000
            )

            circuit_breaker_manager.record_success(model_code)

            total_tokens = response.usage.get("total_tokens", 0)
            cost = response.usage.get("call_cost", 0.0)

            await record_usage(
                tenant_id=org_id,
                model_code=model_code,
                user_id="system",
                tokens=total_tokens,
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
                usage={
                    "input_tokens": 0,
                    "total_tokens": 0,
                    "call_cost": 0.0,
                },
                exec_time_ms=latency,
            )

    # ------------------------------------------------------------------
    # Internal: Call logging
    # ------------------------------------------------------------------

    async def _log_call(
        self,
        org_id: str,
        model_code: str,
        scene_code: str,
        agent_code: str,
        user_id: str,
        request_id: str,
        status: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        latency_ms: int,
        error_msg: str | None = None,
    ) -> None:
        """
        Insert a record into the llm_call_log table for auditing and
        analytics.  Failures are logged but never propagated.
        """
        if not supabase:
            return

        try:
            row = {
                "id": str(uuid.uuid4()),
                "org_id": org_id,
                "model_code": model_code,
                "scene_code": scene_code,
                "agent_code": agent_code,
                "user_id": user_id,
                "request_id": request_id,
                "status": status,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "cost": cost,
                "latency_ms": latency_ms,
                "error_msg": error_msg,
            }
            await supabase.table("llm_call_log").insert(row).execute()
        except Exception as e:
            # Logging failures must never break the main flow
            logger.warning(f"Failed to log LLM call to database: {e}")

    # ------------------------------------------------------------------
    # Internal: Backup model lookup
    # ------------------------------------------------------------------

    async def _get_backup_model(
        self,
        scene_code: str,
        agent_code: str,
        org_id: str,
        exclude: str,
    ) -> str | None:
        """
        Look up the backup model from the cached schedule rule,
        excluding the already-failed model.
        """
        cache_key = f"{org_id}:{scene_code}:{agent_code}"
        if cache_key in self._schedule_cache:
            rule, _ = self._schedule_cache[cache_key]
            backup = (
                rule.get("backup_model_code")
                or rule.get("backup_model_id")
            )
            if backup and backup != exclude:
                if circuit_breaker_manager.is_allowed(backup):
                    return backup
        return None

    # ------------------------------------------------------------------
    # Public: Cache invalidation
    # ------------------------------------------------------------------

    def invalidate_cache(self, org_id: str | None = None) -> None:
        """
        Clear model config and schedule rule caches.

        If org_id is provided, only entries for that org are removed.
        If org_id is None, all caches are cleared.
        """
        if org_id is None:
            self._model_cache.clear()
            self._schedule_cache.clear()
            logger.info("All LLM gateway caches invalidated")
        else:
            model_keys = [
                k for k in self._model_cache if k.startswith(f"{org_id}:")
            ]
            for k in model_keys:
                del self._model_cache[k]

            schedule_keys = [
                k
                for k in self._schedule_cache
                if k.startswith(f"{org_id}:")
            ]
            for k in schedule_keys:
                del self._schedule_cache[k]

            logger.info(
                f"LLM gateway caches invalidated for org {org_id} "
                f"({len(model_keys)} model, "
                f"{len(schedule_keys)} schedule entries)"
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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


# ======================================================================
# Module-level singleton
# ======================================================================

llm_gateway = LLMGatewayService()
