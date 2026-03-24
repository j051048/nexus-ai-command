"""
WBS Task Decomposition Node — breaks complex marketing requests into structured sub-tasks.

This node is invoked when the router identifies a multi-agent orchestration scenario.
It uses the LLM to produce a WBS (Work Breakdown Structure) in JSON format, where
each sub-task is assigned to a specific agent role.
"""

import json
import logging
import time
import uuid
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.node_helpers import _get_langfuse_callbacks, _get_trace_context
from app.agent.state import (
    AgentConfig,
    AgentPhase,
    AgentState,
    ThinkingStep,
)

logger = logging.getLogger(__name__)


# ─── #14: WBS Quality Validation ────────────────────────────────────────────

_KNOWN_AGENT_CODES = {
    "director_agent", "content_agent", "design_agent", "media_agent",
    "clue_agent", "sales_agent", "synergy_agent", "operation_agent",
    "pr_agent", "compliance_agent",
}


def _validate_wbs(wbs: dict) -> list[str]:
    """
    #14: Validate WBS structure quality. Returns list of warning strings.
    Non-blocking: warnings are logged but never prevent execution.
    """
    warnings = []
    sub_tasks = wbs.get("sub_tasks", [])
    n = len(sub_tasks)

    # 1. Self-reference and invalid dependency check
    for i, task in enumerate(sub_tasks):
        deps = task.get("dependencies", [])
        if i in deps:
            warnings.append(f"子任务[{i}] '{task.get('title', '')}' 存在自引用依赖")
        for d in deps:
            if not isinstance(d, int) or d < 0 or d >= n:
                warnings.append(f"子任务[{i}] 依赖索引 {d} 超出范围(0~{n-1})")

    # 2. Cycle detection via topological sort (Kahn's algorithm)
    in_degree = [0] * n
    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    for i, task in enumerate(sub_tasks):
        for d in task.get("dependencies", []):
            if isinstance(d, int) and 0 <= d < n:
                adj[d].append(i)
                in_degree[i] += 1
    queue = [i for i in range(n) if in_degree[i] == 0]
    visited = 0
    while queue:
        node = queue.pop(0)
        visited += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    if visited < n:
        warnings.append(f"WBS依赖图存在循环: 仅 {visited}/{n} 个任务可拓扑排序")

    # 3. Complex tasks should have director_agent for integration
    if n >= 4:
        has_director = any(t.get("agent_code") == "director_agent" for t in sub_tasks)
        if not has_director:
            warnings.append("复杂WBS(≥4子任务)缺少 director_agent 整合任务")

    # 4. Unknown agent codes
    for i, task in enumerate(sub_tasks):
        code = task.get("agent_code", "")
        if code and code not in _KNOWN_AGENT_CODES:
            warnings.append(f"子任务[{i}] 使用未知 agent_code: {code}")

    return warnings


# ─── WBS Prompt Template ─────────────────────────────────────────────────────

_WBS_SYSTEM_PROMPT = """你是一个任务拆解专家。你的职责是将用户的复杂业务需求拆解为结构化的子任务列表。

## 可用的Agent角色及其能力
- director_agent: 总监，负责整体策略规划和方案整合
- content_agent: 内容创作，负责白皮书、案例文章、SEO内容、社交媒体文案
- design_agent: 视觉设计，负责品牌视觉、宣传物料、展会设计方案
- media_agent: 媒介投放，负责广告投放策略、渠道分析、预算分配
- clue_agent: 线索获客，负责线索获取、评分、渠道归因
- sales_agent: 销售赋能，负责话术、Battlecard、报价策略、竞品对比、标书
- synergy_agent: 协同管理，负责跨部门需求传递、项目协调、任务分配、排班、日程安排
- operation_agent: 运营管理，负责社群运营、会员管理、客户旅程、数据分析
- pr_agent: 舆情口碑，负责品牌舆情监控、危机公关
- compliance_agent: 合规校验，负责广告法合规、内容审核、费用合规检查

## 输出格式要求
请严格输出以下JSON格式（不要包含markdown代码块标记）：
{
  "title": "主任务标题",
  "summary": "需求摘要（1-2句话）",
  "sub_tasks": [
    {
      "title": "子任务标题",
      "agent_code": "对应的agent_code",
      "description": "子任务详细描述，包含输入要求和预期输出",
      "dependencies": [],
      "priority": 1
    }
  ]
}

## 拆解原则
1. 每个子任务只分配给一个Agent
2. dependencies数组包含该任务依赖的其他子任务的索引（0-based）
3. priority: 1(最高)-5(最低)
4. 子任务数量控制在2-8个之间，不宜过多
5. 如果需求涉及合规敏感内容，必须包含compliance_agent的审核任务
6. 并行任务尽量同时执行以提高效率
7. 最终整合任务通常交给director_agent
"""


async def wbs_decompose_node(state: AgentState) -> dict:
    """
    LangGraph node: Decompose a complex request into sub-tasks using WBS methodology.

    Reads the user's latest message, calls the LLM with the WBS system prompt,
    parses the JSON output, and stores the structure in state.

    Returns state updates:
        - wbs_structure: The parsed WBS JSON dict
        - main_task_id: A unique ID for this decomposition
        - thinking_steps: UI progress indicators
    """
    config: AgentConfig = state["config"]
    messages = state.get("messages", [])

    # Extract the last user message
    last_user_msg = ""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_msg = msg.content
            break
        elif isinstance(msg, dict) and msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    if not last_user_msg:
        return {
            "error": "WBS拆解失败: 未找到用户消息",
            "current_phase": AgentPhase.ERROR,
        }

    thinking_step = ThinkingStep(
        phase="wbs_decompose",
        content="正在将复杂需求拆解为可执行的子任务...",
    )

    # Build LLM messages
    llm_messages = [
        SystemMessage(content=_WBS_SYSTEM_PROMPT),
        HumanMessage(content=f"请拆解以下业务需求:\n\n{last_user_msg}"),
    ]

    # Use the high-tier model for task decomposition
    model = config.model  # Use the main model for complex decomposition

    # Resolve model via LLM gateway
    resolved = None
    try:
        from app.services.llm_helpers import resolve_model_config

        org_id = config.org_id or "default"
        scene_code = state.get("scene_code", "")
        agent_code = state.get("agent_code", "")
        resolved = await resolve_model_config(org_id, scene_code, agent_code)
    except Exception:
        logger.debug("LLM gateway model config unavailable in wbs_node, using default")

    if resolved:
        llm = ChatOpenAI(
            model=resolved.get("model", model),
            api_key=resolved.get("api_key", config.api_key),
            base_url=resolved.get("base_url", config.base_url),
            temperature=0.3,
            timeout=resolved.get("timeout", 60.0),
            callbacks=_get_langfuse_callbacks(**_get_trace_context(config), tags=["wbs"]),
        )
    else:
        llm = ChatOpenAI(
            model=model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=0.3,
            timeout=60.0,
            callbacks=_get_langfuse_callbacks(**_get_trace_context(config), tags=["wbs"]),
        )

    try:
        start_time = time.time()
        ai_msg = await llm.ainvoke(llm_messages)
        duration_ms = int((time.time() - start_time) * 1000)

        content = ai_msg.content or ""

        # Parse JSON from LLM response (handle potential markdown code blocks)
        json_str = content.strip()
        if json_str.startswith("```"):
            # Strip markdown code block
            lines = json_str.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```") and not in_block:
                    in_block = True
                    continue
                elif line.strip().startswith("```") and in_block:
                    break
                elif in_block:
                    json_lines.append(line)
            json_str = "\n".join(json_lines)

        wbs_structure = json.loads(json_str)

        # Validate structure
        if "sub_tasks" not in wbs_structure or not wbs_structure["sub_tasks"]:
            raise ValueError("WBS结构缺少sub_tasks字段或为空")

        # Assign IDs to sub-tasks
        main_task_id = str(uuid.uuid4())
        for i, task in enumerate(wbs_structure["sub_tasks"]):
            task["sub_task_id"] = f"{main_task_id}_sub_{i}"
            task["status"] = "pending"
            # Validate agent_code
            if "agent_code" not in task:
                task["agent_code"] = "director_agent"

        task_count = len(wbs_structure["sub_tasks"])

        # #14: WBS quality validation (non-blocking)
        wbs_warnings = _validate_wbs(wbs_structure)
        if wbs_warnings:
            logger.warning(f"[WBS] Validation warnings: {wbs_warnings}")

        task_summary = ", ".join(
            f"{t.get('agent_code', '?')}:{t.get('title', '?')}" for t in wbs_structure["sub_tasks"]
        )

        # Track token usage
        usage = ai_msg.response_metadata.get("token_usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        logger.info(f"[WBS] Decomposed into {task_count} sub-tasks in {duration_ms}ms: {task_summary}")

        # ── Persist WBS to vmd_main_task / vmd_sub_task ──────────────
        db_task_id = None
        try:
            from app.core.database import supabase as admin

            if admin:
                org_id = config.org_id or "default"
                user_id = config.user_id or ""
                date_part = datetime.now(UTC).strftime("%Y%m%d")
                task_code = f"VMD-{date_part}-{uuid.uuid4().hex[:6].upper()}"

                main_record = {
                    "tenant_id": org_id,
                    "task_code": task_code,
                    "title": wbs_structure.get("title", "WBS任务"),
                    "description": wbs_structure.get("summary", last_user_msg[:500]),
                    "scene_code": state.get("scene_code", "task_decompose"),
                    "priority": "medium",
                    "status": "planning",
                    "user_id": user_id,
                    "wbs_structure": wbs_structure,
                }

                res = await admin.table("vmd_main_task").insert(main_record).execute()
                db_task_id = res.data[0]["id"] if res.data else None

                if db_task_id:
                    for i, st in enumerate(wbs_structure.get("sub_tasks", [])):
                        sub_record = {
                            "main_task_id": db_task_id,
                            "tenant_id": org_id,
                            "title": st.get("title", "未命名子任务"),
                            "agent_code": st.get("agent_code", "director_agent"),
                            "description": st.get("description", ""),
                            "sort_order": i + 1,
                            "status": "todo",
                        }
                        await admin.table("vmd_sub_task").insert(sub_record).execute()

                    logger.info(f"[WBS] Persisted to DB: main_task={db_task_id}, {task_count} sub-tasks")
        except Exception as e:
            logger.warning(f"[WBS] DB persistence failed (non-blocking): {e}")

        return {
            "wbs_structure": wbs_structure,
            "main_task_id": db_task_id or main_task_id,
            "current_phase": AgentPhase.EXECUTING,
            "thinking_steps": [
                thinking_step,
                ThinkingStep(
                    phase="wbs_decompose",
                    content=f"任务拆解完成: {wbs_structure.get('title', '未命名')} → {task_count}个子任务",
                    duration_ms=duration_ms,
                ),
            ] + ([ThinkingStep(
                phase="wbs_decompose",
                content=f"⚠️ WBS校验警告: {'; '.join(wbs_warnings)}",
            )] if wbs_warnings else []),
            "total_input_tokens": state.get("total_input_tokens", 0) + input_tokens,
            "total_output_tokens": state.get("total_output_tokens", 0) + output_tokens,
        }

    except json.JSONDecodeError as e:
        logger.error(f"[WBS] Failed to parse LLM output as JSON: {e}")
        return {
            "error": f"WBS拆解失败: LLM输出格式错误 ({str(e)[:100]})",
            "current_phase": AgentPhase.ERROR,
            "thinking_steps": [
                ThinkingStep(
                    phase="wbs_decompose",
                    content="WBS拆解失败: 无法解析任务结构",
                )
            ],
        }
    except Exception as e:
        logger.error(f"[WBS] Decomposition failed: {e}")
        return {
            "error": f"WBS拆解失败: {str(e)[:200]}",
            "current_phase": AgentPhase.ERROR,
            "thinking_steps": [
                ThinkingStep(
                    phase="wbs_decompose",
                    content=f"WBS拆解异常: {str(e)[:100]}",
                )
            ],
        }
