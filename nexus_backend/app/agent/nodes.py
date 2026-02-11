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

    For SIMPLE queries, the LLM will usually respond directly (no tools).
    For COMPLEX queries, it will produce tool_calls that feed into execute_node.
    """
    config: AgentConfig = state["config"]
    model = state.get("selected_model", config.model)
    messages = state.get("messages", [])
    iteration = state.get("iteration", 0)

    # Convert to OpenAI format
    openai_msgs = _messages_to_openai_format(messages)

    # Decide whether to include tools
    complexity = state.get("complexity", QueryComplexity.MODERATE)
    include_tools = complexity != QueryComplexity.SIMPLE

    thinking_step = ThinkingStep(
        phase=AgentPhase.PLANNING.value,
        content=f"正在分析用户意图，规划执行策略... (迭代 {iteration + 1})",
    )

    # Call LLM
    llm_response = await _call_llm(
        openai_msgs,
        config,
        model=model,
        tools=_ALL_TOOL_SCHEMAS if include_tools else None,
    )

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
        ai_msg_kwargs["content"] = content or ""
        ai_msg_kwargs["additional_kwargs"] = {"tool_calls": tool_calls_raw}

    result = {
        "messages": [AIMessage(**ai_msg_kwargs)],
        "current_phase": AgentPhase.EXECUTING if pending_tools else AgentPhase.REFLECTING,
        "plan": content or "(tool calls planned)",
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
    Execute all pending tool calls in parallel, then feed results back as
    ToolMessage objects so the LLM can synthesize them.
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
        content=f"正在执行工具: {tool_names}",
        tool_name=tool_names,
    )

    # Execute all tools in parallel
    tasks = [_execute_single_tool(record, config) for record in pending]
    completed: List[ToolCallRecord] = await asyncio.gather(*tasks)

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
        result_steps.append(ThinkingStep(
            phase=AgentPhase.EXECUTING.value,
            content=f"工具 {record.tool_name} → {record.status}",
            tool_name=record.tool_name,
            tool_result=record.result[:500] if record.result else None,
            duration_ms=record.duration_ms,
        ))

    # Merge with previously completed tools
    all_completed = list(state.get("completed_tool_calls", [])) + completed

    return {
        "messages": tool_messages,
        "current_phase": AgentPhase.PLANNING,  # Go back to planning for LLM to synthesize
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
    Self-reflection: validate the LLM's response for quality and hallucination.

    Checks:
    1. Is the response empty or too short?
    2. Does it reference data NOT from tools? (hallucination heuristic)
    3. Content safety scan
    4. Confidence scoring

    If issues found → set needs_replanning = True so the graph loops back.
    """
    config: AgentConfig = state["config"]
    messages = state.get("messages", [])
    iteration = state.get("iteration", 0)
    complexity = state.get("complexity", QueryComplexity.MODERATE)

    # Extract the last AI message content
    last_ai_content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            last_ai_content = msg.content or ""
            break

    thinking_step = ThinkingStep(
        phase=AgentPhase.REFLECTING.value,
        content="正在验证回复质量...",
    )

    # ── Check 1: Empty or trivially short response ──
    if not last_ai_content.strip() or len(last_ai_content.strip()) < 5:
        # If we have completed tools but empty response, need replanning
        if state.get("completed_tool_calls"):
            return {
                "reflection": "回复为空但工具已执行，需要重新生成回复。",
                "is_hallucination": False,
                "needs_replanning": True if iteration < config.max_iterations - 1 else False,
                "confidence_score": 0.1,
                "current_phase": AgentPhase.PLANNING if iteration < config.max_iterations - 1 else AgentPhase.RESPONDING,
                "thinking_steps": [ThinkingStep(
                    phase=AgentPhase.REFLECTING.value,
                    content="检测到空回复，触发重新规划",
                )],
            }
        # Simple query with short response is OK
        pass

    # ── Check 2: Hallucination heuristic ──
    # If complexity required tools but none were used, flag as suspicious
    is_hallucination = False
    if (
        complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
        and not state.get("completed_tool_calls")
        and iteration == 0
    ):
        # LLM answered a complex question without using any tools — suspicious
        hallucination_keywords = ["根据数据", "数据显示", "系统显示", "查询结果"]
        if any(kw in last_ai_content for kw in hallucination_keywords):
            is_hallucination = True
            logger.warning(
                f"[Reflect] Possible hallucination detected: "
                f"complex query answered without tools, contains data-like language"
            )

    # ── Check 3: Content safety ──
    is_safe, violations = scan_content(last_ai_content)
    if not is_safe:
        logger.warning(f"[Reflect] Output contained {len(violations)} safety violations")
        last_ai_content = sanitize_output(last_ai_content)

    # ── Check 4: Confidence scoring ──
    confidence = 0.8  # default
    if is_hallucination:
        confidence = 0.2
    elif state.get("completed_tool_calls"):
        # Tool-backed answers are more reliable
        confidence = 0.9
        # Penalty for tool errors
        errors = [t for t in state.get("completed_tool_calls", []) if t.status == "error"]
        if errors:
            confidence -= 0.1 * len(errors)
    elif complexity == QueryComplexity.SIMPLE:
        confidence = 0.95  # Simple greetings don't need tools

    # ── Decision: replan or proceed ──
    needs_replanning = is_hallucination and iteration < config.max_iterations - 1

    if needs_replanning:
        # Inject a correction hint into messages
        correction_msg = HumanMessage(
            content="[系统提示] 请使用工具查询实际数据后再回答，不要编造数据。"
        )
        return {
            "messages": [correction_msg],
            "reflection": "检测到可能的幻觉回复，已触发自我修正。",
            "is_hallucination": True,
            "needs_replanning": True,
            "confidence_score": confidence,
            "current_phase": AgentPhase.PLANNING,
            "thinking_steps": [ThinkingStep(
                phase=AgentPhase.REFLECTING.value,
                content="⚠️ 检测到潜在幻觉，触发自我修正循环",
            )],
        }

    return {
        "reflection": "回复质量验证通过" if not is_hallucination else "存在风险但已达最大迭代次数",
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
    Terminal node: finalize the response, apply sanitization, emit final thinking step.
    """
    final_response = state.get("final_response", "")
    config: AgentConfig = state["config"]

    # If no final response yet, extract from last AI message
    if not final_response:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                final_response = msg.content
                break

    # Apply output sanitization
    if final_response:
        is_safe, violations = scan_content(final_response)
        if not is_safe:
            final_response = sanitize_output(final_response)

    confidence = state.get("confidence_score", 0.8)
    thinking_step = ThinkingStep(
        phase=AgentPhase.RESPONDING.value,
        content=f"最终回复已生成 (置信度: {confidence:.0%})",
    )

    return {
        "final_response": final_response or "抱歉，我暂时无法处理这个请求。请稍后重试。",
        "current_phase": AgentPhase.DONE,
        "thinking_steps": [thinking_step],
    }
"""