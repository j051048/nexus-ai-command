"""
Multi-Agent Orchestration Node — executes WBS sub-tasks by delegating to role-specific agents.

This node reads the wbs_structure from state, then for each sub-task:
1. Loads the role config (system prompt + tool whitelist) for the assigned agent
2. Builds a mini agent context with role-specific prompts
3. Executes a plan+execute+reflect cycle for that sub-task
4. Collects and aggregates all results
"""

from __future__ import annotations

import asyncio
import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

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


async def orchestrate_node(state: AgentState) -> dict:
    """
    LangGraph node: Execute WBS sub-tasks by delegating to appropriate agent roles.

    For each sub-task (respecting dependency ordering):
      1. Load the role config for the sub_task's agent_code
      2. Build messages with the role's system_prompt
      3. Call LLM with role-specific tool schemas
      4. If tools are called, execute them
      5. Collect the result text

    After all sub-tasks complete, aggregate results into delegation_results
    and produce a final integration prompt for the respond node.

    Returns state updates:
        - delegation_results: list of sub-task result dicts
        - final_response: integrated response from all sub-agents
        - thinking_steps: progress indicators
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
    completed_context = {}  # agent_code -> result text (for dependent tasks)
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

        async def _run_task_with_semaphore(task_idx: int) -> dict:
            """Execute a single sub-task with concurrency control."""
            async with semaphore:
                task = sub_tasks[task_idx]
                agent_code = task.get("agent_code", "director_agent")
                task_title = task.get("title", f"子任务{task_idx + 1}")
                task_description = task.get("description", "")
                sub_task_id = task.get("sub_task_id", f"sub_{task_idx}")

                try:
                    result, tokens_in, tokens_out = await _execute_sub_task(
                        config=config,
                        agent_code=agent_code,
                        task_title=task_title,
                        task_description=task_description,
                        dependencies=task.get("dependencies", []),
                        completed_context=completed_context,
                        original_messages=state.get("messages", []),
                    )

                    return {
                        "task_idx": task_idx,
                        "sub_task_id": sub_task_id,
                        "agent_code": agent_code,
                        "title": task_title,
                        "status": "completed",
                        "result": result,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                    }
                except Exception as e:
                    logger.error(f"[Orchestrate] Sub-task {task_idx} ({agent_code}) failed: {e}")
                    return {
                        "task_idx": task_idx,
                        "sub_task_id": sub_task_id,
                        "agent_code": agent_code,
                        "title": task_title,
                        "status": "failed",
                        "result": f"执行失败: {str(e)[:200]}",
                        "tokens_in": 0,
                        "tokens_out": 0,
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
            total_input_tokens += lr["tokens_in"]
            total_output_tokens += lr["tokens_out"]

            delegation_results.append({
                "sub_task_id": lr["sub_task_id"],
                "agent_code": lr["agent_code"],
                "title": lr["title"],
                "status": lr["status"],
                "result": lr["result"],
            })

            # Store result for dependent tasks in subsequent layers
            completed_context[f"task_{task_idx}"] = lr["result"]
            completed_context[lr["agent_code"]] = lr["result"]

            status_label = "完成" if lr["status"] == "completed" else "失败"
            thinking_steps.append(
                ThinkingStep(
                    phase="orchestrate",
                    content=f"[{task_idx + 1}/{total_tasks}] {lr['agent_code']} {status_label}: {lr['title']}",
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
    )

    thinking_steps.append(
        ThinkingStep(
            phase="orchestrate",
            content=f"多Agent协同完成: {len([r for r in delegation_results if r['status'] == 'completed'])}/{total_tasks} 子任务成功",
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


async def _execute_sub_task(
    config: AgentConfig,
    agent_code: str,
    task_title: str,
    task_description: str,
    dependencies: list[int],
    completed_context: dict[str, str],
    original_messages: list,
) -> tuple[str, int, int]:
    """
    Execute a single sub-task using the role-specific agent config.

    Returns:
        (result_text, input_tokens, output_tokens)
    """
    # 1. Load role config
    role_config = get_role_config_sync(agent_code)

    # 2. Build messages
    system_prompt = role_config.system_prompt

    # Inject dependency context
    dep_context = ""
    if dependencies:
        dep_parts = []
        for dep_idx in dependencies:
            dep_key = f"task_{dep_idx}"
            if dep_key in completed_context:
                dep_parts.append(f"[前置任务{dep_idx + 1}的结果]:\n{completed_context[dep_key][:1500]}")
        if dep_parts:
            dep_context = "\n\n".join(dep_parts)

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

    # 4. Choose model based on role tier
    model = config.model if role_config.recommended_model_tier == "high" else config.mini_model

    # Resolve model via LLM gateway
    resolved = None
    try:
        from app.services.llm_helpers import resolve_model_config

        org_id = config.org_id or "default"
        resolved = await resolve_model_config(org_id, "", agent_code)
    except Exception:
        pass

    if resolved:
        llm = ChatOpenAI(
            model=resolved.get("model", model),
            api_key=resolved.get("api_key", config.api_key),
            base_url=resolved.get("base_url", config.base_url),
            temperature=resolved.get("temperature", config.temperature),
            timeout=resolved.get("timeout", 60.0),
        )
    else:
        llm = ChatOpenAI(
            model=model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            timeout=60.0,
        )

    llm_with_tools = llm.bind_tools(tool_schemas) if tool_schemas else llm

    # 5. Execute (with one tool-calling round)
    total_in = 0
    total_out = 0

    start = time.time()
    ai_msg = await llm_with_tools.ainvoke(messages)
    duration = int((time.time() - start) * 1000)

    usage = ai_msg.response_metadata.get("token_usage", {})
    total_in += usage.get("prompt_tokens", 0)
    total_out += usage.get("completion_tokens", 0)

    # If the LLM wants to call tools, execute them
    if ai_msg.tool_calls:
        messages.append(ai_msg)  # Add AI message with tool_calls to history

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

        # Call LLM again to synthesize tool results
        ai_msg2 = await llm.ainvoke(messages)
        usage2 = ai_msg2.response_metadata.get("token_usage", {})
        total_in += usage2.get("prompt_tokens", 0)
        total_out += usage2.get("completion_tokens", 0)
        result_text = ai_msg2.content or ""
    else:
        result_text = ai_msg.content or ""

    logger.info(
        f"[Orchestrate] Sub-task {agent_code}:{task_title} completed in {duration}ms "
        f"(tools={'yes' if ai_msg.tool_calls else 'no'})"
    )

    return result_text, total_in, total_out


async def _run_single_tool(tool_name: str, tool_args: dict, config: AgentConfig) -> str:
    """Execute a single tool call and return result as string."""
    import asyncio

    tool = get_tool(tool_name)
    if not tool:
        return f"Error: Tool '{tool_name}' not found."

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
            timeout=config.tool_timeout,
        )
        return str(result)
    except Exception as e:
        logger.warning(f"[Orchestrate] Tool {tool_name} failed: {e}")
        return f"Error: {str(e)[:200]}"


# ─── Result Integration ──────────────────────────────────────────────────────


async def _integrate_results(
    config: AgentConfig,
    wbs_title: str,
    delegation_results: list[dict],
    original_messages: list,
) -> str:
    """
    Use the director agent to integrate all sub-task results into a coherent response.
    """
    # Extract original user query
    original_query = ""
    for msg in reversed(original_messages):
        if hasattr(msg, "type") and msg.type == "human":
            original_query = msg.content
            break

    # Build integration prompt
    results_text = ""
    for r in delegation_results:
        status_icon = "done" if r["status"] == "completed" else "failed"
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
5. 如有子任务失败，说明影响和替代方案
6. 输出格式使用markdown，包含清晰的标题层级
"""

    # Resolve model via LLM gateway for integration step
    resolved = None
    try:
        from app.services.llm_helpers import resolve_model_config

        org_id = config.org_id or "default"
        resolved = await resolve_model_config(org_id)
    except Exception:
        pass

    if resolved:
        llm = ChatOpenAI(
            model=resolved.get("model", config.model),
            api_key=resolved.get("api_key", config.api_key),
            base_url=resolved.get("base_url", config.base_url),
            temperature=0.5,
            timeout=resolved.get("timeout", 90.0),
        )
    else:
        llm = ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=0.5,
            timeout=90.0,
        )

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
