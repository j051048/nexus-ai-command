"""[J] Three response recovery strategies: content-filter, short-response, empty-response."""

from langchain_core.messages import SystemMessage

from app.agent.node_helpers import (
    AgentConfig,
    QueryComplexity,
    _get_llm,
    logger,
)


async def recover_response(
    *,
    ai_msg,
    state: dict,
    agent_config: AgentConfig,
    model: str | None,
    lc_msgs: list,
    tool_schemas: list | None,
    complexity: QueryComplexity,
    iteration: int,
    resolved: dict | None,
):
    """Apply recovery strategies and return (ai_msg, content, tool_calls_raw)."""
    tool_calls_raw = ai_msg.tool_calls
    content = ai_msg.content or ""
    finish_reason = ai_msg.response_metadata.get("finish_reason", "unknown")

    # ── Content Filter Recovery ──
    if finish_reason == "content_filter" and not tool_calls_raw and not content.strip():
        ai_msg, content, tool_calls_raw = await _recover_content_filter(
            ai_msg, agent_config, model, lc_msgs, tool_schemas
        )

    # ── Short/Useless Response Recovery (First Iteration) ──
    if (
        iteration == 0
        and not tool_calls_raw
        and len(content.strip()) < 100
        and complexity in (QueryComplexity.COMPLEX, QueryComplexity.CRITICAL)
    ):
        ai_msg, content, tool_calls_raw = await _recover_short_response(
            ai_msg, content, agent_config, model, lc_msgs, tool_schemas, complexity
        )

    # ── Empty Response Recovery ──
    completed_tools = state.get("completed_tool_calls", [])
    if not content.strip() and not tool_calls_raw and completed_tools and iteration > 0:
        ai_msg, content, tool_calls_raw = await _recover_empty_response(
            ai_msg, agent_config, model, lc_msgs, completed_tools, resolved
        )

    return ai_msg, content, tool_calls_raw


async def _recover_content_filter(ai_msg, agent_config, model, lc_msgs, tool_schemas):
    logger.warning(
        "[PlanNode] Content filter blocked response — retrying with fallback LLM"
    )
    try:
        from app.agent.node_helpers import _get_fallback_llm

        fallback_llm = _get_fallback_llm(agent_config, model=model, streaming=True)
        if fallback_llm:
            if tool_schemas:
                fallback_llm = fallback_llm.bind_tools(
                    tool_schemas, parallel_tool_calls=True
                )
            ai_msg = await fallback_llm.ainvoke(lc_msgs)
            content = ai_msg.content or ""
            tool_calls_raw = ai_msg.tool_calls
            if tool_calls_raw or content.strip():
                logger.info(
                    "[PlanNode] Content filter recovery succeeded via fallback LLM"
                )
            else:
                logger.warning(
                    "[PlanNode] Fallback LLM also returned empty after content_filter"
                )
            return ai_msg, content, tool_calls_raw
        else:
            logger.info(
                "[PlanNode] No fallback LLM available for content_filter recovery"
            )
    except Exception as e:
        logger.error(f"[PlanNode] Content filter recovery failed: {e}")
    return ai_msg, ai_msg.content or "", ai_msg.tool_calls


async def _recover_short_response(
    ai_msg, content, agent_config, model, lc_msgs, tool_schemas, complexity
):
    logger.warning(
        f"[PlanNode] Short response ({len(content.strip())} chars) with no tool calls "
        f"for {complexity.value} query — retrying with fallback LLM"
    )
    try:
        from app.agent.node_helpers import _get_fallback_llm

        fallback_llm = _get_fallback_llm(agent_config, model=model, streaming=True)
        if fallback_llm:
            if tool_schemas:
                fallback_llm = fallback_llm.bind_tools(
                    tool_schemas, parallel_tool_calls=True
                )
            ai_msg = await fallback_llm.ainvoke(lc_msgs)
            content = ai_msg.content or ""
            tool_calls_raw = ai_msg.tool_calls
            if tool_calls_raw or len(content.strip()) >= 100:
                logger.info(
                    "[PlanNode] Short response recovery succeeded via fallback LLM"
                )
            else:
                logger.warning(
                    "[PlanNode] Fallback LLM also returned short response"
                )
            return ai_msg, content, tool_calls_raw
        else:
            logger.info(
                "[PlanNode] No fallback LLM available for short response recovery"
            )
    except Exception as e:
        logger.error(f"[PlanNode] Short response recovery failed: {e}")
    return ai_msg, ai_msg.content or "", ai_msg.tool_calls


async def _recover_empty_response(
    ai_msg, agent_config, model, lc_msgs, completed_tools, resolved
):
    logger.warning(
        "[PlanNode] LLM returned empty response after tool execution, retrying with synthesis prompt"
    )
    # Build a concise summary of tool results for the retry
    tool_summaries = []
    for tc in completed_tools[-5:]:
        t_name = (
            tc.tool_name if hasattr(tc, "tool_name") else tc.get("tool_name", "")
        )
        t_result = (tc.result if hasattr(tc, "result") else tc.get("result", ""))[
            :300
        ]
        t_status = tc.status if hasattr(tc, "status") else tc.get("status", "")
        tool_summaries.append(f"- {t_name} ({t_status}): {t_result}")
    synthesis_msg = SystemMessage(
        content=(
            "你刚才调用了工具并获得了结果，但没有生成回复。"
            "请根据以下工具执行结果，直接用中文回答用户的问题。\n\n"
            "工具结果:\n" + "\n".join(tool_summaries)
        )
    )
    retry_msgs = lc_msgs + [synthesis_msg]
    try:
        retry_llm = _get_llm(
            agent_config, model=model, streaming=True, resolved_config=resolved
        )
        # Don't bind tools — we want a text response, not more tool calls
        ai_msg = await retry_llm.ainvoke(retry_msgs)
        content = ai_msg.content or ""
        tool_calls_raw = ai_msg.tool_calls
        if content.strip():
            logger.info("[PlanNode] Empty response recovery succeeded")
        else:
            # Still empty — build a fallback response from tool results
            logger.warning(
                "[PlanNode] Retry still empty, constructing fallback from tool results"
            )
            fallback_parts = ["以下是工具执行结果：\n"]
            for tc in completed_tools:
                t_name = (
                    tc.tool_name
                    if hasattr(tc, "tool_name")
                    else tc.get("tool_name", "")
                )
                t_result = (
                    tc.result if hasattr(tc, "result") else tc.get("result", "")
                )[:500]
                fallback_parts.append(f"**{t_name}**: {t_result}")
            content = "\n\n".join(fallback_parts)
            from langchain_core.messages import AIMessage as _AIMessage

            ai_msg = _AIMessage(content=content)
            tool_calls_raw = []
        return ai_msg, content, tool_calls_raw
    except Exception as e:
        logger.error(f"[PlanNode] Empty response recovery failed: {e}")
    return ai_msg, ai_msg.content or "", ai_msg.tool_calls or []
