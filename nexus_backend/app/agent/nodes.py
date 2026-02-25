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
import logging
import time

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
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


logger = logging.getLogger(__name__)


# P1 Fix: Cache tool schemas to avoid rebuilding on every request
_tool_schemas_cache = None
_tool_schemas_count = None


def _get_tool_schemas():
    """Get tool schemas with caching (invalidates when tool count changes)."""
    global _tool_schemas_cache, _tool_schemas_count
    schemas = get_all_tools_schema()
    if _tool_schemas_cache is None or len(schemas) != _tool_schemas_count:
        _tool_schemas_cache = schemas
        _tool_schemas_count = len(schemas)
    return _tool_schemas_cache


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _get_llm(
    config: AgentConfig, model: str | None = None, streaming: bool = False, resolved_config: dict | None = None
):
    """Get a LangChain ChatOpenAI instance with the provided config.

    If resolved_config is provided (from LLM gateway), use it.
    Otherwise fall back to AgentConfig settings.
    """
    if resolved_config:
        return ChatOpenAI(
            model=resolved_config.get("model", model or config.model),
            api_key=resolved_config.get("api_key", config.api_key),
            base_url=resolved_config.get("base_url", config.base_url),
            temperature=resolved_config.get("temperature", config.temperature),
            streaming=streaming,
            timeout=resolved_config.get("timeout", 60.0),
        )
    return ChatOpenAI(
        model=model or config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        streaming=streaming,
        timeout=60.0,
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

    # 3. Execute with configurable timeout and retry
    start_time = time.time()
    last_error = None
    timeout = config.tool_timeout if hasattr(config, "tool_timeout") else 30.0

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


async def plan_node(state: AgentState) -> dict:
    """
    Call the LLM with the current messages + tool schemas.
    """
    config: AgentConfig = state["config"]
    model = state.get("selected_model", config.model)
    messages = state.get("messages", [])
    iteration = state.get("iteration", 0)
    rag_context = state.get("rag_context", "")

    # Resolve model via LLM gateway
    resolved = None
    try:
        from app.services.llm_helpers import resolve_model_config

        org_id = config.org_id or "default"
        scene_code = state.get("scene_code", "")
        agent_code = state.get("agent_code", "")
        resolved = await resolve_model_config(org_id, scene_code, agent_code)
    except Exception:
        pass

    # Convert to LC format
    lc_msgs = _messages_to_lc_format(messages)

    # ── Dynamic System Prompt Injection ──
    # Inject user_role and available_tools into the system prompt
    if iteration == 0:
        extra_lines = []
        user_role = config.user_role
        if user_role:
            extra_lines.append(f"当前用户角色: {user_role}")

        tool_schemas = _get_tool_schemas()
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
    llm = _get_llm(config, model=model, streaming=True, resolved_config=resolved)
    if include_tools:
        llm = llm.bind_tools(_get_tool_schemas())

    thinking_step = ThinkingStep(
        phase=AgentPhase.PLANNING.value,
        content=f"正在分析意图并规划执行路径... (轮次 {iteration + 1})",
    )

    # P1 Plugin: PRE_CHAT hook
    try:
        hook_ctx = await plugin_system_service.run_hooks(
            ExtensionPoint.PRE_CHAT,
            {"messages": lc_msgs, "model": model, "config": config},
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
        record_llm_latency(model=model or config.model, duration_ms=(time.time() - _llm_start) * 1000)
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
            pending_tools.append(
                ToolCallRecord(
                    tool_name=tc.get("name", "unknown"),
                    tool_args=tc.get("args", {}),
                    tool_call_id=tc.get("id", ""),
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

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: execute_node
# ═══════════════════════════════════════════════════════════════════════════════


async def execute_node(state: AgentState) -> dict:
    """
    Execute all pending tool calls in parallel.
    """
    config: AgentConfig = state["config"]
    pending = state.get("pending_tool_calls", [])

    if not pending:
        return {
            "current_phase": AgentPhase.REFLECTING,
            "pending_tool_calls": [],
        }

    tool_names = ", ".join(t.tool_name for t in pending)
    thinking_step = ThinkingStep(
        phase=AgentPhase.EXECUTING.value,
        content=f"正在并行执行 {len(pending)} 个工具: {tool_names}",
        tool_name=tool_names,
    )

    # Execute all tools in parallel with overall timeout
    gather_timeout = config.gather_timeout if hasattr(config, "gather_timeout") else 60.0

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
        tasks = [_execute_single_tool(record, config, shared_idempotency_cache) for record in pending]
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

    # P1 Plugin: POST_TOOL hook
    try:
        await plugin_system_service.run_hooks(
            ExtensionPoint.POST_TOOL,
            {
                "completed_tools": [
                    {"name": r.tool_name, "status": r.status, "duration_ms": r.duration_ms}
                    for r in completed
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

    # Resolve model via LLM gateway
    resolved = None
    try:
        from app.services.llm_helpers import resolve_model_config

        org_id = config.org_id or "default"
        scene_code = state.get("scene_code", "")
        agent_code = state.get("agent_code", "")
        resolved = await resolve_model_config(org_id, scene_code, agent_code)
    except Exception:
        pass

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
    # IMPORTANT: Skip this check when tools were called and returned real data.
    # Tool results are authoritative data sources — they should NOT be
    # second-guessed by RAG context (which may show "搜索失败" or stale data).
    grounded_warning = None
    rag_context = state.get("rag_context", "")
    has_successful_tools = any(getattr(t, "status", None) == "success" for t in completed_tools)
    rag_search_failed = (
        not rag_context or "搜索失败" in rag_context or "缺少" in rag_context or len(rag_context.strip()) < 20
    )

    if rag_context and last_ai_content and not is_hallucination and not has_successful_tools and not rag_search_failed:
        prompt = f"""[事实核查任务]
请比较【参考知识】与【AI回复】，判断回复是否完全基于背景知识，是否存在编造或矛盾。

参考知识:
{rag_context[:2000]}

AI回复:
{last_ai_content[:1000]}
"""
        try:
            llm = _get_llm(config, model=config.mini_model, resolved_config=resolved)
            structured_llm = llm.with_structured_output(GroundednessCheck)
            eval_result: GroundednessCheck = await structured_llm.ainvoke([HumanMessage(content=prompt)])
            if not eval_result.is_grounded:
                is_hallucination = True
                grounded_warning = eval_result.reason or "事实偏差"
                logger.warning(f"[Reflect] Ungrounded response: {grounded_warning}")
        except Exception as e:
            logger.debug(f"[ReflectNode] Groundedness check failed: {e}")
    elif has_successful_tools and rag_context:
        logger.info("[Reflect] Layer 4 skipped: tools returned authoritative data, RAG groundedness check not needed")

    # ── Layer 5: LLM-based reflection ──
    # Skip LLM reflection if tools returned real data — tool results are ground truth.
    if config.reflect_use_llm and last_ai_content and not is_hallucination and not has_successful_tools:
        messages_text = "\n".join([f"{m.type}: {m.content[:200]}" for m in messages[-3:]])
        prompt = f"""请评估 AI 的最新回复是否包含编造的信息（幻觉）。

检查要点:
1. 是否声称有数据但实际未调用工具?
2. 是否引用了不存在的文档或来源?
3. 数值是否合理且有依据?

上下文摘要:
{messages_text}

AI 回复:
{last_ai_content}
"""
        try:
            llm = _get_llm(config, model=config.mini_model, resolved_config=resolved)
            structured_llm = llm.with_structured_output(HallucinationCheck)
            eval_result: HallucinationCheck = await structured_llm.ainvoke([HumanMessage(content=prompt)])
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
        return {
            "messages": [
                HumanMessage(
                    content=f"[自我指引] 发现回复可能包含不实内容({hallucination_reason})。请务必核实工具返回的数据，严禁编造信息。"
                )
            ],
            "reflection": f"触发幻觉修正: {hallucination_reason}",
            "is_hallucination": True,
            "needs_replanning": True,
            "confidence_score": confidence,
            "current_phase": AgentPhase.PLANNING,
            "iteration": iteration + 1,
            "thinking_steps": [
                ThinkingStep(
                    phase=AgentPhase.REFLECTING.value,
                    content=f"⚠️ 检测到潜在事实错误: {hallucination_reason}，正在修正...",
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
    """
    import re

    issues = []

    # Extract all numbers from AI response
    ai_numbers = re.findall(r"\d+(?:\.\d+)?", ai_response)

    # Get all numbers from tool results
    tool_numbers = []
    for tool in tool_results:
        if tool.result:
            tool_numbers.extend(re.findall(r"\d+(?:\.\d+)?", str(tool.result)))

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

    # Require at least 3 ungrounded numbers to flag (avoids noise from dates, IDs, etc.)
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
