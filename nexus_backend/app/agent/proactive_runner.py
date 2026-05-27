"""
Proactive Agent Runner — invokes the AI agent pipeline without an HTTP request context.

Used by AutoTriggerService and EventBus handlers to run the agent
for background tasks like report generation, data analysis, and proactive notifications.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.agent.graph import get_agent_graph
from app.agent.state import (
    CURRENT_SCHEMA_VERSION,
    AgentConfig,
    AgentPhase,
    QueryComplexity,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

_agent_graph = get_agent_graph()


async def run_proactive_agent(
    prompt: str,
    user_id: str,
    org_id: str | None = None,
    agent_name: str = "proactive_agent",
    scene_code: str = "",
    timeout: float = 120.0,
) -> dict[str, Any]:
    """
    Run the agent graph to completion for a background/proactive task.

    Unlike the SSE streaming path, this collects the full result synchronously
    and returns it as a dict — suitable for trigger handlers and event processors.

    Returns:
        {
            "success": bool,
            "response": str,       # The final agent response text
            "thinking_steps": int,  # Number of thinking steps
            "tokens": {"input": int, "output": int},
        }
    """
    agent_config = AgentConfig(
        user_id=user_id,
        session_id="default",
        agent_name=agent_name,
        api_key=settings.OPENAI_API_KEY or "",
        base_url=settings.AI_BASE_URL or "https://api.openai.com/v1",
        model=settings.AI_DEFAULT_MODEL or "deepseek-v4-flash",
        mini_model=settings.AI_MINI_MODEL or "deepseek-v4-flash",
        system_confirmed=True,
        user_role="system",
        org_id=org_id,
        max_iterations=3,
        tool_timeout=30,
        gather_timeout=60,
        enable_rag_inject=False,
        reflect_use_llm=False,
    )

    from langchain_core.messages import HumanMessage, SystemMessage

    now_str = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

    # 注入用户记忆，让主动任务结果更个性化
    memory_ctx = ""
    try:
        from app.core.database import supabase as db_client
        from app.services.conversation_memory_service import conversation_memory_service

        memory_ctx = await conversation_memory_service.build_memory_context(
            user_id=user_id,
            current_query=prompt,
            db=db_client,
        )
    except Exception as mem_err:
        logger.warning("[ProactiveRunner] Memory injection skipped: %s", mem_err)

    system_parts = [
        "你是 Nexus AI 系统的智能助手，正在为用户执行后台任务。请根据指令完成任务并给出简洁、友好的结论。",
        f"\n当前时间：{now_str}",
    ]
    if memory_ctx:
        system_parts.append(f"\n{memory_ctx}")

    # PII sanitization before sending to LLM
    from app.services.content_moderation import sanitize_pii_for_llm

    prompt = sanitize_pii_for_llm(prompt)

    initial_state = {
        "messages": [
            SystemMessage(content="\n".join(system_parts)),
            HumanMessage(content=prompt),
        ],
        "current_phase": AgentPhase.ROUTING,
        "iteration": 0,
        "complexity": QueryComplexity.COMPLEX,
        "selected_model": agent_config.model,
        "intent_summary": "",
        "plan": "",
        "requires_tools": False,
        "pending_tool_calls": [],
        "completed_tool_calls": [],
        "reflection": "",
        "is_hallucination": False,
        "needs_replanning": False,
        "confidence_score": 0.0,
        "final_response": "",
        "thinking_steps": [],
        "config": agent_config,
        "error": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "rag_context": "",
        "rag_sources": [],
        "error_recovery_attempted": False,
        "error_recovery_level": 0,
        "agent_code": "",
        "scene_code": scene_code,
        "main_task_id": None,
        "sub_task_id": None,
        "parent_agent_code": None,
        "delegation_results": [],
        "wbs_structure": None,
        "_schema_version": CURRENT_SCHEMA_VERSION,
    }

    try:
        final_state = await asyncio.wait_for(
            _agent_graph.run(
                initial_state, thread_id=f"proactive_{agent_name}_{user_id}"
            ),
            timeout=timeout,
        )

        response = final_state.get("final_response", "")
        if not response:
            from langchain_core.messages import AIMessage

            for msg in reversed(final_state.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content:
                    response = msg.content
                    break

        return {
            "success": True,
            "response": response or "分析完成，但未生成有效输出。",
            "thinking_steps": len(final_state.get("thinking_steps", [])),
            "tokens": {
                "input": final_state.get("total_input_tokens", 0),
                "output": final_state.get("total_output_tokens", 0),
            },
        }

    except TimeoutError:
        logger.error(
            f"[ProactiveRunner] Agent timed out after {timeout}s for user {user_id}"
        )
        return {
            "success": False,
            "response": "后台任务执行超时",
            "thinking_steps": 0,
            "tokens": {"input": 0, "output": 0},
        }
    except Exception as e:
        logger.error(f"[ProactiveRunner] Agent execution failed: {e}", exc_info=True)
        return {
            "success": False,
            "response": f"后台任务执行失败: {str(e)[:200]}",
            "thinking_steps": 0,
            "tokens": {"input": 0, "output": 0},
        }
