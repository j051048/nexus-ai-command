"""
WBS Task Decomposition Node — breaks complex marketing requests into structured sub-tasks.

This node is invoked when the router identifies a multi-agent orchestration scenario.
It uses the LLM to produce a WBS (Work Breakdown Structure) in JSON format, where
each sub-task is assigned to a specific agent role.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.agent.state import (
    AgentConfig,
    AgentPhase,
    AgentState,
    ThinkingStep,
)

logger = logging.getLogger(__name__)


# ─── WBS Prompt Template ─────────────────────────────────────────────────────

_WBS_SYSTEM_PROMPT = """你是一个任务拆解专家。你的职责是将用户的复杂市场营销需求拆解为结构化的子任务列表。

## 可用的Agent角色及其能力
- director_agent: 市场总监，负责整体策略和方案整合
- content_agent: 内容营销，负责白皮书、案例文章、SEO内容、社交媒体文案
- design_agent: 视觉设计，负责品牌视觉、宣传物料、展会设计方案
- media_agent: 媒介投放，负责广告投放策略、渠道分析、预算分配
- clue_agent: 线索获客，负责线索获取、评分、渠道归因
- sales_agent: 销售赋能，负责话术、Battlecard、报价策略、竞品对比
- synergy_agent: 研产销协同，负责跨部门需求传递和信息同步
- operation_agent: 私域运营，负责社群运营、会员管理、客户旅程
- pr_agent: 舆情口碑，负责品牌舆情监控、危机公关
- compliance_agent: 合规校验，负责广告法合规、内容审核

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
        HumanMessage(content=f"请拆解以下营销需求:\n\n{last_user_msg}"),
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
        pass

    if resolved:
        llm = ChatOpenAI(
            model=resolved.get("model", model),
            api_key=resolved.get("api_key", config.api_key),
            base_url=resolved.get("base_url", config.base_url),
            temperature=0.3,
            timeout=resolved.get("timeout", 60.0),
        )
    else:
        llm = ChatOpenAI(
            model=model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=0.3,
            timeout=60.0,
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
        task_summary = ", ".join(
            f"{t.get('agent_code', '?')}:{t.get('title', '?')}"
            for t in wbs_structure["sub_tasks"]
        )

        # Track token usage
        usage = ai_msg.response_metadata.get("token_usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        logger.info(
            f"[WBS] Decomposed into {task_count} sub-tasks in {duration_ms}ms: {task_summary}"
        )

        return {
            "wbs_structure": wbs_structure,
            "main_task_id": main_task_id,
            "current_phase": AgentPhase.EXECUTING,
            "thinking_steps": [
                thinking_step,
                ThinkingStep(
                    phase="wbs_decompose",
                    content=f"任务拆解完成: {wbs_structure.get('title', '未命名')} → {task_count}个子任务",
                    duration_ms=duration_ms,
                ),
            ],
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
