"""
Graph Node: execute_node — parallel tool execution with RBAC & circuit breaker.
"""

import asyncio
import contextlib
import hashlib
import json as _json
import time

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig

from app.agent.node_helpers import (
    LONG_RUNNING_TOOLS,
    AgentConfig,
    AgentPhase,
    AgentState,
    ThinkingStep,
    ToolCallRecord,
    _format_validation_error,
    _try_extract_tool_names,
    get_tool,
    logger,
    plugin_system_service,
    record_tool_execution,
    tool_circuit_breaker,
)
from app.services.plugin_system_service import ExtensionPoint


async def _execute_single_tool(
    record: ToolCallRecord,
    config: AgentConfig,
    _idempotency_cache: dict = None,
) -> ToolCallRecord:
    """Execute a single tool with RBAC, confirmation gates, circuit breaker, idempotency, and retry."""
    # Evict old cache entries to prevent unbounded memory growth
    if _idempotency_cache is None:
        _idempotency_cache = {}
    if len(_idempotency_cache) > 500:
        # Remove oldest half
        keys = list(_idempotency_cache.keys())
        for k in keys[:250]:
            del _idempotency_cache[k]

    tool = get_tool(record.tool_name)
    if not tool:
        # Gemini concatenation bug workaround: when the model concatenates multiple
        # tool names into one (e.g. "get_daily_briefingget_pending_approvals"),
        # try to extract the first valid tool name from the concatenated string.
        extracted_names = _try_extract_tool_names(record.tool_name)
        if extracted_names:
            logger.warning(
                f"[Execute] Tool name '{record.tool_name}' appears concatenated, "
                f"extracted {len(extracted_names)} tools: {extracted_names}"
            )
            record.tool_name = extracted_names[0]
            tool = get_tool(extracted_names[0])

    if not tool:
        record.status = "error"
        record.result = f"Error: Tool '{record.tool_name}' not found."
        return record

    # -1. Idempotency Check: prevent duplicate execution on retry
    idempotency_key = f"{record.tool_call_id}:{record.tool_name}"
    if idempotency_key and idempotency_key in _idempotency_cache:
        cached = _idempotency_cache[idempotency_key]
        record.status = cached["status"]
        record.result = cached["result"]
        record.duration_ms = cached.get("duration_ms", 0)
        logger.info(f"[Idempotency] Returning cached result for {record.tool_name} (call_id={record.tool_call_id})")
        return record

    # 0. Circuit Breaker Check
    if not tool_circuit_breaker.allow_request():
        record.status = "error"
        record.result = "Error: 工具服务断路器已打开，请稍后重试。"
        return record

    # 1. RBAC Check
    if tool.required_role not in ("all", "ai_assistant"):
        if tool.required_role == "boss" and config.user_role not in ("boss", "founder"):
            record.status = "blocked"
            record.result = f"⛔ 权限不足: 工具 [{record.tool_name}] 需要领导权限，当前角色为 [{config.user_role}]。"
            return record
        if tool.required_role == "manager" and config.user_role not in ("manager", "boss", "founder"):
            record.status = "blocked"
            record.result = f"⛔ 权限不足: 工具 [{record.tool_name}] 需要管理者权限，当前角色为 [{config.user_role}]。"
            return record

    # 2. Confirmation Gate (irreversible operations)
    confirmation_msg = tool.check_confirmation(record.tool_args, system_confirmed=config.system_confirmed)
    if confirmation_msg is not None:
        record.status = "blocked"
        record.result = confirmation_msg
        return record

    # 2b. Schema Validation — 强制验证 LLM 生成的参数符合工具声明的 JSON Schema
    try:
        await tool.validate(record.tool_args)
    except Exception as ve:
        record.status = "error"
        record.result = _format_validation_error(record.tool_name, ve, tool.parameters)
        logger.warning(f"[Execute] Tool {record.tool_name} schema validation failed: {ve}")
        return record

    # 3. Execute with configurable timeout and retry
    start_time = time.time()
    last_error = None
    timeout = config.tool_timeout if hasattr(config, "tool_timeout") else 30.0

    # Use longer timeout for known long-running tools
    if record.tool_name in LONG_RUNNING_TOOLS:
        timeout = max(timeout, 120.0)

    for attempt in range(3):
        try:
            result = await asyncio.wait_for(
                tool.run(
                    record.tool_args,
                    config.user_id,
                    config={
                        "api_key": config.api_key,
                        "base_url": config.base_url,
                        "model": config.model,
                        "org_id": config.org_id,
                    },
                ),
                timeout=timeout,
            )
            record.result = str(result)
            record.status = "success"
            record.duration_ms = int((time.time() - start_time) * 1000)
            record_tool_execution(record.tool_name, True, record.duration_ms)
            tool_circuit_breaker.record_success()
            # Cache successful result for idempotency
            if idempotency_key:
                _idempotency_cache[idempotency_key] = {
                    "status": record.status,
                    "result": record.result,
                    "duration_ms": record.duration_ms,
                }
            return record
        except TimeoutError:
            logger.warning(f"Tool {record.tool_name} timed out after {timeout}s (attempt {attempt+1})")
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            record.status = "error"
            record.result = f"Error: Tool '{record.tool_name}' timed out after {timeout}s."
            record.duration_ms = int((time.time() - start_time) * 1000)
            return record
        except Exception as e:
            last_error = e
            logger.error(f"Tool {record.tool_name} failed: {e}")
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue

    record.status = "error"
    record.result = f"Error: Tool '{record.tool_name}' failed after 3 attempts: {str(last_error)}"
    record.duration_ms = int((time.time() - start_time) * 1000)
    record_tool_execution(record.tool_name, False, record.duration_ms)
    tool_circuit_breaker.record_failure()
    return record


def _tool_call_fingerprint(tool_calls: list) -> str:
    """Generate a hash fingerprint for a batch of tool calls (name + args)."""
    if not tool_calls:
        return ""
    parts = []
    for tc in sorted(tool_calls, key=lambda t: t.tool_name):
        args_str = _json.dumps(tc.tool_args, sort_keys=True, ensure_ascii=False) if tc.tool_args else ""
        parts.append(f"{tc.tool_name}:{args_str}")
    combined = "|".join(parts)
    return hashlib.md5(combined.encode()).hexdigest()


async def execute_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """
    Execute all pending tool calls in parallel.
    """
    agent_config: AgentConfig = state["config"]
    pending = state.get("pending_tool_calls", [])

    if not pending:
        return {
            "current_phase": AgentPhase.REFLECTING,
            "pending_tool_calls": [],
        }

    # P1-7: Intercept ask_user pseudo-tool — do not execute, emit as blocked
    ask_user_calls = [t for t in pending if t.tool_name == "ask_user"]
    if ask_user_calls:
        # Return ask_user calls as "blocked" with status="ask_user"
        # so the stream layer can emit the SSE event
        non_ask_pending = [t for t in pending if t.tool_name != "ask_user"]
        ask_records = []
        for tc in ask_user_calls:
            tc.status = "ask_user"
            tc.result = tc.tool_args.get("question", "请提供更多信息")
            ask_records.append(tc)

        return {
            "current_phase": AgentPhase.RESPONDING,
            "pending_tool_calls": non_ask_pending,
            "completed_tool_calls": ask_records,
            "final_response": "",  # Will be replaced by ask_user SSE event
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.EXECUTING.value,
                    content=f"向用户提问: {ask_records[0].result}",
                )
            ],
        }

    tool_names = ", ".join(t.tool_name for t in pending)
    thinking_step = ThinkingStep(
        phase=AgentPhase.EXECUTING.value,
        content=f"正在并行执行 {len(pending)} 个工具: {tool_names}",
        tool_name=tool_names,
    )

    # Execute all tools in parallel with overall timeout
    gather_timeout = agent_config.gather_timeout if hasattr(agent_config, "gather_timeout") else 120.0

    # P1 Plugin: PRE_TOOL hook
    try:
        tool_names_list = [t.tool_name for t in pending]
        await plugin_system_service.run_hooks(
            ExtensionPoint.PRE_TOOL,
            {"tools": tool_names_list, "pending_count": len(pending)},
        )
    except Exception as e:
        logger.debug(f"[ExecuteNode] PRE_TOOL hook error: {e}")

    # P1 Fix: Share a single idempotency cache across all parallel tool executions
    shared_idempotency_cache: dict = {}

    try:
        tasks = [_execute_single_tool(record, agent_config, shared_idempotency_cache) for record in pending]
        completed: list[ToolCallRecord] = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=False),
            timeout=gather_timeout,
        )
    except TimeoutError:
        logger.error(f"[ExecuteNode] Tool gather timed out after {gather_timeout}s")
        return {
            "error": f"工具执行整体超时 ({gather_timeout}秒)",
            "current_phase": AgentPhase.ERROR,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.EXECUTING.value,
                    content=f"⚠️ 工具执行整体超时 ({gather_timeout}秒)",
                )
            ],
        }
    except Exception as e:
        logger.error(f"[ExecuteNode] Tool execution fatal error: {e}")
        return {
            "error": f"工具执行异常: {str(e)}",
            "current_phase": AgentPhase.ERROR,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.EXECUTING.value,
                    content=f"⚠️ 工具执行崩溃: {str(e)}",
                )
            ],
        }

    # Build ToolMessage objects for the message history
    tool_messages = []
    result_steps = []
    for record in completed:
        tool_messages.append(
            ToolMessage(
                content=record.result or "",
                name=record.tool_name,
                tool_call_id=record.tool_call_id,
            )
        )
        if record.status == "error":
            logger.warning(f"[ExecuteNode] Tool {record.tool_name} failed: {record.result}")
            # Non-fatal errors are passed to LLM, but we log them

        result_steps.append(
            ThinkingStep(
                phase=AgentPhase.EXECUTING.value,
                content=f"工具 [{record.tool_name}] 执行完毕 ({record.status})",
                tool_name=record.tool_name,
                tool_result=record.result[:500] if record.result else None,
                duration_ms=record.duration_ms,
            )
        )

    # Merge with previously completed tools
    all_completed = list(state.get("completed_tool_calls", [])) + completed

    # Langfuse: log tool executions
    _configurable = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    trace_logger = _configurable.get("trace_logger")
    if trace_logger:
        for record in completed:
            with contextlib.suppress(Exception):
                trace_logger.log_tool_execution(
                    record.tool_name, record.status, record.result[:500] if record.result else ""
                )

    # P1 Plugin: POST_TOOL hook
    try:
        await plugin_system_service.run_hooks(
            ExtensionPoint.POST_TOOL,
            {
                "completed_tools": [
                    {"name": r.tool_name, "status": r.status, "duration_ms": r.duration_ms} for r in completed
                ]
            },
        )
    except Exception as e:
        logger.debug(f"[ExecuteNode] POST_TOOL hook error: {e}")

    return {
        "messages": tool_messages,
        "current_phase": AgentPhase.PLANNING,
        "pending_tool_calls": [],
        "completed_tool_calls": all_completed,
        "iteration": state.get("iteration", 0) + 1,
        "thinking_steps": [thinking_step] + result_steps,
        # P2: Record tool call fingerprint for loop detection
        "_tool_call_history": [_tool_call_fingerprint(completed)],
    }
