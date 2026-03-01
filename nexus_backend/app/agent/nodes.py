"""
Graph Nodes — each function is a node in the LangGraph state machine.

Node contract:
  - Input:  AgentState (full state dict)
  - Output: dict with ONLY the keys to update (LangGraph merges automatically)

Nodes:
  plan_node     → Calls LLM to produce a plan (or direct answer for simple queries)
  execute_node  → Runs tool calls returned by the LLM
  reflect_node  → Validates output, checks hallucination, decides next step
  respond_node  → Formats final response and emits thinking chain
"""

import asyncio
import contextlib
import logging
import time

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.agent.state import (
    AgentConfig,
    AgentPhase,
    AgentState,
    QueryComplexity,
    ThinkingStep,
    ToolCallRecord,
)
from app.core.ai_metrics import (
    record_hallucination,
    record_llm_latency,
    record_tool_execution,
)
from app.services.content_moderation import sanitize_output, scan_content
from app.services.error_recovery_service import llm_circuit_breaker, tool_circuit_breaker
from app.services.plugin_system_service import ExtensionPoint, plugin_system_service
from app.tools import get_all_tools_schema, get_tool

logger = logging.getLogger(__name__)

# Long-running tools that need extended timeout (120s instead of default 30s)
LONG_RUNNING_TOOLS: set[str] = {
    "generate_product_manual",
    "generate_faq_response",
    "generate_training_material",
    "generate_weekly_report",
    "generate_competitor_analysis",
    "generate_tender_analysis",
    "generate_contract_summary",
    "batch_analyze_documents",
    "query_knowledge_base",
    "strategy_simulation",
    "get_company_stats",
}


# ─── Pydantic models for structured LLM output in reflect_node ───────────────


class GroundednessCheck(BaseModel):
    """RAG groundedness evaluation result."""

    is_grounded: bool = Field(description="Whether the response is grounded in reference knowledge")
    reason: str = Field(default="", description="Reason for the evaluation")
    score: float = Field(default=0.5, ge=0.0, le=1.0, description="Groundedness score 0-1")


class HallucinationCheck(BaseModel):
    """LLM-based hallucination detection result."""

    is_hallucination: bool = Field(description="Whether the response contains fabricated information")
    reason: str = Field(default="", description="Reason for the evaluation")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score 0-1")


class CriticResult(BaseModel):
    """P1-5: Independent critic evaluation of agent response quality."""

    completeness: float = Field(default=0.5, ge=0.0, le=1.0, description="回答是否完整覆盖用户问题")
    relevance: float = Field(default=0.5, ge=0.0, le=1.0, description="回答与用户意图的相关性")
    accuracy: float = Field(default=0.5, ge=0.0, le=1.0, description="信息准确性（基于工具结果）")
    passed: bool = Field(default=True, description="是否通过评审")
    improvement_suggestion: str = Field(default="", description="改进建议（未通过时提供）")


logger = logging.getLogger(__name__)


# P1 Fix: Cache tool schemas to avoid rebuilding on every request
_tool_schemas_cache = None
_tool_schemas_count = None

# Role hierarchy for tool access filtering
_ROLE_HIERARCHY = {
    "guest": 0,
    "employee": 1,
    "manager": 2,
    "boss": 3,
    "founder": 4,
}


def _get_tool_schemas(user_role: str | None = None):
    """Get tool schemas with caching. Optionally filter by user role to reduce token cost."""
    global _tool_schemas_cache, _tool_schemas_count
    schemas = get_all_tools_schema()
    if _tool_schemas_cache is None or len(schemas) != _tool_schemas_count:
        _tool_schemas_cache = schemas
        _tool_schemas_count = len(schemas)

    if not user_role:
        return _tool_schemas_cache

    # Filter schemas by user role — exclude tools the user cannot execute
    user_level = _ROLE_HIERARCHY.get(user_role, 1)
    filtered = []
    for schema in _tool_schemas_cache:
        tool_name = schema.get("function", {}).get("name", "")
        tool = get_tool(tool_name)
        if not tool:
            continue
        req_role = getattr(tool, "required_role", "all")
        if req_role in ("all", "ai_assistant"):
            filtered.append(schema)
        else:
            req_level = _ROLE_HIERARCHY.get(req_role, 1)
            if user_level >= req_level:
                filtered.append(schema)
    return filtered


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _get_llm(
    config: AgentConfig, model: str | None = None, streaming: bool = False, resolved_config: dict | None = None
):
    """Get a LangChain ChatOpenAI instance with the provided config.

    If resolved_config is provided (from LLM gateway), use it.
    Otherwise fall back to AgentConfig settings.

    #25: Injects trace_id as default header for full-chain propagation.
    """
    from app.core.trace_context import get_request_id, get_trace_id

    # 构建追踪头
    default_headers = {}
    trace_id = get_trace_id()
    request_id = get_request_id()
    if trace_id:
        default_headers["X-Trace-ID"] = trace_id
    if request_id:
        default_headers["X-Request-ID"] = request_id

    if resolved_config:
        return ChatOpenAI(
            model=resolved_config.get("model", model or config.model),
            api_key=resolved_config.get("api_key", config.api_key),
            base_url=resolved_config.get("base_url", config.base_url),
            temperature=resolved_config.get("temperature", config.temperature),
            streaming=streaming,
            timeout=resolved_config.get("timeout", 60.0),
            default_headers=default_headers or None,
        )
    return ChatOpenAI(
        model=model or config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        streaming=streaming,
        timeout=60.0,
        default_headers=default_headers or None,
    )


def _messages_to_lc_format(messages) -> list[BaseMessage]:
    """Ensure messages are in LangChain format."""
    result = []
    for msg in messages:
        if isinstance(msg, BaseMessage):
            result.append(msg)
        elif isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                result.append(SystemMessage(content=content))
            elif role == "user":
                result.append(HumanMessage(content=content))
            elif role == "assistant":
                result.append(AIMessage(content=content, additional_kwargs=msg.get("additional_kwargs", {})))
            elif role == "tool":
                result.append(
                    ToolMessage(content=content, tool_call_id=msg.get("tool_call_id", ""), name=msg.get("name", ""))
                )
    return result


def _format_validation_error(tool_name: str, error: Exception, schema: dict | None = None) -> str:
    """
    Format a schema validation error with field-level guidance for the LLM.

    Instead of raw jsonschema error text, produces a structured message
    that helps the LLM understand exactly which field to fix.
    """
    try:
        import jsonschema

        if isinstance(error, jsonschema.ValidationError):
            field_path = " → ".join(str(p) for p in error.absolute_path) if error.absolute_path else "(root)"
            lines = [f"参数校验失败 [{tool_name}]:"]
            lines.append(f"  错误字段: {field_path}")
            lines.append(f"  问题: {error.message}")

            # Add expected type/enum info
            if error.schema:
                if "type" in error.schema:
                    lines.append(f"  期望类型: {error.schema['type']}")
                if "enum" in error.schema:
                    lines.append(f"  允许值: {error.schema['enum']}")
                if "description" in error.schema:
                    lines.append(f"  字段说明: {error.schema['description']}")

            # Show required fields if it's a missing-property error
            if error.validator == "required" and schema:
                required = schema.get("required", [])
                props = schema.get("properties", {})
                if required:
                    field_hints = []
                    for r in required:
                        desc = props.get(r, {}).get("description", "")
                        ftype = props.get(r, {}).get("type", "")
                        field_hints.append(f"    - {r} ({ftype}): {desc}" if desc else f"    - {r} ({ftype})")
                    lines.append("  必填字段:")
                    lines.extend(field_hints)

            return "\n".join(lines)
    except Exception:
        pass

    # Fallback for non-jsonschema errors
    return f"参数校验失败 [{tool_name}]: {error}"


def _try_extract_tool_names(concatenated_name: str) -> list[str]:
    """
    Gemini concatenation bug workaround: Extract ALL valid tool names
    from a concatenated string like 'get_daily_briefingget_pending_approvals'.

    Returns a list of matched tool names (may be empty).
    """
    all_schemas = get_all_tools_schema()
    # Sort by length descending to match longest tool name first
    known_names = sorted(
        [s["function"]["name"] for s in all_schemas],
        key=len,
        reverse=True,
    )

    found: list[str] = []
    remaining = concatenated_name
    while remaining:
        matched = False
        for name in known_names:
            if remaining.startswith(name):
                found.append(name)
                remaining = remaining[len(name) :]
                matched = True
                break
        if not matched:
            break  # Unrecognizable remainder, stop parsing

    return found if len(found) > 1 else []  # Only useful when multiple names found


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


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: plan_node
# ═══════════════════════════════════════════════════════════════════════════════


async def plan_node(state: AgentState, config: RunnableConfig | None = None) -> dict:
    """
    Call the LLM with the current messages + tool schemas.
    """
    agent_config: AgentConfig = state["config"]
    model = state.get("selected_model", agent_config.model)
    messages = state.get("messages", [])
    iteration = state.get("iteration", 0)
    rag_context = state.get("rag_context", "")

    # Resolve model via LLM gateway (P2-9: complexity-aware routing)
    resolved = None
    try:
        from app.services.llm_helpers import resolve_model_config

        org_id = agent_config.org_id or "default"
        scene_code = state.get("scene_code", "")
        agent_code = state.get("agent_code", "")
        complexity = state.get("complexity", QueryComplexity.MODERATE)
        resolved = await resolve_model_config(org_id, scene_code, agent_code, complexity_tier=complexity.model_tier)
    except Exception:
        logger.debug("LLM gateway model config unavailable in plan_node, using default")

    # Convert to LC format
    lc_msgs = _messages_to_lc_format(messages)

    # ── Dynamic System Prompt Injection ──
    # Inject user_role and available_tools into the system prompt
    if iteration == 0:
        extra_lines = []
        user_role = agent_config.user_role
        if user_role:
            extra_lines.append(f"当前用户角色: {user_role}")

        tool_schemas = _get_tool_schemas(agent_config.user_role)
        if tool_schemas:
            tool_names = ", ".join(t["function"]["name"] for t in tool_schemas)
            extra_lines.append(f"可用工具: {tool_names}")

        if extra_lines:
            injection = "\n".join(extra_lines)
            injected = False
            for _i, m in enumerate(lc_msgs):
                if isinstance(m, SystemMessage):
                    m.content += f"\n\n{injection}"
                    injected = True
                    break
            if not injected:
                lc_msgs.insert(0, SystemMessage(content=injection))

    # P0-3: On re-planning iterations, inject reflection guidance into system prompt
    if iteration > 0:
        reflection_guidance = state.get("reflection_guidance", "")
        if reflection_guidance:
            guidance_injection = (
                f"\n\n[重要：反思修正指令]\n{reflection_guidance}\n"
                f"请根据以上指令调整你的回复策略。当前是第{iteration + 1}轮规划。"
            )
            injected_guidance = False
            for m in lc_msgs:
                if isinstance(m, SystemMessage):
                    m.content += guidance_injection
                    injected_guidance = True
                    break
            if not injected_guidance:
                lc_msgs.insert(0, SystemMessage(content=guidance_injection))

    # ── RAG Injection ──
    # If we have retrieved context, prepend it to the history or inject into system prompt
    if rag_context and iteration == 0:
        rag_disclaimer = (
            "【重要：文档来源区分】\n"
            "以下检索结果可能来自不同类型的文档，请注意区分：\n"
            "- [招标文件]: 客户/甲方发布的采购需求，其中提到的产品规格是客户要求，不代表我方产品\n"
            "- [投标文件]: 我方编写的投标响应文档\n"
            "- [产品资料]: 我方的产品说明、规格书等，代表我方实际能力\n"
            "- 无标签的内容请根据上下文自行判断来源\n"
            "回答时务必区分「客户要求」和「我方能力」，切勿将招标文件中的需求当作我方产品参数。\n"
        )
        rag_block = f"\n\n{rag_disclaimer}\n[检索到的参考知识]:\n{rag_context}"
        found_sys = False
        for _i, m in enumerate(lc_msgs):
            if isinstance(m, SystemMessage):
                m.content += rag_block
                found_sys = True
                break
        if not found_sys:
            lc_msgs.insert(0, SystemMessage(content=f"你可以参考以下背景知识来回答问题:{rag_block}"))

    # Decide whether to include tools
    complexity = state.get("complexity", QueryComplexity.MODERATE)
    include_tools = complexity != QueryComplexity.SIMPLE

    # ── Task 1 & 2: LangChain Planning + Streaming ──
    # Use ChatOpenAI with streaming and bind_tools
    llm = _get_llm(agent_config, model=model, streaming=True, resolved_config=resolved)
    if include_tools:
        llm = llm.bind_tools(_get_tool_schemas(agent_config.user_role), parallel_tool_calls=True)

    thinking_step = ThinkingStep(
        phase=AgentPhase.PLANNING.value,
        content=f"正在分析意图并规划执行路径... (轮次 {iteration + 1})",
    )

    # P1 Plugin: PRE_CHAT hook
    try:
        hook_ctx = await plugin_system_service.run_hooks(
            ExtensionPoint.PRE_CHAT,
            {"messages": lc_msgs, "model": model, "config": agent_config},
        )
        if "messages" in hook_ctx and isinstance(hook_ctx["messages"], list):
            lc_msgs = hook_ctx["messages"]
    except Exception as e:
        logger.debug(f"[PlanNode] PRE_CHAT hook error: {e}")

    # Call LLM via standard invoke
    try:
        # Circuit breaker check for LLM service
        if not llm_circuit_breaker.allow_request():
            return {
                "error": "LLM 服务断路器已打开，请稍后重试。",
                "current_phase": AgentPhase.ERROR,
                "thinking_steps": [
                    ThinkingStep(
                        phase=AgentPhase.PLANNING.value,
                        content="⚠️ LLM 服务暂时不可用（断路器保护），请稍后再试",
                    )
                ],
            }
        # We use astream to capture tokens if needed, but for the node return we need the full message
        # In a real heavy-streaming app, we'd use a callback handler passed via config
        _llm_start = time.time()
        ai_msg = await llm.ainvoke(lc_msgs)
        record_llm_latency(model=model or agent_config.model, duration_ms=(time.time() - _llm_start) * 1000)
        llm_circuit_breaker.record_success()
    except Exception as e:
        llm_circuit_breaker.record_failure()
        logger.error(f"[PlanNode] LLM call failed: {e}")
        return {
            "error": f"LLM 规划失败: {str(e)}",
            "current_phase": AgentPhase.ERROR,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.PLANNING.value,
                    content=f"⚠️ LLM 调用异常: {str(e)}",
                )
            ],
        }

    # Track usage (LangChain usually provides this in additional_kwargs or response_metadata)
    usage = ai_msg.response_metadata.get("token_usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    # Langfuse: log LLM generation
    _configurable = (config or {}).get("configurable", {}) if isinstance(config, dict) else {}
    trace_logger = _configurable.get("trace_logger")
    if trace_logger:
        with contextlib.suppress(Exception):
            trace_logger.log_generation(
                model=model or agent_config.model,
                input_messages=[{"role": "user", "content": str(lc_msgs[-1].content)[:500]}] if lc_msgs else [],
                output=str(ai_msg.content or "")[:1000],
                usage={"prompt_tokens": input_tokens, "completion_tokens": output_tokens},
            )

    # P1 Plugin: POST_CHAT hook
    try:
        await plugin_system_service.run_hooks(
            ExtensionPoint.POST_CHAT,
            {"ai_message": ai_msg, "input_tokens": input_tokens, "output_tokens": output_tokens},
        )
    except Exception as e:
        logger.debug(f"[PlanNode] POST_CHAT hook error: {e}")

    tool_calls_raw = ai_msg.tool_calls
    content = ai_msg.content or ""

    # Build pending tool call records
    pending_tools: list[ToolCallRecord] = []
    if tool_calls_raw:
        for tc in tool_calls_raw:
            tc_name = tc.get("name", "unknown")
            tc_args = tc.get("args", {})
            tc_id = tc.get("id", "")

            # Gemini concatenation bug: split concatenated tool names into separate records
            if not get_tool(tc_name):
                extracted = _try_extract_tool_names(tc_name)
                if extracted:
                    logger.warning(
                        f"[PlanNode] Splitting concatenated tool name '{tc_name}' "
                        f"into {len(extracted)} tools: {extracted}"
                    )
                    for i, ename in enumerate(extracted):
                        pending_tools.append(
                            ToolCallRecord(
                                tool_name=ename,
                                tool_args=tc_args if i == 0 else {},
                                tool_call_id=f"{tc_id}_split{i}" if tc_id else "",
                            )
                        )
                    continue

            pending_tools.append(
                ToolCallRecord(
                    tool_name=tc_name,
                    tool_args=tc_args,
                    tool_call_id=tc_id,
                )
            )

    # Construct the AIMessage to append to history
    # LangChain's ai_msg already is a BaseMessage
    result = {
        "messages": [ai_msg],
        "current_phase": AgentPhase.EXECUTING if pending_tools else AgentPhase.REFLECTING,
        "plan": content or "(执行工具调用)",
        "requires_tools": bool(pending_tools),
        "pending_tool_calls": pending_tools,
        "thinking_steps": [thinking_step],
        "total_input_tokens": state.get("total_input_tokens", 0) + input_tokens,
        "total_output_tokens": state.get("total_output_tokens", 0) + output_tokens,
    }

    if pending_tools:
        tool_names = ", ".join(t.tool_name for t in pending_tools)
        exec_step = ThinkingStep(
            phase=AgentPhase.PLANNING.value,
            content=f"计划调用工具: {tool_names}",
        )
        result["thinking_steps"] = [thinking_step, exec_step]
        # Langfuse: log tool plans
        if trace_logger:
            for t in pending_tools:
                with contextlib.suppress(Exception):
                    trace_logger.log_tool_plan(t.tool_name, t.tool_args)

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: execute_node
# ═══════════════════════════════════════════════════════════════════════════════


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
    gather_timeout = agent_config.gather_timeout if hasattr(agent_config, "gather_timeout") else 60.0

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
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: reflect_node
# ═══════════════════════════════════════════════════════════════════════════════


async def reflect_node(state: AgentState) -> dict:
    """
    P1 Security Enhancement: Self-reflection with advanced hallucination detection.

    Detection layers:
    1. Empty response check
    2. Keyword-based hallucination detection
    3. Tool result grounding verification
    4. LLM-based fact checking
    5. Numerical data validation
    """
    config: AgentConfig = state["config"]
    messages = state.get("messages", [])
    iteration = state.get("iteration", 0)
    complexity = state.get("complexity", QueryComplexity.MODERATE)
    completed_tools = state.get("completed_tool_calls", [])

    # Resolve model via LLM gateway (P2-9: complexity-aware routing)
    resolved = None
    try:
        from app.services.llm_helpers import resolve_model_config

        org_id = config.org_id or "default"
        scene_code = state.get("scene_code", "")
        agent_code = state.get("agent_code", "")
        resolved = await resolve_model_config(org_id, scene_code, agent_code, complexity_tier=complexity.model_tier)
    except Exception:
        logger.debug("LLM gateway model config unavailable in reflect_node, using default")

    # Extract the last AI message
    last_ai_content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai_content = msg.content or ""
            break

    thinking_step = ThinkingStep(
        phase=AgentPhase.REFLECTING.value,
        content="正在评估回复完整度与事实准确性...",
    )

    # ── Layer 1: Empty response check ──
    if (not last_ai_content.strip() or len(last_ai_content.strip()) < 5) and completed_tools:
        return {
            "reflection": "回复内容为空，需要整合工具结果重新回答。",
            "needs_replanning": iteration < config.max_iterations,
            "current_phase": AgentPhase.PLANNING if iteration < config.max_iterations else AgentPhase.RESPONDING,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.REFLECTING.value,
                    content="检测到未正常生成回复，触发重试路径",
                )
            ],
        }

    # ── Layer 2: Keyword-based hallucination detection ──
    is_hallucination = False
    hallucination_reason = ""

    if complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL) and not completed_tools:
        hallucination_keywords = ["查询到", "系统显示", "数据显示", "结果是", "找到", "检索到", "发现"]
        if any(kw in last_ai_content for kw in hallucination_keywords):
            # Additional check: does it contain specific numbers/data?
            import re

            number_pattern = r"\d+(?:\.\d+)?(?:万|千|百|元|个|%|位)?"
            if re.search(number_pattern, last_ai_content):
                is_hallucination = True
                hallucination_reason = "复杂查询未调用工具却产出了具体数据"

    # ── Layer 3: Tool result grounding verification ──
    # P1 Fix: Verify that numerical data in response matches tool results
    if completed_tools and last_ai_content:
        grounding_issues = await _verify_tool_grounding(last_ai_content, completed_tools)
        if grounding_issues:
            is_hallucination = True
            hallucination_reason = f"回复数据与工具返回不一致: {grounding_issues}"

    # ── Layer 4: RAG-based groundedness check ──
    # IMPORTANT: Skip this check when tools were involved (even if some failed).
    # If the query triggered tool calls, it's a tool-oriented query — RAG context
    # is NOT the right source of truth for validating the response.
    grounded_warning = None
    rag_context = state.get("rag_context", "")

    # Safely get tool status, handling both dict and dataclass
    def _is_success(t):
        if isinstance(t, dict):
            return t.get("status") == "success"
        return getattr(t, "status", None) == "success"

    has_successful_tools = any(_is_success(t) for t in completed_tools)
    has_any_tool_attempts = len(completed_tools) > 0

    # Broader pattern matching for failed/empty RAG results
    _rag_empty_patterns = ("搜索失败", "缺少", "未找到", "没有找到", "无相关", "暂无", "不存在")
    rag_search_failed = (
        not rag_context or any(p in rag_context for p in _rag_empty_patterns) or len(rag_context.strip()) < 20
    )

    # Skip Layer 4 when: tools were attempted (query is tool-oriented), OR RAG returned nothing useful
    if rag_context and last_ai_content and not is_hallucination and not has_any_tool_attempts and not rag_search_failed:
        prompt = f"""[事实核查任务]
请比较【参考知识】与【AI回复】，判断回复是否完全基于背景知识，是否存在编造或矛盾。
请严格按照以下 JSON 格式返回，不要输出其他内容:
{{"is_grounded": true, "reason": "", "score": 0.8}}

参考知识:
{rag_context[:2000]}

AI回复:
{last_ai_content[:1000]}
"""
        try:
            import json as _json
            import re as _re

            llm = _get_llm(config, model=config.mini_model, resolved_config=resolved)
            raw_resp = await llm.ainvoke([HumanMessage(content=prompt)])
            raw_text = raw_resp.content.strip()
            json_match = _re.search(r"\{.*\}", raw_text, _re.DOTALL)
            if json_match:
                parsed = _json.loads(json_match.group())
                eval_result = GroundednessCheck(**parsed)
                if not eval_result.is_grounded:
                    is_hallucination = True
                    grounded_warning = eval_result.reason or "事实偏差"
                    logger.warning(f"[Reflect] Ungrounded response: {grounded_warning}")
        except Exception as e:
            logger.debug(f"[ReflectNode] Groundedness check failed: {e}")
    elif has_any_tool_attempts:
        logger.info(
            f"[Reflect] Layer 4 skipped: query used tools "
            f"(success={has_successful_tools}, total={len(completed_tools)}), "
            f"RAG groundedness check not applicable"
        )
    elif rag_search_failed:
        logger.info("[Reflect] Layer 4 skipped: RAG context empty or search failed")

    # ── Layer 5: LLM-based reflection ──
    # Skip LLM reflection if tools were involved — tool results are ground truth.
    if config.reflect_use_llm and last_ai_content and not is_hallucination and not has_any_tool_attempts:
        messages_text = "\n".join([f"{m.type}: {m.content[:200]}" for m in messages[-3:]])
        prompt = f"""请评估 AI 的最新回复是否包含编造的信息（幻觉）。

检查要点:
1. 是否声称有数据但实际未调用工具?
2. 是否引用了不存在的文档或来源?
3. 数值是否合理且有依据?

请严格按照以下 JSON 格式返回，不要输出其他内容:
{{"is_hallucination": false, "reason": "", "confidence": 0.8}}

上下文摘要:
{messages_text}

AI 回复:
{last_ai_content}
"""
        try:
            import json as _json
            import re as _re

            llm = _get_llm(config, model=config.mini_model, resolved_config=resolved)
            raw_resp = await llm.ainvoke([HumanMessage(content=prompt)])
            raw_text = raw_resp.content.strip()
            json_match = _re.search(r"\{.*\}", raw_text, _re.DOTALL)
            if json_match:
                parsed = _json.loads(json_match.group())
                eval_result = HallucinationCheck(**parsed)
                if eval_result.is_hallucination:
                    is_hallucination = True
                    hallucination_reason = eval_result.reason or "存在事实偏差"
        except Exception as e:
            logger.debug(f"[ReflectNode] LLM eval failed: {e}")

    if grounded_warning:
        hallucination_reason = grounded_warning

    # ── Content Safety ──
    is_safe, violations = scan_content(last_ai_content)
    if not is_safe:
        last_ai_content = sanitize_output(last_ai_content)

    # Calculate confidence
    confidence = 0.85
    if is_hallucination:
        confidence = 0.3
    if completed_tools:
        # P1 Fix: Don't override hallucination-reduced confidence
        confidence = min(confidence, 0.95) if is_hallucination else 0.95
    if state.get("needs_replanning"):
        confidence = min(confidence, 0.6)

    needs_replanning = is_hallucination and iteration < config.max_iterations

    # P1 Fix: Record hallucination metrics
    if is_hallucination:
        record_hallucination("reflect_node")

    if needs_replanning:
        # Provide escalating feedback: deeper iterations get more specific UI hints
        if iteration >= 3:
            thinking_content = f"🔄 深度验证第{iteration}轮: {hallucination_reason}，即将结束验证..."
        elif iteration >= 2:
            thinking_content = f"🔄 深度验证中 (第{iteration}轮): {hallucination_reason}，正在修正..."
        else:
            thinking_content = f"⚠️ 检测到潜在事实错误: {hallucination_reason}，正在修正..."

        # P0-3: Build structured correction guidance for plan_node
        guidance_parts = [f"## 反思修正指令 (第{iteration + 1}轮)"]
        guidance_parts.append(f"**问题类型**: {hallucination_reason}")

        if "未调用工具却产出了具体数据" in hallucination_reason:
            guidance_parts.append("**修正策略**: 必须调用相关工具获取真实数据，禁止凭空编造数值")
            guidance_parts.append("**建议**: 根据用户查询意图选择数据查询类工具")
        elif "工具返回不一致" in hallucination_reason:
            guidance_parts.append("**修正策略**: 严格引用工具返回的原始数据，不做未经授权的数值修改")
        elif "事实偏差" in hallucination_reason or "Ungrounded" in str(hallucination_reason):
            guidance_parts.append("**修正策略**: 回复必须完全基于检索到的参考知识，移除无依据的陈述")
        else:
            guidance_parts.append("**修正策略**: 重新审视回复，确保所有信息有据可查")

        if completed_tools:
            tool_summary = []
            for t in completed_tools[-3:]:
                t_name = t.tool_name if hasattr(t, "tool_name") else t.get("tool_name", "")
                t_result = (t.result if hasattr(t, "result") else t.get("result", ""))[:200]
                tool_summary.append(f"  - {t_name}: {t_result}")
            guidance_parts.append("**可用工具结果**:\n" + "\n".join(tool_summary))

        reflection_guidance = "\n".join(guidance_parts)

        return {
            "messages": [HumanMessage(content=f"[自我指引] {reflection_guidance}")],
            "reflection": f"触发幻觉修正: {hallucination_reason}",
            "reflection_guidance": reflection_guidance,
            "is_hallucination": True,
            "needs_replanning": True,
            "confidence_score": confidence,
            "current_phase": AgentPhase.PLANNING,
            "iteration": iteration + 1,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.REFLECTING.value,
                    content=thinking_content,
                )
            ],
        }

    return {
        "reflection": "通过质量校验",
        "is_hallucination": is_hallucination,
        "needs_replanning": False,
        "confidence_score": confidence,
        "final_response": last_ai_content,
        "current_phase": AgentPhase.RESPONDING,
        "thinking_steps": [thinking_step],
    }


async def _verify_tool_grounding(ai_response: str, tool_results: list) -> str | None:
    """
    P1 Fix: Verify that numerical data in AI response matches tool results.
    Returns a description of grounding issues, or None if all grounded.

    Uses relaxed matching to avoid false positives:
    - Skips small numbers (< 10) which are commonly used in formatting
    - Uses ±10% relative tolerance for number comparison
    - Requires at least 3 ungrounded numbers to trigger (avoids noise from dates, IDs, etc.)
    - Aggressively strips date/time strings before extracting numbers.
    """
    import re

    issues = []

    # Strip out common date/time formats to avoid false positives (e.g. 2024年12月16日, 2024-12-16)
    def _strip_dates(text: str) -> str:
        text = re.sub(r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号]?", "", text)
        text = re.sub(r"\d{4}\s*-\s*\d{1,2}\s*-\s*\d{1,2}", "", text)
        text = re.sub(r"\d{1,2}\s*:\s*\d{1,2}(?:\s*:\s*\d{1,2})?", "", text)
        # Also strip ISO timestamps and UUIDs which contain many numbers
        text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", "", text)
        text = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "", text)
        return text

    clean_ai_response = _strip_dates(ai_response)

    # Extract all numbers from AI response
    ai_numbers = re.findall(r"\d+(?:\.\d+)?", clean_ai_response)

    # Get all numbers from tool results (also strip dates to avoid false positives)
    tool_numbers = []
    for tool in tool_results:
        # P1 fix: Handle both ToolCallRecord objects and dicts
        result_text = tool.get("result", "") if isinstance(tool, dict) else getattr(tool, "result", "")
        if result_text:
            clean_result = _strip_dates(str(result_text))
            tool_numbers.extend(re.findall(r"\d+(?:\.\d+)?", clean_result))

    if not tool_numbers:
        return None  # No tool numbers to compare against

    # Check if AI mentions numbers not in tool results
    for num in ai_numbers:
        # Skip small numbers — commonly used in formatting, list indices, etc.
        if float(num) < 10:
            continue
        # Use ±10% relative tolerance for comparison
        found = any(abs(float(num) - float(tn)) / max(float(tn), 1.0) < 0.10 for tn in tool_numbers)
        if not found:
            issues.append(f"数值 {num} 未见工具返回")

    # Require at least 3 ungrounded numbers to flag (avoids noise from IDs, etc.)
    if len(issues) >= 3:
        return "; ".join(issues[:3])

    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: respond_node
# ═══════════════════════════════════════════════════════════════════════════════


async def respond_node(state: AgentState) -> dict:
    """
    Finalize output and format for UI.
    Includes role-based sensitive field masking for security.
    """
    final_response = state.get("final_response", "")

    if not final_response:
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content
                break

    # Final moderation filter
    final_response = sanitize_output(final_response)

    # P1 Security: Role-based sensitive field masking
    # Prevents lower-privilege users from seeing sensitive data
    # that may have been retrieved by RAG or tool calls
    config: AgentConfig = state["config"]
    final_response = _mask_sensitive_fields(final_response, config.user_role)

    return {
        "final_response": final_response or "抱歉，系统处理出现异常，请重试。",
        "current_phase": AgentPhase.DONE,
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.RESPONDING.value,
                content=f"思考路径完成，正在输出回复 (置信度: {state.get('confidence_score', 0.8):.0%})",
            )
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: critic_node (P1-5)
# ═══════════════════════════════════════════════════════════════════════════════


async def critic_node(state: AgentState) -> dict:
    """
    P1-5: Independent quality evaluation before final response.

    Only activates for COMPLEX/CRITICAL queries. Uses mini_model with a strict
    evaluation prompt to assess completeness, relevance, and accuracy.
    If the critic fails the response, it sets reflection_guidance and
    needs_replanning=True to send it back to plan_node for one correction pass.
    """
    config: AgentConfig = state["config"]
    complexity = state.get("complexity", QueryComplexity.MODERATE)

    # Skip critic for simple/moderate queries — not worth the extra LLM call
    if complexity in (QueryComplexity.SIMPLE, QueryComplexity.MODERATE):
        return {
            "critic_passed": True,
            "critic_feedback": "",
            "current_phase": AgentPhase.RESPONDING,
        }

    final_response = state.get("final_response", "")
    if not final_response:
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content
                break

    if not final_response:
        return {
            "critic_passed": True,
            "critic_feedback": "无回复内容，跳过评审",
            "current_phase": AgentPhase.RESPONDING,
        }

    # Gather context for critic evaluation
    intent_summary = state.get("intent_summary", "")
    tool_results_summary = []
    for tc in state.get("completed_tool_calls", []):
        result_preview = (getattr(tc, "result", "") or "")[:200]
        tool_results_summary.append(f"- {tc.tool_name}: {result_preview}")
    tool_context = "\n".join(tool_results_summary[:5]) if tool_results_summary else "无工具调用"

    critic_prompt = f"""你是一个严格的质量评审员。请评估以下AI回复的质量。

## 用户意图
{intent_summary or '未知'}

## 工具调用结果摘要
{tool_context}

## AI回复
{final_response[:2000]}

## 评估标准
1. completeness (0-1): 回答是否完整覆盖了用户的所有问题点？
2. relevance (0-1): 回答是否紧扣用户意图，没有跑题？
3. accuracy (0-1): 回答中的数据/事实是否与工具返回结果一致？
4. passed (true/false): 三项均≥0.6 且无明显错误时为 true
5. improvement_suggestion: 如果 passed=false，给出简明改进建议（一句话）

请严格按照以下 JSON 格式返回，不要输出其他内容:
{{"completeness": 0.8, "relevance": 0.9, "accuracy": 0.7, "passed": true, "improvement_suggestion": ""}}"""

    try:
        # P2-9: Use Gateway instead of direct ChatOpenAI construction
        resolved_critic = None
        try:
            from app.services.llm_helpers import resolve_model_config

            org_id = config.org_id or "default"
            scene_code = state.get("scene_code", "")
            agent_code = state.get("agent_code", "")
            resolved_critic = await resolve_model_config(org_id, scene_code, agent_code, complexity_tier="low")
        except Exception:
            logger.debug("LLM gateway unavailable in critic_node, using default mini_model")

        if resolved_critic:
            critic_llm = ChatOpenAI(
                model=resolved_critic.get("model", config.mini_model),
                api_key=resolved_critic.get("api_key", config.api_key),
                base_url=resolved_critic.get("base_url", config.base_url),
                temperature=0.1,
                max_tokens=300,
            )
        else:
            critic_llm = ChatOpenAI(
                model=config.mini_model,
                api_key=config.api_key,
                base_url=config.base_url,
                temperature=0.1,
                max_tokens=300,
            )
        # Avoid with_structured_output — many proxied/non-OpenAI APIs reject
        # additionalProperties in the JSON schema.  Parse JSON manually instead.
        import json as _json
        import re as _re

        raw_response = await critic_llm.ainvoke([SystemMessage(content=critic_prompt)])
        raw_text = raw_response.content.strip()
        # Extract JSON from possible markdown fences
        json_match = _re.search(r"\{.*\}", raw_text, _re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON found in critic response: {raw_text[:200]}")
        parsed = _json.loads(json_match.group())
        result = CriticResult(**parsed)
    except Exception as e:
        # Critic failure should never block the response — silently pass
        logger.warning(f"[CriticNode] Evaluation failed, silently passing: {e}")
        return {
            "critic_passed": True,
            "critic_feedback": f"评审异常，自动通过: {e}",
            "current_phase": AgentPhase.RESPONDING,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.CRITIQUING.value,
                    content="质量评审异常，自动通过",
                )
            ],
        }

    critic_feedback = (
        f"完整性: {result.completeness:.0%}, " f"相关性: {result.relevance:.0%}, " f"准确性: {result.accuracy:.0%}"
    )
    if result.improvement_suggestion:
        critic_feedback += f" | 建议: {result.improvement_suggestion}"

    if result.passed:
        logger.info(f"[CriticNode] ✅ Passed: {critic_feedback}")
        return {
            "critic_passed": True,
            "critic_feedback": critic_feedback,
            "confidence_score": min(result.completeness, result.relevance, result.accuracy),
            "current_phase": AgentPhase.RESPONDING,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.CRITIQUING.value,
                    content=f"质量评审通过: {critic_feedback}",
                )
            ],
        }

    # Failed: send back for one correction pass
    logger.info(f"[CriticNode] ❌ Failed: {critic_feedback}")
    guidance = (
        f"## Critic 评审未通过\n"
        f"**评分**: 完整性={result.completeness:.0%} 相关性={result.relevance:.0%} 准确性={result.accuracy:.0%}\n"
        f"**改进要求**: {result.improvement_suggestion}\n"
        f"请根据以上反馈修正回复。"
    )
    return {
        "critic_passed": False,
        "critic_feedback": critic_feedback,
        "reflection_guidance": guidance,
        "needs_replanning": True,
        "current_phase": AgentPhase.PLANNING,
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.CRITIQUING.value,
                content=f"质量评审未通过，需要修正: {result.improvement_suggestion}",
            )
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: error_node
# ═══════════════════════════════════════════════════════════════════════════════


async def error_node(state: AgentState) -> dict:
    """
    Global error handler with multi-level recovery.

    P1 Fix: 3-level recovery instead of single boolean flag:
      Level 0→1: Clear failed tools, ask LLM for alternative approach
      Level 1→2: Disable tools entirely, ask for best-effort text answer
      Level 2+:  Give up gracefully with user-facing message
    """
    error_msg = state.get("error", "未知错误")
    recovery_level = state.get("error_recovery_level", 0)
    iteration = state.get("iteration", 0)

    logger.error(f"[ErrorNode] Handling error: {error_msg} (level={recovery_level}, iter={iteration})")

    # P1 Plugin: ON_ERROR hook
    try:
        await plugin_system_service.run_hooks(
            ExtensionPoint.ON_ERROR,
            {"error": error_msg, "recovery_level": recovery_level, "iteration": iteration},
        )
    except Exception as e:
        logger.debug(f"[ErrorNode] ON_ERROR hook error: {e}")

    if recovery_level == 0 and iteration < 5:
        # Level 1: Clear failed tools, ask LLM to try alternative approach
        return {
            "error": None,
            "error_recovery_level": 1,
            "error_recovery_attempted": True,
            "pending_tool_calls": [],
            "current_phase": AgentPhase.PLANNING,
            "messages": [
                HumanMessage(content=f"[错误恢复L1] 前序操作失败: {error_msg}。请尝试一个不涉及此错误的替代方案。")
            ],
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.ERROR.value,
                    content=f"恢复L1: 切换方案以避免: {error_msg}",
                )
            ],
        }
    elif recovery_level == 1 and iteration < 5:
        # Level 2: Disable tools, ask for best-effort text answer
        return {
            "error": None,
            "error_recovery_level": 2,
            "pending_tool_calls": [],
            "requires_tools": False,
            "current_phase": AgentPhase.PLANNING,
            "messages": [
                HumanMessage(
                    content="[错误恢复L2] 工具调用持续失败。请不使用任何工具，基于已有信息给出最佳回答。如信息不足请如实说明。"
                )
            ],
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.ERROR.value,
                    content=f"恢复L2: 降级为纯文本模式: {error_msg}",
                )
            ],
        }

    # Level 3: Give up gracefully
    return {
        "final_response": f"⚠️ 系统执行过程中遇到了难以恢复的问题: {error_msg}。您可以尝试换一种说法再次提问。",
        "current_phase": AgentPhase.RESPONDING,
        "thinking_steps": [
            ThinkingStep(
                phase=AgentPhase.ERROR.value,
                content=f"❌ 遇到严重故障，停止执行: {error_msg}",
            )
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPER: Role-based Sensitive Field Masking
# ═══════════════════════════════════════════════════════════════════════════════

# Sensitive field patterns with role access levels
# Only roles at or above the specified level can see unmasked values
import re as _re  # noqa: E402

_SENSITIVE_FIELD_RULES = [
    # (pattern, mask_replacement, minimum_role_level)
    # Role levels: guest=0, employee=1, manager=2, boss=3, founder=4
    (_re.compile(r"(薪[资酬水]|工资|月薪|年薪|底薪|基本工资)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[薪资信息已隐藏]", 3),
    (_re.compile(r"(提成|奖金|绩效奖|年终奖)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[奖金信息已隐藏]", 3),
    (_re.compile(r"(社保|公积金|五险一金)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[社保信息已隐藏]", 3),
    (_re.compile(r"(合同金额|签约金额|合同价)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[合同金额已隐藏]", 2),
    (_re.compile(r"(成本价|进货价|底价)\s*[:：]?\s*[\d,.]+\s*[元万千]?"), "[成本信息已隐藏]", 2),
    (_re.compile(r"(利润率|毛利率|净利率)\s*[:：]?\s*[\d,.]+\s*%?"), "[利润信息已隐藏]", 2),
]

_ROLE_LEVELS = {
    "guest": 0,
    "employee": 1,
    "manager": 2,
    "boss": 3,
    "founder": 4,
}


def _mask_sensitive_fields(content: str, user_role: str) -> str:
    """
    P1 Security: Mask sensitive financial/HR fields based on user role.

    Higher-privilege roles see more data. Lower-privilege roles get
    sensitive fields replaced with '[已隐藏]' placeholders.
    """
    if not content or not user_role:
        return content

    current_level = _ROLE_LEVELS.get(user_role, 1)

    for pattern, replacement, min_level in _SENSITIVE_FIELD_RULES:
        if current_level < min_level:
            content = pattern.sub(replacement, content)

    return content
