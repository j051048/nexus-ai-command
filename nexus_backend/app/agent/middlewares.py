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

            updates: dict[str, Any] = {"_memory_injected": True}

            if memory_context:
                logger.debug(f"[Middleware] Injected memory context ({len(memory_context)} chars)")
                updates["_injected_memories"] = [memory_context]

            # P0-6: 技能匹配 — 检索已有技能模板，注入 planning 提示
            try:
                from app.agent.skill_library import skill_library
                from app.core.database import supabase as db_client

                matched = await skill_library.match_skill(
                    user_message=user_message,
                    user_id=config.user_id,
                    org_id=config.org_id or "default",
                    db=db_client,
                )
                if matched:
                    hint = skill_library.skill_to_tool_hints(matched)
                    if hint:
                        existing = updates.get("_injected_memories", [])
                        existing.append(hint)
                        updates["_injected_memories"] = existing
                        updates["_matched_skill"] = matched
                        logger.info(f"[Middleware] Skill matched: {matched.get('intent_pattern', '')[:40]}")
            except Exception as e:
                logger.debug(f"[Middleware] Skill matching skipped: {e}")

            # 工作状态注入 — 轻量摘要（仅计数 + key 名称）
            try:
                from app.agent.working_directory import working_directory

                active_states = await working_directory.list_active(user_id=config.user_id, limit=20)
                if active_states:
                    key_names = ", ".join(s["key"] for s in active_states[:5])
                    if len(active_states) > 5:
                        summary = f"[工作状态] 你有 {len(active_states)} 个进行中的任务状态可用: {key_names} 等"
                    else:
                        summary = f"[工作状态] 你有 {len(active_states)} 个进行中的任务状态可用: {key_names}"
                    existing = updates.get("_injected_memories", [])
                    existing.append(summary)
                    updates["_injected_memories"] = existing
                    logger.debug(f"[Middleware] Working directory: {len(active_states)} active states")
            except Exception as e:
                logger.debug(f"[Middleware] Working directory injection skipped: {e}")

            return updates

    except Exception as e:
        logger.error(f"[Middleware] Memory injection failed: {e}")

    return {"_memory_injected": True}


async def token_limit_middleware(state: AgentState) -> dict[str, Any]:
    """
    Token 限制中间件 (P0 升级版)

    集成 TokenBudgetManager 多维预算检查：
    - 单会话 token 上限
    - 单用户小时 token 上限
    - 单会话费用上限
    - 单租户日/月费用上限
    """
    config = state.get("config")
    if not config:
        return {}

    # 基础 token 数检查 (快速路径)
    total_tokens = state.get("total_input_tokens", 0) + state.get("total_output_tokens", 0)
    max_tokens = getattr(config, "max_total_tokens", 100000)

    if total_tokens > max_tokens:
        logger.error(f"[Middleware] Token budget exceeded: {total_tokens}/{max_tokens}")
        return {
            "error": "TOKEN_LIMIT_EXCEEDED",
            "final_response": f"对话已达到 token 限制（{max_tokens}），请开始新的对话。",
        }

    # P0: 集成 TokenBudgetManager 多维预算检查
    try:
        from app.core.token_budget import BudgetVerdict, token_budget_manager

        session_id = getattr(config, "session_id", "") or "unknown"
        user_id = getattr(config, "user_id", "") or "unknown"
        tenant_id = getattr(config, "org_id", None)

        budget_status = await token_budget_manager.check_budget(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        if budget_status.verdict == BudgetVerdict.EXCEEDED:
            logger.error(f"[Middleware] Budget exceeded: {budget_status.message}")
            return {
                "error": "BUDGET_EXCEEDED",
                "final_response": budget_status.message,
            }

        if budget_status.verdict == BudgetVerdict.WARNING:
            logger.warning(f"[Middleware] Budget warning: {budget_status.message}")
            return {"_token_warning": True, "_budget_warning_message": budget_status.message}

    except Exception as e:
        logger.warning(f"[Middleware] Budget check failed, falling back to basic check: {e}")
        # 降级到基础检查
        if total_tokens > max_tokens * 0.9:
            return {"_token_warning": True}

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
    new_tools = completed_tools[state.get("_last_audit_count", 0) :]
    for tool_call in new_tools:
        tool_name = getattr(tool_call, "tool_name", None) or tool_call.get("tool_name", "unknown")
        status = getattr(tool_call, "status", None) or tool_call.get("status", "unknown")
        logger.info(f"[Audit] org={config.org_id} user={config.user_id} " f"tool={tool_name} status={status}")

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

            # P0-6: 技能提炼 — 成功的多步工具链自动提炼为可复用技能
            completed = state.get("completed_tool_calls", [])
            if len(completed) >= 2:
                try:
                    from app.agent.skill_library import skill_library
                    from app.core.database import supabase as db_client

                    # 转换为 dict 列表
                    tc_dicts = []
                    for tc in completed:
                        tc_dicts.append(
                            {
                                "tool_name": getattr(tc, "tool_name", "")
                                or (tc.get("tool_name", "") if isinstance(tc, dict) else ""),
                                "status": getattr(tc, "status", "")
                                or (tc.get("status", "") if isinstance(tc, dict) else ""),
                                "args": getattr(tc, "args", {}) or (tc.get("args", {}) if isinstance(tc, dict) else {}),
                            }
                        )

                    complexity = state.get("complexity")
                    complexity_str = complexity.value if hasattr(complexity, "value") else str(complexity or "")

                    asyncio.create_task(
                        skill_library.extract_skill(
                            intent_summary=state.get("intent_summary", user_message[:60]),
                            tool_chain=tc_dicts,
                            complexity=complexity_str,
                            user_id=config.user_id,
                            org_id=config.org_id or "default",
                            db=db_client,
                        )
                    )
                    logger.debug("[Middleware] Skill extraction scheduled")
                except Exception as e:
                    logger.debug(f"[Middleware] Skill extraction skipped: {e}")

            # P1-1: 错误学习 — 记录工具调用成功/失败到 LearningSystem
            try:
                from app.agent.learning_system import learning_system

                for tc in completed:
                    tc_name = (
                        getattr(tc, "tool_name", None)
                        or (tc.get("tool_name") if isinstance(tc, dict) else None)
                        or "unknown"
                    )
                    tc_status = (
                        getattr(tc, "status", None) or (tc.get("status") if isinstance(tc, dict) else None) or "unknown"
                    )
                    tc_args = getattr(tc, "args", None) or (tc.get("args") if isinstance(tc, dict) else None) or {}
                    param_keys = list(tc_args.keys()) if isinstance(tc_args, dict) else []

                    if tc_status == "success":
                        ctx = {
                            "tool_name": tc_name,
                            "param_keys": param_keys,
                            "intent": state.get("intent_summary", "")[:60],
                        }
                        asyncio.create_task(
                            learning_system.record_success(
                                tool_name=tc_name,
                                solution=f"called {tc_name} with keys {param_keys}",
                                context=ctx,
                                org_id=config.org_id or "default",
                            )
                        )
                    elif tc_status == "error":
                        tc_error = (
                            getattr(tc, "error", None)
                            or (tc.get("error") if isinstance(tc, dict) else None)
                            or "unknown_error"
                        )
                        ctx = {
                            "tool_name": tc_name,
                            "error_type": type(tc_error).__name__ if not isinstance(tc_error, str) else tc_error[:120],
                            "param_keys": param_keys,
                        }
                        asyncio.create_task(
                            learning_system.record_failure(
                                tool_name=tc_name,
                                error_pattern=str(tc_error)[:200],
                                context=ctx,
                                user_id=config.user_id,
                                org_id=config.org_id or "default",
                            )
                        )
                logger.debug("[Middleware] Learning system recording scheduled")
            except Exception as e:
                logger.debug(f"[Middleware] Learning system recording skipped: {e}")

            # P0-7: 轻量快照 — 每轮对话结束时自动拍快照
            try:
                from app.agent.state_versioning import state_version_control

                session_id = getattr(config, "session_id", "")
                if session_id:
                    tool_names = []
                    for tc in completed:
                        name = getattr(tc, "tool_name", None) or (tc.get("tool_name") if isinstance(tc, dict) else None)
                        if name:
                            tool_names.append(name)

                    asyncio.create_task(
                        state_version_control.save_lightweight_snapshot(
                            thread_id=session_id,
                            state=state,
                            label="auto_turn",
                            tool_names=tool_names,
                        )
                    )
                    logger.debug("[Middleware] Turn-end snapshot scheduled")
            except Exception as e:
                logger.debug(f"[Middleware] Turn-end snapshot skipped: {e}")

    except Exception as e:
        logger.error(f"[Middleware] Memory update failed: {e}")

    return {"_memory_updated": True}
