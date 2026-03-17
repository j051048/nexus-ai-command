"""
Multi-Agent Orchestration Node — executes WBS sub-tasks by delegating to role-specific agents.

This node reads the wbs_structure from state, then for each sub-task:
1. Loads the role config (system prompt + tool whitelist) for the assigned agent
2. Builds a mini agent context with role-specific prompts
3. Executes a multi-round plan+execute cycle for that sub-task (P0-1)
4. Retries on failure with degradation (P0-2)
5. Dynamically adjusts remaining tasks if a layer fails badly (P1-4)
6. Collects and aggregates all results via SharedBlackboard (P2-10)
"""

import asyncio
import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.agent.blackboard import SharedBlackboard, TaskResult
from app.agent.node_helpers import _get_langfuse_callbacks
from app.agent.roles.registry import get_role_config_sync
from app.agent.state import (
    AgentConfig,
    AgentPhase,
    AgentState,
    ThinkingStep,
)
from app.tools import get_tool

logger = logging.getLogger(__name__)

# Maximum sub-tasks to execute in one orchestration pass
_MAX_SUB_TASKS = 8
# Maximum concurrent LLM calls per layer (rate-limit guard)
_MAX_CONCURRENCY = 4
# P0-1: Maximum tool-calling rounds per sub-task
_MAX_SUB_TASK_TOOL_ROUNDS = 3
# P1-4: Failure rate threshold to trigger dynamic replanning
_REPLAN_FAILURE_THRESHOLD = 0.5
# Known long-running tools that need extended timeout
_LONG_RUNNING_TOOLS = {
    "generate_product_manual",
    "generate_whitepaper",
    "generate_bid_document",
    "analyze_contract",
    "strategy_simulation",
    "generate_market_research",
}


# ─── P2-9: Unified LLM factory for orchestrator ─────────────────────────────


async def _create_orchestrator_llm(
    config: AgentConfig,
    agent_code: str = "",
    use_mini: bool = False,
    temperature: float = 0.5,
    timeout: float = 60.0,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance, resolving via LLM Gateway when available.

    This replaces 7+ duplicate resolve+ChatOpenAI patterns throughout the
    orchestrator module.
    """
    resolved = None
    try:
        from app.services.llm_helpers import resolve_model_config

        org_id = config.org_id or "default"
        resolved = await resolve_model_config(org_id, "", agent_code)
    except Exception:
        logger.debug("LLM gateway unavailable in orchestrator, using fallback")

    fallback_model = config.mini_model if use_mini else config.model
    if resolved:
        return ChatOpenAI(
            model=resolved.get("model", fallback_model),
            api_key=resolved.get("api_key", config.api_key),
            base_url=resolved.get("base_url", config.base_url),
            temperature=temperature,
            timeout=resolved.get("timeout", timeout),
            callbacks=_get_langfuse_callbacks(),
        )
    return ChatOpenAI(
        model=fallback_model,
        api_key=config.api_key,
        base_url=config.base_url,
        temperature=temperature,
        timeout=timeout,
        callbacks=_get_langfuse_callbacks(),
    )


async def orchestrate_node(state: AgentState) -> dict:
    """
    LangGraph node: Execute WBS sub-tasks by delegating to appropriate agent roles.

    Enhanced with:
    - P0-2: Retry + degradation for failed sub-tasks
    - P1-4: Dynamic replanning when layer failure rate is high
    - P2-9: Unified LLM factory via Gateway
    - P2-10: SharedBlackboard for structured data sharing
    """
    config: AgentConfig = state["config"]
    wbs_structure = state.get("wbs_structure")

    if not wbs_structure or "sub_tasks" not in wbs_structure:
        return {
            "error": "编排失败: 缺少WBS任务结构",
            "current_phase": AgentPhase.ERROR,
        }

    sub_tasks = wbs_structure["sub_tasks"][:_MAX_SUB_TASKS]
    total_tasks = len(sub_tasks)

    thinking_steps = [
        ThinkingStep(
            phase="orchestrate",
            content=f"开始多Agent协同执行: {total_tasks}个子任务",
        )
    ]

    # ── Resolve execution layers (parallelizable groups) ──
    execution_layers = _resolve_execution_layers(sub_tasks)

    delegation_results = []
    # P2-10: Replace completed_context dict with SharedBlackboard
    blackboard = SharedBlackboard()
    total_input_tokens = state.get("total_input_tokens", 0)
    total_output_tokens = state.get("total_output_tokens", 0)

    semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)

    for layer_idx, layer in enumerate(execution_layers):
        layer_size = len(layer)
        if layer_size > 1:
            thinking_steps.append(
                ThinkingStep(
                    phase="orchestrate",
                    content=f"第{layer_idx + 1}层: 并行执行 {layer_size} 个独立子任务",
                )
            )

        # P0-2: Enhanced task runner with retry + degradation
        async def _run_task_with_semaphore(task_idx: int) -> dict:
            """Execute a single sub-task with retry, degradation, and concurrency control."""
            async with semaphore:
                task = sub_tasks[task_idx]
                agent_code = task.get("agent_code", "director_agent")
                task_title = task.get("title", f"子任务{task_idx + 1}")
                task_description = task.get("description", "")
                sub_task_id = task.get("sub_task_id", f"sub_{task_idx}")

                _base_result = {
                    "task_idx": task_idx,
                    "sub_task_id": sub_task_id,
                    "agent_code": agent_code,
                    "title": task_title,
                }

                # Attempt 1: Normal execution
                try:
                    result, tokens_in, tokens_out, tool_calls_data = await _execute_sub_task(
                        config=config,
                        agent_code=agent_code,
                        task_title=task_title,
                        task_description=task_description,
                        dependencies=task.get("dependencies", []),
                        blackboard=blackboard,
                        original_messages=state.get("messages", []),
                    )
                    return {
                        **_base_result,
                        "status": "completed",
                        "result": result,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "tool_calls": tool_calls_data,
                    }
                except Exception as e1:
                    logger.warning(f"[Orchestrate] Sub-task {task_idx} ({agent_code}) first attempt failed: {e1}")

                # Attempt 2: Retry
                try:
                    result, tokens_in, tokens_out, tool_calls_data = await _execute_sub_task(
                        config=config,
                        agent_code=agent_code,
                        task_title=task_title,
                        task_description=task_description,
                        dependencies=task.get("dependencies", []),
                        blackboard=blackboard,
                        original_messages=state.get("messages", []),
                    )
                    return {
                        **_base_result,
                        "status": "completed",
                        "result": result,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "tool_calls": tool_calls_data,
                    }
                except Exception as e2:
                    logger.warning(
                        f"[Orchestrate] Sub-task {task_idx} ({agent_code}) "
                        f"retry failed: {e2}, falling back to degraded mode"
                    )

                # Attempt 3: Degraded (mini_model, no tools)
                try:
                    result, tokens_in, tokens_out, tool_calls_data = await _execute_sub_task_degraded(
                        config=config,
                        task_title=task_title,
                        task_description=task_description,
                        dependencies=task.get("dependencies", []),
                        blackboard=blackboard,
                        original_messages=state.get("messages", []),
                    )
                    return {
                        **_base_result,
                        "status": "degraded",
                        "result": result,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "tool_calls": tool_calls_data,
                    }
                except Exception as e3:
                    logger.error(f"[Orchestrate] Sub-task {task_idx} all attempts exhausted: {e3}")
                    return {
                        **_base_result,
                        "status": "failed",
                        "result": f"执行失败(含重试和降级): {str(e3)[:200]}",
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "tool_calls": [],
                    }

        # Execute all tasks in this layer concurrently
        layer_results = await asyncio.gather(
            *[_run_task_with_semaphore(idx) for idx in layer],
            return_exceptions=True,
        )

        # Aggregate layer results
        for lr in layer_results:
            if isinstance(lr, Exception):
                logger.error(f"[Orchestrate] Unexpected layer error: {lr}")
                continue

            task_idx = lr["task_idx"]
            total_input_tokens += lr.get("tokens_in", 0)
            total_output_tokens += lr.get("tokens_out", 0)

            delegation_results.append(
                {
                    "sub_task_id": lr["sub_task_id"],
                    "agent_code": lr["agent_code"],
                    "title": lr["title"],
                    "status": lr["status"],
                    "result": lr["result"],
                }
            )

            # P2-10: Write result to SharedBlackboard (replaces completed_context)
            await blackboard.write(
                TaskResult(
                    task_idx=task_idx,
                    sub_task_id=lr["sub_task_id"],
                    agent_code=lr["agent_code"],
                    title=lr["title"],
                    status=lr["status"],
                    text=lr["result"],
                    tool_calls=lr.get("tool_calls", []),
                )
            )

            status_labels = {"completed": "完成", "degraded": "降级完成", "failed": "失败"}
            status_label = status_labels.get(lr["status"], lr["status"])
            thinking_steps.append(
                ThinkingStep(
                    phase="orchestrate",
                    content=f"[{task_idx + 1}/{total_tasks}] {lr['agent_code']} {status_label}: {lr['title']}",
                )
            )

        # P1-4: Dynamic replanning — check if layer failure rate is too high
        if layer_idx < len(execution_layers) - 1:
            valid_results = [lr for lr in layer_results if not isinstance(lr, Exception)]
            layer_failed = sum(1 for lr in valid_results if lr["status"] == "failed")
            if valid_results and layer_failed / len(valid_results) > _REPLAN_FAILURE_THRESHOLD:
                thinking_steps.append(
                    ThinkingStep(
                        phase="orchestrate",
                        content=f"第{layer_idx + 1}层有 {layer_failed}/{len(valid_results)} 个任务失败，"
                        f"正在评估后续任务...",
                    )
                )

                remaining_indices = []
                for future_layer in execution_layers[layer_idx + 1 :]:
                    remaining_indices.extend(future_layer)

                if remaining_indices:
                    adjusted = await _check_and_adjust_plan(
                        config=config,
                        sub_tasks=sub_tasks,
                        delegation_results=delegation_results,
                        remaining_indices=remaining_indices,
                        original_messages=state.get("messages", []),
                    )
                    if adjusted:
                        for idx, new_desc in adjusted.items():
                            if idx < len(sub_tasks):
                                sub_tasks[idx]["description"] = new_desc
                        thinking_steps.append(
                            ThinkingStep(
                                phase="orchestrate",
                                content=f"已动态调整 {len(adjusted)} 个后续子任务的策略",
                            )
                        )

    # ── Integrate Results ──
    thinking_steps.append(
        ThinkingStep(
            phase="orchestrate",
            content="所有子任务执行完毕，正在整合结果...",
        )
    )

    integrated_response = await _integrate_results(
        config=config,
        wbs_title=wbs_structure.get("title", "营销方案"),
        delegation_results=delegation_results,
        original_messages=state.get("messages", []),
        blackboard=blackboard,
    )

    completed_count = len([r for r in delegation_results if r["status"] in ("completed", "degraded")])
    thinking_steps.append(
        ThinkingStep(
            phase="orchestrate",
            content=f"多Agent协同完成: {completed_count}/{total_tasks} 子任务成功",
        )
    )

    return {
        "delegation_results": delegation_results,
        "final_response": integrated_response,
        "current_phase": AgentPhase.RESPONDING,
        "thinking_steps": thinking_steps,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
    }


# ─── Sub-task Execution ──────────────────────────────────────────────────────

# P2: Sub-agent context isolation — independent token budget per sub-task
_SUB_TASK_TOKEN_BUDGET = 4000  # max tokens per sub-task before forced synthesis
_RESULT_COMPRESS_THRESHOLD = 1500  # chars — compress result if longer


async def _compress_sub_result(config: AgentConfig, task_title: str, text: str) -> str:
    """Compress a verbose sub-task result into a concise summary using mini_model."""
    try:
        llm = await _create_orchestrator_llm(config, use_mini=True, temperature=0.2, timeout=20.0)
        prompt = (
            f"请将以下子任务「{task_title}」的执行结果精炼为不超过500字的摘要。\n"
            f"保留：关键数据点、结论、数字指标。删除：冗余描述、重复信息、格式装饰。\n\n"
            f"原始结果:\n{text[:3000]}"
        )
        from langchain_core.messages import HumanMessage as _HM, SystemMessage as _SM
        resp = await llm.ainvoke([
            _SM(content="你是信息压缩专家，擅长提炼关键信息。只输出摘要，不加前缀。"),
            _HM(content=prompt),
        ])
        compressed = resp.content or text
        logger.debug(f"[Orchestrate] Compressed result for '{task_title}': {len(text)} -> {len(compressed)} chars")
        return compressed
    except Exception as e:
        logger.warning(f"[Orchestrate] Result compression failed for '{task_title}': {e}")
        return text[:_RESULT_COMPRESS_THRESHOLD] + "..."


async def _execute_sub_task(
    config: AgentConfig,
    agent_code: str,
    task_title: str,
    task_description: str,
    dependencies: list[int],
    blackboard: SharedBlackboard,
    original_messages: list,
) -> tuple[str, int, int, list[dict]]:
    """
    Execute a single sub-task using the role-specific agent config.

    P0-1 Enhancement: Supports multi-round tool calling (up to _MAX_SUB_TASK_TOOL_ROUNDS).
    P2-10 Enhancement: Uses SharedBlackboard for dependency context + collects tool call data.

    Returns:
        (result_text, input_tokens, output_tokens, tool_calls_data)
    """
    # 1. Load role config
    role_config = get_role_config_sync(agent_code)

    # 2. Build messages
    system_prompt = role_config.system_prompt

    # P2-10: Get dependency context from blackboard (replaces manual dict lookup)
    dep_context = blackboard.get_dependency_context(dependencies)

    # Extract original user query for context
    original_query = ""
    for msg in reversed(original_messages):
        if hasattr(msg, "type") and msg.type == "human":
            original_query = msg.content
            break

    user_prompt = f"""## 当前子任务
标题: {task_title}
描述: {task_description}

## 用户原始需求
{original_query[:2000]}
"""

    if dep_context:
        user_prompt += f"\n## 前置任务结果（供参考）\n{dep_context}"

    user_prompt += "\n\n请针对上述子任务给出专业、详细的执行结果。"

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    # 3. Get role-specific tool schemas
    tool_schemas = role_config.get_tool_schemas()

    # 4. P2-9: Create LLM via unified factory
    llm = await _create_orchestrator_llm(config, agent_code=agent_code)
    llm_with_tools = llm.bind_tools(tool_schemas) if tool_schemas else llm

    # 5. P0-1: Multi-round tool calling loop
    total_in = 0
    total_out = 0
    result_text = ""
    # P2-10: Collect tool call data for blackboard
    tool_calls_data: list[dict] = []
    start = time.time()

    for round_idx in range(_MAX_SUB_TASK_TOOL_ROUNDS):
        ai_msg = await llm_with_tools.ainvoke(messages)

        usage = ai_msg.response_metadata.get("token_usage", {})
        total_in += usage.get("prompt_tokens", 0)
        total_out += usage.get("completion_tokens", 0)

        # P2: Token budget check — force synthesis if budget exceeded
        if total_in + total_out >= _SUB_TASK_TOKEN_BUDGET:
            logger.info(
                f"[Orchestrate] Sub-task {agent_code}:{task_title} "
                f"hit token budget ({total_in + total_out}/{_SUB_TASK_TOKEN_BUDGET}), forcing synthesis"
            )
            result_text = ai_msg.content or ""
            if not result_text:
                final_msg = await llm.ainvoke(messages)
                usage2 = final_msg.response_metadata.get("token_usage", {})
                total_in += usage2.get("prompt_tokens", 0)
                total_out += usage2.get("completion_tokens", 0)
                result_text = final_msg.content or ""
            break

        if not ai_msg.tool_calls:
            # No tool calls — LLM has produced final content
            result_text = ai_msg.content or ""
            break

        # Has tool calls → execute and feed results back
        messages.append(ai_msg)

        for tc in ai_msg.tool_calls:
            tool_name = tc.get("name", "unknown")
            tool_args = tc.get("args", {})
            tool_call_id = tc.get("id", "")

            tool_result = await _run_single_tool(tool_name, tool_args, config)
            messages.append(
                ToolMessage(
                    content=tool_result,
                    name=tool_name,
                    tool_call_id=tool_call_id,
                )
            )

            # P2-10: Record tool call data for blackboard
            tool_calls_data.append(
                {
                    "tool_name": tool_name,
                    "args_summary": str(tool_args)[:100],
                    "result_summary": tool_result[:200],
                }
            )

        logger.info(
            f"[Orchestrate] Sub-task {agent_code}:{task_title} "
            f"round {round_idx + 1} completed ({len(ai_msg.tool_calls)} tools)"
        )

        # Last round: force a final synthesis without tools
        if round_idx == _MAX_SUB_TASK_TOOL_ROUNDS - 1:
            final_msg = await llm.ainvoke(messages)
            usage2 = final_msg.response_metadata.get("token_usage", {})
            total_in += usage2.get("prompt_tokens", 0)
            total_out += usage2.get("completion_tokens", 0)
            result_text = final_msg.content or ""
            break
    else:
        # Loop completed normally (all rounds had tool calls)
        if not result_text:
            result_text = ai_msg.content or ""

    duration = int((time.time() - start) * 1000)
    logger.info(f"[Orchestrate] Sub-task {agent_code}:{task_title} completed in {duration}ms")

    # P2: Compress verbose results before returning to blackboard
    if result_text and len(result_text) > _RESULT_COMPRESS_THRESHOLD:
        result_text = await _compress_sub_result(config, task_title, result_text)

    return result_text, total_in, total_out, tool_calls_data


# P0-2: Degraded execution (mini_model, no tools)
async def _execute_sub_task_degraded(
    config: AgentConfig,
    task_title: str,
    task_description: str,
    dependencies: list[int],
    blackboard: SharedBlackboard,
    original_messages: list,
) -> tuple[str, int, int, list[dict]]:
    """Degraded fallback: mini_model, no tools, pure text reasoning."""
    # P2-10: Get dependency context from blackboard
    dep_context = blackboard.get_dependency_context(dependencies, max_chars=2000)

    original_query = ""
    for msg in reversed(original_messages):
        if hasattr(msg, "type") and msg.type == "human":
            original_query = msg.content
            break

    user_prompt = f"""## 当前子任务（降级模式 - 仅基于已有知识回答）
标题: {task_title}
描述: {task_description}

## 用户原始需求
{original_query[:1500]}

注意: 当前为降级模式，无法调用工具。请基于你的专业知识给出最佳回答。
如有数据查询需求，请说明需要哪些数据，但给出基于经验的参考建议。
"""

    if dep_context:
        user_prompt += f"\n## 前置任务结果（供参考）\n{dep_context}"

    messages = [
        SystemMessage(content="你是一位经验丰富的专业顾问。请基于专业知识回答以下问题。"),
        HumanMessage(content=user_prompt),
    ]

    # P2-9: Use unified LLM factory
    llm = await _create_orchestrator_llm(config, use_mini=True, temperature=0.7, timeout=30.0)

    ai_msg = await llm.ainvoke(messages)
    usage = ai_msg.response_metadata.get("token_usage", {})

    result_text = ai_msg.content or ""
    result_text = f"[基于AI分析的参考回答，非实时数据]\n{result_text}"

    return result_text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), []


# P0-1: Enhanced tool execution with retry
async def _run_single_tool(tool_name: str, tool_args: dict, config: AgentConfig) -> str:
    """Execute a single tool call with validation and single retry."""
    tool = get_tool(tool_name)
    if not tool:
        return f"Error: Tool '{tool_name}' not found."

    # Schema Validation
    try:
        await tool.validate(tool_args)
    except Exception as ve:
        logger.warning(f"[Orchestrate] Tool {tool_name} schema validation failed: {ve}")
        try:
            import jsonschema

            if isinstance(ve, jsonschema.ValidationError):
                field_path = " → ".join(str(p) for p in ve.absolute_path) if ve.absolute_path else "(root)"
                return f"参数校验失败 [{tool_name}]: 字段 {field_path} - {ve.message}" + (
                    f" (允许值: {ve.schema['enum']})" if ve.schema and "enum" in ve.schema else ""
                )
        except Exception:
            pass
        return f"参数校验失败 [{tool_name}]: {ve}"

    # Determine timeout
    timeout = config.tool_timeout
    if tool_name in _LONG_RUNNING_TOOLS:
        timeout = max(timeout, 120.0)

    # Execute with single retry
    last_error = None
    for attempt in range(2):
        try:
            result = await asyncio.wait_for(
                tool.run(
                    tool_args,
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
            return str(result)
        except Exception as e:
            last_error = e
            if attempt == 0:
                logger.warning(f"[Orchestrate] Tool {tool_name} attempt 1 failed: {e}, retrying")
                await asyncio.sleep(0.5)

    logger.warning(f"[Orchestrate] Tool {tool_name} failed after 2 attempts: {last_error}")
    return f"Error: {str(last_error)[:200]}"


# ─── P1-4: Dynamic Replanning ────────────────────────────────────────────────


async def _check_and_adjust_plan(
    config: AgentConfig,
    sub_tasks: list[dict],
    delegation_results: list[dict],
    remaining_indices: list[int],
    original_messages: list,
) -> dict[int, str] | None:
    """
    P1-4: Evaluate whether remaining sub-tasks need adjustment based on failures.

    Returns a dict mapping task index -> adjusted description, or None if no adjustment needed.
    """
    failed_summaries = []
    for r in delegation_results:
        if r["status"] == "failed":
            failed_summaries.append(f"- {r['title']} ({r['agent_code']}): {r['result'][:150]}")

    if not failed_summaries:
        return None

    remaining_summaries = []
    for idx in remaining_indices:
        if idx < len(sub_tasks):
            t = sub_tasks[idx]
            remaining_summaries.append(f"- [{idx}] {t.get('title', '?')}: {t.get('description', '')[:100]}")

    prompt = f"""以下子任务已失败:
{chr(10).join(failed_summaries)}

以下子任务尚未执行:
{chr(10).join(remaining_summaries)}

请评估: 失败的子任务是否影响后续任务? 如果影响，请为受影响的任务提供调整后的描述。
注意: 不要创建新任务，只修改现有任务的描述来适配失败情况。

请以JSON格式回答，格式为: {{"adjustments": {{"任务索引": "调整后的描述"}}}}
如果不需要调整，返回: {{"adjustments": {{}}}}
"""

    try:
        # P2-9: Use unified LLM factory
        llm = await _create_orchestrator_llm(config, use_mini=True, temperature=0.3, timeout=30.0)

        ai_msg = await llm.ainvoke(
            [
                SystemMessage(content="你是任务编排专家，负责根据执行情况动态调整任务计划。只返回JSON。"),
                HumanMessage(content=prompt),
            ]
        )

        import json

        content = ai_msg.content or ""
        # Strip markdown code blocks
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        parsed = json.loads(content)
        adjustments = parsed.get("adjustments", {})

        if adjustments:
            return {int(k): v for k, v in adjustments.items() if v}
    except Exception as e:
        logger.warning(f"[Orchestrate] Dynamic replanning failed: {e}")

    return None


# ─── Result Integration ──────────────────────────────────────────────────────


async def _integrate_results(
    config: AgentConfig,
    wbs_title: str,
    delegation_results: list[dict],
    original_messages: list,
    blackboard: SharedBlackboard | None = None,
) -> str:
    """
    Use the director agent to integrate all sub-task results into a coherent response.

    P2-10: Optionally includes tool call data summary from SharedBlackboard.
    """
    # Extract original user query
    original_query = ""
    for msg in reversed(original_messages):
        if hasattr(msg, "type") and msg.type == "human":
            original_query = msg.content
            break

    # Build integration prompt with P0-2 degraded status support
    results_text = ""
    for r in delegation_results:
        status_map = {"completed": "done", "degraded": "degraded", "failed": "failed"}
        status_icon = status_map.get(r["status"], r["status"])
        results_text += f"\n### [{status_icon}] {r['title']} ({r['agent_code']})\n{r['result'][:3000]}\n"

    integration_prompt = f"""## 整合任务

你是市场总监，请将以下各专业Agent的执行结果整合为一份完整、一致的方案。

### 用户原始需求
{original_query[:2000]}

### 主任务: {wbs_title}

### 各子任务执行结果
{results_text}

### 整合要求
1. 将各Agent的输出整合为一份结构清晰的完整方案
2. 消除各部分之间的矛盾和重复
3. 补充必要的衔接内容和整体总结
4. 给出明确的执行建议和优先级
5. 如有子任务失败或降级，说明影响和替代方案
6. 标注为[degraded]的子任务结果仅供参考，应明确说明其数据局限性
7. 输出格式使用markdown，包含清晰的标题层级
"""

    # P2-10: Inject tool data summary from blackboard
    if blackboard:
        tool_summary = blackboard.get_tool_data_summary()
        if tool_summary:
            integration_prompt += f"\n### 工具调用数据摘要\n{tool_summary}\n"

    # P2-9: Use unified LLM factory
    llm = await _create_orchestrator_llm(config, timeout=90.0)

    try:
        ai_msg = await llm.ainvoke(
            [
                SystemMessage(content="你是一位资深市场总监，擅长整合多方信息形成完整方案。"),
                HumanMessage(content=integration_prompt),
            ]
        )
        return ai_msg.content or "整合结果生成失败，请查看各子任务的独立输出。"
    except Exception as e:
        logger.error(f"[Orchestrate] Integration failed: {e}")
        # Fallback: concatenate results
        fallback = f"# {wbs_title}\n\n"
        for r in delegation_results:
            fallback += f"## {r['title']}\n{r['result'][:2000]}\n\n"
        return fallback


# ─── Dependency Resolution ───────────────────────────────────────────────────


def _resolve_execution_order(sub_tasks: list[dict]) -> list[int]:
    """
    Resolve execution order based on task dependencies (simple topological sort).

    Tasks with no dependencies are executed first. Tasks that depend on
    earlier tasks are executed after their dependencies complete.

    Returns a list of task indices in execution order.
    """
    n = len(sub_tasks)
    if n == 0:
        return []

    # Build adjacency list
    in_degree = [0] * n
    dependents = [[] for _ in range(n)]

    for i, task in enumerate(sub_tasks):
        deps = task.get("dependencies", [])
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, int) and 0 <= dep < n:
                    in_degree[i] += 1
                    dependents[dep].append(i)

    # Kahn's algorithm
    queue = [i for i in range(n) if in_degree[i] == 0]
    order = []

    while queue:
        # Sort by priority (lower number = higher priority)
        queue.sort(key=lambda idx: sub_tasks[idx].get("priority", 3))
        current = queue.pop(0)
        order.append(current)

        for dep in dependents[current]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    # If there are cycles, add remaining tasks at the end
    if len(order) < n:
        remaining = [i for i in range(n) if i not in order]
        order.extend(remaining)

    return order


def _resolve_execution_layers(sub_tasks: list[dict]) -> list[list[int]]:
    """
    Resolve execution layers: tasks within the same layer have no mutual
    dependencies and can run in parallel.

    Uses Kahn's algorithm but collects each "wave" of zero-in-degree nodes
    as a single layer instead of flattening into one list.

    Returns a list of layers, each layer being a list of task indices.
    """
    n = len(sub_tasks)
    if n == 0:
        return []

    # Build adjacency
    in_degree = [0] * n
    dependents = [[] for _ in range(n)]

    for i, task in enumerate(sub_tasks):
        deps = task.get("dependencies", [])
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, int) and 0 <= dep < n:
                    in_degree[i] += 1
                    dependents[dep].append(i)

    # Layered Kahn's algorithm
    current_layer = [i for i in range(n) if in_degree[i] == 0]
    layers: list[list[int]] = []
    visited = set()

    while current_layer:
        # Sort within layer by priority
        current_layer.sort(key=lambda idx: sub_tasks[idx].get("priority", 3))
        layers.append(current_layer)
        visited.update(current_layer)

        next_layer = []
        for node in current_layer:
            for dep in dependents[node]:
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    next_layer.append(dep)
        current_layer = next_layer

    # Handle cycles: add remaining as final layer
    if len(visited) < n:
        remaining = [i for i in range(n) if i not in visited]
        layers.append(remaining)

    return layers
