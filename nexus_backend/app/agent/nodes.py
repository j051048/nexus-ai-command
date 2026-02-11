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
from typing import Any, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.agent.state import (
    AgentConfig,
    AgentPhase,
    AgentState,
    QueryComplexity,
    ThinkingStep,
    ToolCallRecord,
)
from app.tools import get_tool, get_all_tools_schema, TOOL_REGISTRY
from app.services.content_moderation import scan_content, sanitize_output
from app.core.trace_logger import TraceLogger

logger = logging.getLogger(__name__)

# Tool schemas (computed once at import time)
_ALL_TOOL_SCHEMAS = get_all_tools_schema()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_openai_client(config: AgentConfig):
    """Build an httpx-compatible OpenAI async client."""
    import httpx

    base_url = config.base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    return {
        "url": f"{base_url}/chat/completions",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}",
        },
    }


async def _call_llm(
    messages: List[Dict[str, Any]],
    config: AgentConfig,
    model: str,
    tools: Optional[List] = None,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Non-streaming LLM call via httpx (maximum proxy compatibility).

    Returns the full parsed response dict with:
      - content: str | None
      - tool_calls: list | None
      - usage: dict | None
    """
    import httpx

    client_cfg = _build_openai_client(config)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature if temperature is not None else config.temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                client_cfg["url"],
                headers=client_cfg["headers"],
                json=payload,
            )
            if response.status_code != 200:
                error_text = response.text[:300]
                logger.error(f"LLM API error {response.status_code}: {error_text}")
                return {
                    "content": f"LLM API Error ({response.status_code}): {error_text}",
                    "tool_calls": None,
                    "usage": None,
                }

            data = response.json()
            choice = data["choices"][0]["message"]

            return {
                "content": choice.get("content"),
                "tool_calls": choice.get("tool_calls"),
                "usage": data.get("usage"),
            }

    except httpx.TimeoutException:
        logger.error("LLM API call timed out")
        return {"content": "LLM 请求超时，请稍后重试。", "tool_calls": None, "usage": None}
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        return {"content": f"LLM 调用失败: {str(e)}", "tool_calls": None, "usage": None}


def _messages_to_openai_format(messages) -> List[Dict[str, Any]]:
    """Convert LangChain BaseMessages to OpenAI API format dicts."""
    result = []
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            entry = {"role": "assistant", "content": msg.content}
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
                if not msg.content:
                    entry["content"] = None
            if msg.additional_kwargs.get("tool_calls"):
                entry["tool_calls"] = msg.additional_kwargs["tool_calls"]
                if not msg.content:
                    entry["content"] = None
            result.append(entry)
        elif isinstance(msg, ToolMessage):
            result.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "name": msg.name,
                "content": msg.content,
            })
        elif isinstance(msg, dict):
            result.append(msg)
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

    # 3. Execute with retry
    start_time = time.time()
    last_error = None
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
                timeout=30.0,
            )
            record.result = str(result)
            record.status = "success"
            record.duration_ms = int((time.time() - start_time) * 1000)
            return record
        except asyncio.TimeoutError:
            record.status = "error"
            record.result = f"Error: Tool '{record.tool_name}' timed out after 30s."
            record.duration_ms = int((time.time() - start_time) * 1000)
            return record
        except Exception as e:
            last_error = e
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))

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

    # Convert to OpenAI format
    openai_msgs = _messages_to_openai_format(messages)

    # ── RAG Injection ──
    # If we have retrieved context, prepend it to the history or inject into system prompt
    if rag_context and iteration == 0:
        # Check if system prompt is first
        if openai_msgs and openai_msgs[0]["role"] == "system":
            openai_msgs[0]["content"] += f"\n\n[检索到的参考知识]:\n{rag_context}"
        else:
            openai_msgs.insert(0, {
                "role": "system",
                "content": f"你可以参考以下背景知识来回答问题:\n{rag_context}"
            })

    # Decide whether to include tools
    complexity = state.get("complexity", QueryComplexity.MODERATE)
    include_tools = complexity != QueryComplexity.SIMPLE

    thinking_step = ThinkingStep(
        phase=AgentPhase.PLANNING.value,
        content=f"正在分析意图并规划执行路径... (轮次 {iteration + 1})",
    )

    # Call LLM
    try:
        llm_response = await _call_llm(
            openai_msgs,
            config,
            model=model,
            tools=_ALL_TOOL_SCHEMAS if include_tools else None,
        )
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

    # Track tokens
    usage = llm_response.get("usage") or {}
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)

    tool_calls_raw = llm_response.get("tool_calls") or []
    content = llm_response.get("content") or ""

    # Build pending tool call records
    pending_tools: List[ToolCallRecord] = []
    if tool_calls_raw:
        for tc in tool_calls_raw:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            pending_tools.append(ToolCallRecord(
                tool_name=fn.get("name", "unknown"),
                tool_args=args,
                tool_call_id=tc.get("id", ""),
            ))

    # Construct the AIMessage to append to history
    ai_msg_kwargs = {"content": content or ""}
    if tool_calls_raw:
        ai_msg_kwargs["additional_kwargs"] = {"tool_calls": tool_calls_raw}

    result = {
        "messages": [AIMessage(**ai_msg_kwargs)],
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

    # Execute all tools in parallel with timeout handling
    try:
        tasks = [_execute_single_tool(record, config) for record in pending]
        completed: List[ToolCallRecord] = await asyncio.gather(*tasks)
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
    has_critical_error = False
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

    # ── LLM-based Reflection (Optional) ──
    if config.reflect_use_llm and last_ai_content and not is_hallucination:
        # Ask LLM if the response is grounded in the conversation history
        history_text = "\n".join([f"{m.type}: {m.content[:200]}" for m in messages[-5:]])
        prompt = f"""请评估 AI 的最新回复是否包含编造的信息（幻觉）。
上下文摘要:
{history_text}

AI 回复:
{last_ai_content}

回复格式为 JSON: {{"is_hallucination": bool, "reason": "str", "score": float}}
"""
        try:
            llm_eval = await _call_llm(
                [{"role": "user", "content": prompt}],
                config,
                model=config.mini_model,
                temperature=0.0
            )
            eval_data = json.loads(llm_eval.get("content", "{}"))
            if eval_data.get("is_hallucination"):
                is_hallucination = True
                hallucination_reason = eval_data.get("reason", "LLM 评估存在事实偏差")
        except Exception as e:
            logger.debug(f"[ReflectNode] LLM eval failed: {e}")

    # ── Content Safety ──
    is_safe, violations = scan_content(last_ai_content)
    if not is_safe:
        last_ai_content = sanitize_output(last_ai_content)

    confidence = 0.85
    if is_hallucination: confidence = 0.3
    if state.get("completed_tool_calls"): confidence = 0.95

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
    config: AgentConfig = state["config"]

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