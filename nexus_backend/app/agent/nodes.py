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

import json
import time
import asyncio
import logging
from typing import List, Optional

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    BaseMessage,
)
from langchain_openai import ChatOpenAI

from app.agent.state import (
    AgentConfig,
    AgentPhase,
    AgentState,
    QueryComplexity,
    ThinkingStep,
    ToolCallRecord,
)
from app.tools import get_tool, get_all_tools_schema
from app.services.content_moderation import scan_content, sanitize_output

logger = logging.getLogger(__name__)

# Tool schemas (computed once at import time)
_ALL_TOOL_SCHEMAS = get_all_tools_schema()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_llm(config: AgentConfig, model: Optional[str] = None, streaming: bool = False):
    """Get a LangChain ChatOpenAI instance with the provided config."""
    return ChatOpenAI(
        model=model or config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=config.temperature,
        streaming=streaming,
        timeout=60.0,
    )


def _messages_to_lc_format(messages) -> List[BaseMessage]:
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
                result.append(ToolMessage(content=content, tool_call_id=msg.get("tool_call_id", ""), name=msg.get("name", "")))
    return result


async def _execute_single_tool(
    record: ToolCallRecord,
    config: AgentConfig,
) -> ToolCallRecord:
    """Execute a single tool with RBAC, confirmation gates, and retry."""
    tool = get_tool(record.tool_name)
    if not tool:
        record.status = "error"
        record.result = f"Error: Tool '{record.tool_name}' not found."
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
    confirmation_msg = tool.check_confirmation(
        record.tool_args, system_confirmed=config.system_confirmed
    )
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
                    },
                ),
                timeout=timeout,
            )
            record.result = str(result)
            record.status = "success"
            record.duration_ms = int((time.time() - start_time) * 1000)
            return record
        except asyncio.TimeoutError:
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

    # Convert to LC format
    lc_msgs = _messages_to_lc_format(messages)

    # ── RAG Injection ──
    # If we have retrieved context, prepend it to the history or inject into system prompt
    if rag_context and iteration == 0:
        found_sys = False
        for i, m in enumerate(lc_msgs):
            if isinstance(m, SystemMessage):
                m.content += f"\n\n[检索到的参考知识]:\n{rag_context}"
                found_sys = True
                break
        if not found_sys:
            lc_msgs.insert(0, SystemMessage(content=f"你可以参考以下背景知识来回答问题:\n{rag_context}"))

    # Decide whether to include tools
    complexity = state.get("complexity", QueryComplexity.MODERATE)
    include_tools = complexity != QueryComplexity.SIMPLE

    # ── Task 1 & 2: LangChain Planning + Streaming ──
    # Use ChatOpenAI with streaming and bind_tools
    llm = _get_llm(config, model=model, streaming=True)
    if include_tools:
        llm = llm.bind_tools(_ALL_TOOL_SCHEMAS)

    thinking_step = ThinkingStep(
        phase=AgentPhase.PLANNING.value,
        content=f"正在分析意图并规划执行路径... (轮次 {iteration + 1})",
    )

    # Call LLM via standard invoke (streaming tokens will be caught by graph callbacks if set)
    try:
        # We use astream to capture tokens if needed, but for the node return we need the full message
        # In a real heavy-streaming app, we'd use a callback handler passed via config
        ai_msg = await llm.ainvoke(lc_msgs)
    except Exception as e:
        logger.error(f"[PlanNode] LLM call failed: {e}")
        return {
            "error": f"LLM 规划失败: {str(e)}",
            "current_phase": AgentPhase.ERROR,
            "thinking_steps": [ThinkingStep(
                phase=AgentPhase.PLANNING.value,
                content=f"⚠️ LLM 调用异常: {str(e)}",
            )],
        }

    # Track usage (LangChain usually provides this in additional_kwargs or response_metadata)
    usage = ai_msg.response_metadata.get("token_usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    tool_calls_raw = ai_msg.tool_calls
    content = ai_msg.content or ""

    # Build pending tool call records
    pending_tools: List[ToolCallRecord] = []
    if tool_calls_raw:
        for tc in tool_calls_raw:
            pending_tools.append(ToolCallRecord(
                tool_name=tc.get("name", "unknown"),
                tool_args=tc.get("args", {}),
                tool_call_id=tc.get("id", ""),
            ))

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
    
    try:
        tasks = [_execute_single_tool(record, config) for record in pending]
        completed: List[ToolCallRecord] = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=False),
            timeout=gather_timeout,
        )
    except asyncio.TimeoutError:
        logger.error(f"[ExecuteNode] Tool gather timed out after {gather_timeout}s")
        return {
            "error": f"工具执行整体超时 ({gather_timeout}秒)",
            "current_phase": AgentPhase.ERROR,
            "thinking_steps": [ThinkingStep(
                phase=AgentPhase.EXECUTING.value,
                content=f"⚠️ 工具执行整体超时 ({gather_timeout}秒)",
            )],
        }
    except Exception as e:
        logger.error(f"[ExecuteNode] Tool execution fatal error: {e}")
        return {
            "error": f"工具执行异常: {str(e)}",
            "current_phase": AgentPhase.ERROR,
            "thinking_steps": [ThinkingStep(
                phase=AgentPhase.EXECUTING.value,
                content=f"⚠️ 工具执行崩溃: {str(e)}",
            )],
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
        
        result_steps.append(ThinkingStep(
            phase=AgentPhase.EXECUTING.value,
            content=f"工具 [{record.tool_name}] 执行完毕 ({record.status})",
            tool_name=record.tool_name,
            tool_result=record.result[:500] if record.result else None,
            duration_ms=record.duration_ms,
        ))

    # Merge with previously completed tools
    all_completed = list(state.get("completed_tool_calls", [])) + completed

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
    Self-reflection: validate LLM response using heuristics and optional LLM-check.
    """
    config: AgentConfig = state["config"]
    messages = state.get("messages", [])
    iteration = state.get("iteration", 0)
    complexity = state.get("complexity", QueryComplexity.MODERATE)

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

    # ── Heuristic Check 1: Empty response ──
    if not last_ai_content.strip() or len(last_ai_content.strip()) < 5:
        if state.get("completed_tool_calls"):
            return {
                "reflection": "回复内容为空，需要整合工具结果重新回答。",
                "needs_replanning": True if iteration < config.max_iterations else False,
                "current_phase": AgentPhase.PLANNING if iteration < config.max_iterations else AgentPhase.RESPONDING,
                "thinking_steps": [ThinkingStep(
                    phase=AgentPhase.REFLECTING.value,
                    content="检测到未正常生成回复，触发重试路径",
                )],
            }

    # ── Heuristic Check 2: Hallucination ──
    is_hallucination = False
    hallucination_reason = ""

    if complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL) and not state.get("completed_tool_calls"):
        hallucination_keywords = ["查询到", "系统显示", "数据显示", "结果是"]
        if any(kw in last_ai_content for kw in hallucination_keywords):
            is_hallucination = True
            hallucination_reason = "复杂查询未调用工具却产出了具体数据"

    # ── Task 3: Groundedness Check (RAG Comparison) ──
    grounded_warning = None
    rag_context = state.get("rag_context", "")
    if rag_context and last_ai_content:
        prompt = f"""[事实核查任务]
请比较【参考知识】与【AI回复】，判断回复是否完全基于背景知识，是否存在编造或矛盾。

参考知识:
{rag_context}

AI回复:
{last_ai_content}

回复格式为 JSON: {{"is_grounded": bool, "reason": "str", "score": float}} 
其中 is_grounded 为 false 表示存在幻觉或编造。
"""
        try:
            llm = _get_llm(config, model=config.mini_model)
            llm_eval = await llm.ainvoke([HumanMessage(content=prompt)])
            eval_data = json.loads(llm_eval.content)
            if not eval_data.get("is_grounded"):
                is_hallucination = True
                grounded_warning = eval_data.get("reason", "事实偏差")
                logger.warning(f"[Reflect] Ungrounded response: {grounded_warning}")
        except Exception as e:
            logger.debug(f"[ReflectNode] Groundedness check failed: {e}")

    # ── Fallback to LLM-based Reflection if no RAG or secondary check ──
    if config.reflect_use_llm and last_ai_content and not is_hallucination:
        messages_text = "\n".join([f"{m.type}: {m.content[:200]}" for m in messages[-3:]])
        prompt = f"""请评估 AI 的最新回复是否包含编造的信息（幻觉）。
上下文摘要:
{messages_text}

AI 回复:
{last_ai_content}

回复格式为 JSON: {{"is_hallucination": bool, "reason": "str"}}
"""
        try:
            llm = _get_llm(config, model=config.mini_model)
            llm_eval = await llm.ainvoke([HumanMessage(content=prompt)])
            eval_data = json.loads(llm_eval.content)
            if eval_data.get("is_hallucination"):
                is_hallucination = True
                hallucination_reason = eval_data.get("reason", "存在事实偏差")
        except Exception as e:
            logger.debug(f"[ReflectNode] LLM eval failed: {e}")

    if grounded_warning:
        hallucination_reason = grounded_warning

    # ── Content Safety ──
    is_safe, violations = scan_content(last_ai_content)
    if not is_safe:
        last_ai_content = sanitize_output(last_ai_content)

    confidence = 0.85
    if is_hallucination:
        confidence = 0.3
    if state.get("completed_tool_calls"):
        confidence = 0.95

    needs_replanning = is_hallucination and iteration < config.max_iterations

    if needs_replanning:
        return {
            "messages": [HumanMessage(content=f"[自我指引] 发现回复可能包含不实内容({hallucination_reason})。请务必核实工具返回的数据，严禁编造信息。")],
            "reflection": f"触发幻觉修正: {hallucination_reason}",
            "is_hallucination": True,
            "needs_replanning": True,
            "confidence_score": confidence,
            "current_phase": AgentPhase.PLANNING,
            "thinking_steps": [ThinkingStep(
                phase=AgentPhase.REFLECTING.value,
                content=f"⚠️ 检测到潜在事实错误: {hallucination_reason}，正在修正...",
            )],
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


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: respond_node
# ═══════════════════════════════════════════════════════════════════════════════

async def respond_node(state: AgentState) -> dict:
    """
    Finalize output and format for UI.
    """
    final_response = state.get("final_response", "")

    if not final_response:
        for msg in reversed(state.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content
                break

    # Final moderation filter
    final_response = sanitize_output(final_response)

    return {
        "final_response": final_response or "抱歉，系统处理出现异常，请重试。",
        "current_phase": AgentPhase.DONE,
        "thinking_steps": [ThinkingStep(
            phase=AgentPhase.RESPONDING.value,
            content=f"思考路径完成，正在输出回复 (置信度: {state.get('confidence_score', 0.8):.0%})",
        )],
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  NODE: error_node
# ═══════════════════════════════════════════════════════════════════════════════

async def error_node(state: AgentState) -> dict:
    """
    Global error handler node. Logs mistakes and tries to recover or exit safely.
    """
    error_msg = state.get("error", "未知错误")
    recovered = state.get("error_recovery_attempted", False)
    iteration = state.get("iteration", 0)

    logger.error(f"[ErrorNode] Handling graph error: {error_msg} (recovered={recovered})")

    if not recovered and iteration < 3:
        # Try once to clear pending tools and ask LLM to try a different path
        return {
            "error": None, # Clear error
            "error_recovery_attempted": True,
            "pending_tool_calls": [],
            "current_phase": AgentPhase.PLANNING,
            "messages": [HumanMessage(content=f"[错误恢复] 前序操作失败: {error_msg}。请尝试一个不涉及此错误的替代方案。")],
            "thinking_steps": [ThinkingStep(
                phase=AgentPhase.ERROR.value,
                content=f"正在尝试从错误中恢复: {error_msg}",
            )],
        }

    return {
        "final_response": f"⚠️ 系统执行过程中遇到了难以恢复的问题: {error_msg}。您可以尝试换一种说法再次提问。",
        "current_phase": AgentPhase.RESPONDING,
        "thinking_steps": [ThinkingStep(
            phase=AgentPhase.ERROR.value,
            content=f"❌ 遇到严重故障，停止执行: {error_msg}",
        )],
    }