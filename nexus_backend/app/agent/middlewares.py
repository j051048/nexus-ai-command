"""
LangGraph 中间件链架构

参考 DeerFlow 的设计，通过节点链实现横切关注点的分离：
- 租户上下文注入
- 记忆管理
- 工具调用审计
- Token 限制检查

每个中间件是一个独立的节点函数，可插拔、可测试。
"""

import logging
import time
from typing import Any

from app.agent.state import AgentState

logger = logging.getLogger(__name__)


# ─── 中间件节点 ───────────────────────────────────────────────────────────


async def tenant_context_middleware(state: AgentState) -> dict[str, Any]:
    """
    租户上下文中间件

    注入租户信息到 state，确保所有后续节点都能访问租户上下文
    """
    config = state.get("config")
    if not config:
        return {}

    # 注入租户上下文（如果尚未注入）
    if not state.get("_tenant_context_injected"):
        logger.debug(f"[Middleware] Injecting tenant context: org_id={config.org_id}")
        return {
            "_tenant_context_injected": True,
            "_tenant_org_id": config.org_id,
            "_tenant_user_id": config.user_id,
        }

    return {}


async def memory_inject_middleware(state: AgentState) -> dict[str, Any]:
    """
    记忆注入中间件

    在 Agent 执行前注入相关记忆到上下文
    """
    if state.get("_memory_injected"):
        return {}

    config = state.get("config")
    if not config or not config.org_id:
        return {"_memory_injected": True}

    try:
        from app.services.conversation_memory_service import conversation_memory_service

        # 获取最后一条用户消息
        messages = state.get("messages", [])
        user_message = ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                user_message = msg.content
                break

        if user_message:
            # 使用 build_memory_context 搜索相关记忆
            memory_context = await conversation_memory_service.build_memory_context(
                user_id=config.user_id,
                current_query=user_message,
            )

            if memory_context:
                logger.debug(f"[Middleware] Injected memory context ({len(memory_context)} chars)")
                return {
                    "_memory_injected": True,
                    "_injected_memories": [memory_context],
                }

    except Exception as e:
        logger.error(f"[Middleware] Memory injection failed: {e}")

    return {"_memory_injected": True}


async def token_limit_middleware(state: AgentState) -> dict[str, Any]:
    """
    Token 限制中间件

    检查累计 token 使用，防止超出预算
    """
    config = state.get("config")
    if not config:
        return {}

    total_tokens = state.get("total_input_tokens", 0) + state.get("total_output_tokens", 0)
    max_tokens = getattr(config, "max_total_tokens", 100000)

    if total_tokens > max_tokens * 0.9:
        logger.warning(f"[Middleware] Token budget near limit: {total_tokens}/{max_tokens}")
        return {"_token_warning": True}

    if total_tokens > max_tokens:
        logger.error(f"[Middleware] Token budget exceeded: {total_tokens}/{max_tokens}")
        return {
            "error": "TOKEN_LIMIT_EXCEEDED",
            "final_response": f"对话已达到 token 限制（{max_tokens}），请开始新的对话。",
        }

    return {}


async def audit_log_middleware(state: AgentState) -> dict[str, Any]:
    """
    审计日志中间件

    记录工具调用和关键操作
    """
    completed_tools = state.get("completed_tool_calls", [])
    if not completed_tools or state.get("_last_audit_count", 0) >= len(completed_tools):
        return {}

    config = state.get("config")
    if not config:
        return {}

    # 记录新的工具调用
    new_tools = completed_tools[state.get("_last_audit_count", 0):]
    for tool_call in new_tools:
        tool_name = getattr(tool_call, "tool_name", None) or tool_call.get("tool_name", "unknown")
        status = getattr(tool_call, "status", None) or tool_call.get("status", "unknown")
        logger.info(
            f"[Audit] org={config.org_id} user={config.user_id} "
            f"tool={tool_name} status={status}"
        )

    return {"_last_audit_count": len(completed_tools)}


async def memory_update_middleware(state: AgentState) -> dict[str, Any]:
    """
    记忆更新中间件

    在 Agent 执行后更新记忆
    """
    if state.get("_memory_updated"):
        return {}

    config = state.get("config")
    final_response = state.get("final_response")

    if not config or not final_response:
        return {}

    try:
        from app.agent.memory import persist_result

        messages = state.get("messages", [])
        # 获取最后一条用户消息
        user_message = ""
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "human":
                user_message = msg.content
                break

        if user_message:
            # 异步保存记忆（不阻塞响应）
            import asyncio
            asyncio.create_task(
                persist_result(
                    user_id=config.user_id,
                    session_id=getattr(config, "session_id", ""),
                    user_message=user_message,
                    assistant_response=final_response,
                    org_id=config.org_id,
                )
            )
            logger.debug("[Middleware] Memory update scheduled")

    except Exception as e:
        logger.error(f"[Middleware] Memory update failed: {e}")

    return {"_memory_updated": True}


