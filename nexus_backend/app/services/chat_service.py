"""Chat Service for Nexus AI
P4 Enhancement: Chat Service (Build Trigger: 20250211-0900)

Handles:
- OpenAI API interaction (Streaming)
- Recursive tool execution with thinking chain visualization
- Context management
- Content moderation integration
- Agent state tracking (Plan → Execute → Reflect cycle)
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

import httpx
import jsonschema

from app.core.config import settings
from app.core.database import supabase
from app.core.prompts_registry import SYSTEM_PROMPTS
from app.core.trace_logger import TraceLogger
from app.services.cache_service import cache_service
from app.services.content_moderation import (
    check_user_input,
    sanitize_output,
    scan_content,
)
from app.services.token_service import (
    record_completion,
    token_counter,
    usage_tracker,
    validate_request_tokens,
)
from app.tools import get_all_tools_schema, get_tool


def _json(obj: Any) -> str:
    """JSON serialize preserving Chinese characters."""
    return json.dumps(obj, ensure_ascii=False)


logger = logging.getLogger(__name__)

# P1 Fix #12: Make chat history window configurable
MAX_HISTORY = getattr(settings, "MAX_CHAT_HISTORY", 10)


class AgentPhase(StrEnum):
    """Agent execution phases for thinking chain visualization"""

    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    RESPONDING = "responding"


@dataclass
class ThinkingStep:
    """Represents a single step in the agent's thinking chain"""

    phase: str
    content: str
    tool_name: str | None = None
    tool_args: dict | None = None
    tool_result: str | None = None
    timestamp: float = None
    duration_ms: int | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


class ChatService:
    TOOLS = get_all_tools_schema()

    @staticmethod
    async def get_system_prompt(
        agent_name: str, db_client: Any | None = None, user_id: str | None = None
    ) -> str:
        """Get formatted system prompt for agent (P1 Fix #29: Fetch from DB with local fallback)
        #24: Integrates A/B test variant selection when user_id is provided.
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        prompt_key = "default_fallback"
        if agent_name in ["@销售指挥官", "sales_commander"]:
            prompt_key = "sales_commander"
        elif agent_name in ["@审批管家", "approval_manager"]:
            prompt_key = "approval_manager"
        elif agent_name in ["@绩效教练", "performance_coach"]:
            prompt_key = "performance_coach"
        elif agent_name in ["@总裁助理", "boss_assistant"]:
            prompt_key = "boss_assistant"

        # 0. Try A/B test variant (if user_id provided)
        if user_id:
            try:
                from app.services.prompt_version_service import prompt_version_service
                variant = prompt_version_service.get_ab_test_variant(prompt_key, user_id)
                if variant and variant.content:
                    try:
                        return variant.content.format(current_time=now_str)
                    except Exception:
                        return variant.content
            except Exception as e:
                logger.debug(f"A/B test variant lookup failed: {e}")

        # 1. Try Cache
        cache_key = f"prompt:{prompt_key}"
        cached_prompt = await cache_service.get(cache_key)
        if cached_prompt:
            try:
                return cached_prompt.format(current_time=now_str)
            except Exception:
                return cached_prompt

        # 2. Try DB
        try:
            client = db_client or supabase
            res = (
                await client.table("prompts")
                .select("content")
                .eq("name", prompt_key)
                .maybe_single()
                .execute()
            )
            if res and res.data:
                raw_prompt = res.data["content"]
                await cache_service.set(cache_key, raw_prompt, ttl=3600)
                return raw_prompt.format(current_time=now_str)
        except Exception as e:
            logger.warning(f"Failed to fetch prompt {prompt_key} from DB: {e}")

        # 3. Fallback to hardcoded registry
        raw_prompt = SYSTEM_PROMPTS.get(prompt_key, SYSTEM_PROMPTS["default_fallback"])
        try:
            return raw_prompt.format(current_time=now_str)
        except Exception:
            return raw_prompt

    @staticmethod
    async def _get_cached_user_role(
        user_id: str, db_client: Any | None = None
    ) -> str:
        """Helper to get user role (cached)"""
        cached = await cache_service.get_user_role(user_id)
        if cached:
            return cached

        try:
            client = db_client or supabase
            res = (
                await client.table("users")
                .select("role")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
            role = res.data.get("role", "employee") if res.data else "employee"
            await cache_service.set_user_role(user_id, role)
            return role
        except Exception as e:
            logger.error(f"Role fetch error: {e}")
            return "employee"

    @staticmethod
    async def execute_tool(
        name: str,
        args: dict[str, Any],
        user_id: str,
        config: dict = None,
        system_confirmed: bool = False,
        db_client: Any | None = None,
    ) -> str:
        """Execute tool with RBAC, System-level Confirmation Gate, and Retry"""
        tool = get_tool(name)
        if not tool:
            return f"Error: Tool {name} not found."

        # 1. RBAC Check
        if tool.required_role not in ["all", "ai_assistant"]:
            user_role = await ChatService._get_cached_user_role(
                user_id, db_client=db_client
            )
            if tool.required_role == "boss" and user_role not in ["boss", "founder"]:
                return f"⛔ Permission Denied: Tool requires [Boss] role. You are [{user_role}]."
            elif tool.required_role == "manager" and user_role not in [
                "manager",
                "boss",
                "founder",
            ]:
                return f"⛔ Permission Denied: Tool requires [Manager] role. You are [{user_role}]."

        # 2. System-level Confirmation Gate (P0 Fix #10)
        # This runs BEFORE the tool's own logic, preventing LLM from bypassing confirm
        # P0 Fix #2: Pass system_confirmed to strict check
        confirmation_msg = tool.check_confirmation(
            args, system_confirmed=system_confirmed
        )
        if confirmation_msg is not None:
            logger.info(f"[HITL Gate] Tool {name} blocked - awaiting user confirmation")
            return confirmation_msg

        # 3. Retry Logic with timeout
        for attempt in range(3):
            try:
                result = await asyncio.wait_for(
                    tool.run(args, user_id, config=config),
                    timeout=30.0,  # 30s timeout per tool execution
                )
                return result
            except TimeoutError:
                return f"Error: Tool {name} timed out after 30 seconds."
            except Exception as e:
                if attempt == 2:
                    return f"Error: Tool {name} failed after 3 attempts: {str(e)}"
                await asyncio.sleep(0.5 * (attempt + 1))
        return "Error: Unknown tool execution failure"

    @staticmethod
    async def save_message(
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        agent: str = None,
        metadata: dict = None,
        db_client: Any | None = None,
    ):
        """Save a message to the database for persistence"""
        try:
            client = db_client or supabase
            data = {
                "user_id": user_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "agent": agent,
                "metadata": metadata or {},
            }
            # Fixed P1: added await
            await client.table("chat_messages").insert(data).execute()
        except Exception as e:
            logger.error(f"Failed to save chat message: {str(e)}")

    @staticmethod
    async def stream_response(
        messages: list[dict],
        config: dict,
        user_id: str,
        tracer: TraceLogger | None = None,
        system_confirmed: bool = False,
        session_id: str | None = None,
        db_client: Any | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream response from OpenAI with recursive tool execution, token tracking, and moderation.
        """
        # Ensure we have a DB client (fallback to global for robustness)
        client_db = db_client or supabase
        # P0 Fix #4: Save the last user message to persistence
        if messages and messages[-1]["role"] == "user":
            user_msg = messages[-1]
            task = asyncio.create_task(
                ChatService.save_message(
                    user_id=user_id,
                    session_id=session_id,
                    role="user",
                    content=user_msg["content"],
                    agent=messages[0].get("agent") if messages else None,
                    db_client=client_db,
                )
            )
            task.add_done_callback(
                lambda t: (
                    logger.error(f"Failed to save message: {t.exception()}")
                    if t.exception()
                    else None
                )
            )

        # 0. Safety Check & Sanitization
        api_key = config.get("api_key")
        base_url = config.get("base_url", "https://api.openai.com/v1")
        model = config.get("model", "gpt-4o")

        # P1 Fix #13: Load user's daily usage from DB into memory cache on first call
        await usage_tracker.ensure_loaded(user_id)

        if not base_url.endswith("/v1"):
            base_url = f"{base_url.rstrip('/')}/v1"
        chat_endpoint = f"{base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        # 1. P1 Optimization: Token & Cost Limit Check
        # Check limits BEFORE making the API call to save costs
        is_allowed, input_tokens, reason = validate_request_tokens(
            messages, model, user_id
        )
        if not is_allowed:
            yield f"data: {_json({'choices': [{'delta': {'content': f'⛔ 请求被拒绝 (超出限制): {reason}'}}]})}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 2. P1 Optimization: Content Moderation (Input)
        last_msg = messages[-1].get("content", "") if messages else ""
        if isinstance(last_msg, str):
            is_safe, warning = check_user_input(last_msg)
            if not is_safe:
                yield f"data: {_json({'choices': [{'delta': {'content': f'⛔ 安全警告: {warning}'}}]})}\n\n"
                yield "data: [DONE]\n\n"
                return

        if tracer:
            tracer.log_start(messages)

        full_response_content = ""

        # A. Semantic Cache Lookup (P0 Fix: Move to before LLM call)
        last_query = (
            messages[-1].get("content")
            if messages and messages[-1]["role"] == "user"
            else ""
        )
        if last_query and user_id:
            # Lazy import inside method to avoid circular deps if any, or just keep as is
            from app.services.semantic_cache import semantic_cache_service

            # P1 Fix: Use the user's latest message for cache lookup
            cached_res = await semantic_cache_service.get_cache(last_query, user_id)
            if cached_res:
                logger.info(f"Semantic cache hit for user {user_id}")
                # Simulate streaming for cached response
                words = cached_res.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield f"data: {_json({'choices': [{'delta': {'content': chunk}}]})}\n\n"
                    await asyncio.sleep(0.005)
                # Record token usage even for cache hits
                try:
                    cache_tokens = token_counter.count_tokens(cached_res, model)
                    await record_completion(user_id, input_tokens, cache_tokens, model)
                except Exception as e:
                    logger.warning(f"Failed to record cache hit tokens: {e}")
                yield "data: [DONE]\n\n"
                if tracer:
                    tracer.log_end(total_tokens=input_tokens)
                return

        async def _call_api(msgs):
            payload = {
                "model": model,
                "messages": msgs,
                "tools": ChatService.TOOLS,
                "tool_choice": "auto",
                "stream": True,
                "temperature": 0.5,
                "stream_options": {"include_usage": True},
            }
            try:
                async with httpx.AsyncClient(timeout=60.0) as client, client.stream(
                    "POST", chat_endpoint, headers=headers, json=payload
                ) as response:
                    if response.status_code != 200:
                        err = await response.aread()
                        yield f"error: AI Service Error ({response.status_code}): {err.decode()[:200]}"
                        return
                    async for line in response.aiter_lines():
                        yield line
            except Exception as e:
                logger.error(f"LLM API connection failed: {e}")
                yield f"error: Connection Failed: {str(e)}"

        # Main Loop (Recursive Tool Use) with Thinking Chain Visualization
        max_iterations = 5
        thinking_steps: list[ThinkingStep] = []

        def emit_thinking_step(step: ThinkingStep):
            """Helper to emit thinking step via SSE"""
            return f"data: {_json({'thinking_step': step.to_dict()})}\n\n"

        for iteration in range(max_iterations):
            iteration_start = time.time()

            # Phase 1: Planning - Emit thinking status
            if iteration == 0:
                planning_step = ThinkingStep(
                    phase=AgentPhase.PLANNING.value,
                    content="正在分析用户意图，规划执行策略...",
                )
                thinking_steps.append(planning_step)
                yield emit_thinking_step(planning_step)
                yield f"data: {_json({'status': '正在思考...'})}\n\n"
            else:
                # Reflection phase for subsequent iterations
                reflect_step = ThinkingStep(
                    phase=AgentPhase.REFLECTING.value,
                    content=f"正在分析工具执行结果，决定下一步操作... (迭代 {iteration + 1}/{max_iterations})",
                )
                thinking_steps.append(reflect_step)
                yield emit_thinking_step(reflect_step)

            tool_calls_map = {}
            has_tool_call = False

            total_usage_chunk = None

            async for line in _call_api(messages):
                if line.startswith("error: "):
                    yield f"data: {_json({'choices': [{'delta': {'content': f' {line}'}}]})}\n\n"
                    return

                if not line.startswith("data: "):
                    continue
                line_data = line[6:].strip()
                if line_data == "[DONE]":
                    break

                try:
                    parsed = json.loads(line_data)
                    if not parsed["choices"]:
                        # Handle usage chunk (OpenAI standard)
                        if "usage" in parsed:
                            usage_data = parsed["usage"]
                            # Accumulate usage if needed, or use directly
                            # For now, we prefer the usage reported by the API
                            total_usage_chunk = usage_data
                        continue

                    delta = parsed["choices"][0]["delta"]

                    if "tool_calls" in delta:
                        has_tool_call = True
                        for tc in delta["tool_calls"]:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls_map:
                                tool_calls_map[idx] = {"id": "", "name": "", "args": ""}

                            if tc.get("id"):
                                tool_calls_map[idx]["id"] = tc["id"]
                            if tc.get("function"):
                                fn = tc["function"]
                                if fn.get("name"):
                                    tool_calls_map[idx]["name"] = fn["name"]
                                if fn.get("arguments"):
                                    tool_calls_map[idx]["args"] += fn["arguments"]
                        continue

                    # Stream content to user if NOT a tool call
                    if not has_tool_call:
                        content = delta.get("content")
                        if content:
                            full_response_content += content
                            # Clear status when generating content
                            if iteration == 0 and len(full_response_content) < 20:
                                yield f"data: {_json({'status': ''})}\n\n"
                            yield f"{line}\n\n"

                except json.JSONDecodeError:
                    continue

            # Execute Tools if any
            if has_tool_call:
                # Add assistant message with tool calls to history
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["args"],
                                },
                            }
                            for tc in tool_calls_map.values()
                        ],
                    }
                )

                # Execute tools in parallel
                tool_tasks = []
                tool_indices = sorted(tool_calls_map.keys())

                # Report Status with thinking step
                tool_names_list = [tool_calls_map[idx]["name"] for idx in tool_indices]
                joined_tool_names = ", ".join(tool_names_list)

                # Emit executing phase thinking step
                exec_step = ThinkingStep(
                    phase=AgentPhase.EXECUTING.value,
                    content=f"正在执行工具: {joined_tool_names}",
                    tool_name=joined_tool_names,
                )
                thinking_steps.append(exec_step)
                yield emit_thinking_step(exec_step)
                yield f"data: {_json({'status': f'正在调用: {joined_tool_names}...'})}\n\n"

                for idx in tool_indices:
                    tc = tool_calls_map[idx]
                    try:
                        args = json.loads(tc["args"]) if tc["args"] else {}
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Invalid JSON args for tool {tc['name']}: {tc['args'][:100]}"
                        )
                        args = {}

                    # P0 Fix #11: Validate tool args against JSON Schema before execution
                    tool_obj = get_tool(tc["name"])
                    if tool_obj and args:
                        try:
                            schema = tool_obj.parameters
                            jsonschema.validate(instance=args, schema=schema)
                        except jsonschema.ValidationError as ve:
                            logger.warning(
                                f"Tool {tc['name']} args validation failed: {ve.message}"
                            )
                            # Don't block — feed error back to LLM so it can self-correct
                            tool_tasks.append(
                                asyncio.create_task(
                                    asyncio.sleep(
                                        0, result=f"参数校验失败: {ve.message}"
                                    )
                                )
                            )
                            if tracer:
                                tracer.log_tool_plan(
                                    tc["name"], {"validation_error": ve.message}
                                )
                            continue
                        except jsonschema.SchemaError:
                            pass  # Schema itself is invalid, skip validation

                    if tracer:
                        tracer.log_tool_plan(tc["name"], args)
                    tool_tasks.append(
                        ChatService.execute_tool(
                            tc["name"],
                            args,
                            user_id,
                            config=config,
                            system_confirmed=system_confirmed,
                            db_client=client_db,
                        )
                    )

                results = await asyncio.gather(*tool_tasks)

                # Add tool results to history with thinking step tracking
                for idx, result in zip(tool_indices, results, strict=False):
                    tc = tool_calls_map[idx]
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": tc["name"],
                            "content": str(result),
                        }
                    )

                    # Emit tool result as thinking step
                    tool_result_step = ThinkingStep(
                        phase=AgentPhase.EXECUTING.value,
                        content=f"工具 {tc['name']} 执行完成",
                        tool_name=tc["name"],
                        tool_result=str(result)[:500] if result else None,
                        duration_ms=int((time.time() - iteration_start) * 1000),
                    )
                    thinking_steps.append(tool_result_step)
                    yield emit_thinking_step(tool_result_step)

                    if tracer:
                        tracer.log_tool_execution(tc["name"], "completed", str(result))

                # Emit reflecting phase
                reflect_step = ThinkingStep(
                    phase=AgentPhase.REFLECTING.value, content="正在分析执行结果..."
                )
                thinking_steps.append(reflect_step)
                yield emit_thinking_step(reflect_step)
                yield f"data: {_json({'status': '正在分析执行结果...'})}\n\n"

            else:
                # No tool calls in this turn, emit responding phase
                if full_response_content:
                    respond_step = ThinkingStep(
                        phase=AgentPhase.RESPONDING.value, content="正在生成最终回复..."
                    )
                    thinking_steps.append(respond_step)
                    yield emit_thinking_step(respond_step)
                break

        # Emit final thinking chain summary
        if thinking_steps:
            yield f"data: {_json({'thinking_chain_complete': True, 'total_steps': len(thinking_steps)})}\n\n"

        # B. Real LLM Execution
        # 3. P1 Optimization: Token Usage Recording & Output Sanitization
        sanitized_content = full_response_content
        try:
            # Output Sanitization - scan for PII/violations in AI output
            is_safe, violations = scan_content(full_response_content)
            if not is_safe:
                logger.warning(
                    f"Output contained {len(violations)} violations - sending sanitized correction"
                )
                # Apply sanitization to replace PII/sensitive content
                sanitized_content = sanitize_output(full_response_content)
                if sanitized_content != full_response_content:
                    # Emit a correction event so frontend replaces the streamed content
                    yield f"data: {_json({'sanitized_content': sanitized_content, 'violation_count': len(violations)})}\n\n"
                    logger.info(
                        f"Sanitized {len(violations)} violations from AI output before delivery"
                    )

            # Use API reported usage if available, else fallback to estimation
            if total_usage_chunk:
                await record_completion(
                    user_id,
                    total_usage_chunk.get("prompt_tokens", input_tokens),
                    total_usage_chunk.get("completion_tokens", 0),
                    model,
                )
            else:
                output_tokens = token_counter.count_tokens(full_response_content, model)
                await record_completion(user_id, input_tokens, output_tokens, model)
        except Exception as e:
            logger.error(f"Post-stream processing error: {e}")

        # Final assistant response summary for token tracking and audit
        # Save finalized assistant message
        task = asyncio.create_task(
            ChatService.save_message(
                user_id=user_id,
                session_id=session_id,
                role="assistant",
                content=sanitized_content,
                agent=messages[0].get("agent") if messages else None,
                db_client=client_db,
            )
        )
        task.add_done_callback(
            lambda t: (
                logger.error(f"Failed to save message: {t.exception()}")
                if t.exception()
                else None
            )
        )

        # P2: Save to Semantic Cache
        if last_query and sanitized_content:
            from app.services.semantic_cache import semantic_cache_service

            asyncio.create_task(
                semantic_cache_service.set_cache(last_query, sanitized_content, user_id)
            )

        if tracer:
            try:
                # Fallback calculation if record_completion wasn't called/failed
                t_tokens = (
                    total_usage_chunk.get("total_tokens", 0) if total_usage_chunk else 0
                )
                tracer.log_end(total_tokens=t_tokens)
            except Exception:
                tracer.log_end()
        yield "data: [DONE]\n\n"
