"""
Post-graph persistence for the Hybrid Memory Manager.

After the agent graph runs, this module persists messages to the DB,
updates semantic caches, and extracts long-term memories in parallel.
"""

import asyncio
import logging
from typing import Any

from app.agent.memory.compaction import _strip_reasoning_from_history
from app.core.database import supabase

logger = logging.getLogger(__name__)


async def persist_result(
    user_id: str,
    session_id: str,
    user_message: str,
    assistant_response: str,
    agent_name: str | None = None,
    metadata: dict | None = None,
    db_client: Any | None = None,
    org_id: str | None = None,
    completed_tool_calls: list[dict] | None = None,
    skip_cache: bool = False,
    skip_semantic: bool = False,
    persist_messages: bool = True,
    defer_extraction: bool = True,
):
    """
    Post-graph: persist messages and update caches.

    1. Save user + assistant messages to DB
    2. Update semantic cache with the new Q-A pair
    3. Extract user-level and org-level long-term memories
    """
    client = db_client or supabase

    # Belt-and-suspenders: ensure no reasoning artifacts leak to DB
    if assistant_response:
        assistant_response = _strip_reasoning_from_history(assistant_response)

    # Persist the visible conversation before deferring enrichment work.
    try:
        import sys

        _memory_pkg = sys.modules[__package__]
        ChatService = _memory_pkg.ChatService

        if persist_messages:
            await ChatService.save_message(
                user_id=user_id,
                session_id=session_id,
                role="user",
                content=user_message,
                agent=agent_name,
                db_client=client,
                org_id=org_id,
            )
            await ChatService.save_message(
                user_id=user_id,
                session_id=session_id,
                role="assistant",
                content=assistant_response,
                agent=agent_name,
                metadata=metadata or {},
                db_client=client,
                org_id=org_id,
            )
    except Exception as e:
        logger.error(f"[Memory] Failed to persist messages: {e}")

    if defer_extraction and user_message and org_id:
        try:
            from app.services.conversation_memory.jobs import (
                enqueue_memory_persistence_job,
            )

            await enqueue_memory_persistence_job(
                user_id=user_id,
                org_id=org_id,
                session_id=session_id,
                user_message=user_message,
                assistant_response=assistant_response,
                agent_name=agent_name,
                metadata=metadata,
                completed_tool_calls=completed_tool_calls,
                skip_cache=skip_cache,
                skip_semantic=skip_semantic,
                db=client,
            )
            return
        except Exception:
            logger.exception(
                "[Memory] Durable extraction enqueue failed; running inline fallback"
            )

    # Update semantic cache (skip for confirmation/blocked responses and SIMPLE queries)
    # ── Phase 2: Parallel extraction tasks (mutually independent) ──
    # All these tasks are independent — run in parallel for ~3-5x speedup
    extraction_tasks: list[tuple[str, Any]] = []

    # Task: Semantic cache update
    if user_message and assistant_response and not skip_cache and not skip_semantic:

        async def _update_semantic_cache():
            from app.services.semantic_cache import semantic_cache_service

            await semantic_cache_service.set_cache(
                user_message, assistant_response, user_id
            )

        extraction_tasks.append(("semantic_cache", _update_semantic_cache()))

    # Task: Extract user-level long-term memories (with conflict resolution)
    if user_message and not skip_semantic:
        # Detect if this conversation used llm_task (subtask delegation)
        # — subtask outputs should not be extracted as user preferences
        _has_subtask = bool(
            completed_tool_calls
            and any(
                (tc.get("tool_name") or tc.get("name")) == "llm_task"
                for tc in completed_tool_calls
                if isinstance(tc, dict)
            )
        )

        async def _extract_user_memories():
            from app.services.conversation_memory_service import (
                conversation_memory_service,
            )

            messages_for_extraction = [
                {"role": "user", "content": user_message},
            ]
            if assistant_response:
                messages_for_extraction.append(
                    {"role": "assistant", "content": assistant_response}
                )
            extracted = await conversation_memory_service.extract_preferences(
                user_id=user_id,
                messages=messages_for_extraction,
                db=client,
                org_id=org_id,
                is_subtask=_has_subtask,
            )
            if extracted:
                logger.info(
                    f"[Memory] Extracted {len(extracted)} long-term memories for user {user_id}"
                )

        extraction_tasks.append(("user_memories", _extract_user_memories()))

    # Task: Extract organization-level memories
    if user_message and org_id and not skip_semantic:

        async def _extract_org_memories():
            from app.services.conversation_memory_service import (
                conversation_memory_service,
            )

            org_extracted = await conversation_memory_service.extract_org_memories(
                org_id=org_id,
                user_id=user_id,
                message=user_message,
                ai_response=assistant_response or "",
                db=client,
            )
            if org_extracted:
                logger.info(
                    f"[Memory] Extracted {len(org_extracted)} org memories for org {org_id} by user {user_id}"
                )

        extraction_tasks.append(("org_memories", _extract_org_memories()))

    # Task: Extract entity relationships for knowledge graph
    if user_message and org_id and not skip_semantic:

        async def _extract_graph():
            from app.services.conversation_memory.graph_extraction import (
                extract_graph_entities,
            )

            tool_output_list = []
            if completed_tool_calls:
                tool_output_list = [
                    {
                        "tool_name": tc.get("tool_name", ""),
                        "result": tc.get("result", ""),
                    }
                    for tc in completed_tool_calls
                    if tc.get("tool_name")
                ]
            entities = await extract_graph_entities(
                user_message=user_message,
                ai_response=assistant_response or "",
                org_id=org_id,
                user_id=user_id,
                tool_outputs=tool_output_list,
                db=client,
                session_id=session_id,
            )
            if entities:
                logger.info(
                    f"[Memory] Extracted {len(entities)} entity relations for org {org_id}"
                )

        extraction_tasks.append(("graph_entities", _extract_graph()))

    # Task: Behavior pattern learning from tool usage
    if completed_tool_calls and org_id:

        async def _learn_patterns():
            from app.services.knowledge_graph_service import learn_tool_patterns

            patterns = await learn_tool_patterns(
                user_id=user_id,
                org_id=org_id,
                tool_calls=completed_tool_calls,
                user_message=user_message,
            )
            if patterns:
                logger.info(
                    f"[Memory] Detected {len(patterns)} behavior patterns for org {org_id}"
                )

        extraction_tasks.append(("tool_patterns", _learn_patterns()))

    # Task: Save interaction episode for experience recall
    if user_message and assistant_response and not skip_semantic:

        async def _save_episode():
            from app.services.conversation_memory_service import episodic_memory_service

            tools_used = []
            if completed_tool_calls:
                tools_used = list(
                    {
                        tc.get("tool_name", "")
                        for tc in completed_tool_calls
                        if tc.get("tool_name")
                    }
                )
            await episodic_memory_service.save_episode(
                user_id=user_id,
                user_intent=user_message[:500],
                strategy=metadata.get("plan", "") if metadata else "",
                tools_used=tools_used,
                outcome=assistant_response[:500],
                confidence_score=(
                    metadata.get("confidence_score", 0.0) if metadata else 0.0
                ),
                duration_ms=metadata.get("duration_ms", 0) if metadata else 0,
                total_tokens=metadata.get("total_tokens", 0) if metadata else 0,
                complexity=(
                    metadata.get("complexity", "moderate") if metadata else "moderate"
                ),
                thinking_steps=metadata.get("thinking_steps", 0) if metadata else 0,
                session_id=session_id,
                org_id=org_id,
                db=client,
            )

        extraction_tasks.append(("episode", _save_episode()))

    # Task: Save completed task summary as long-term memory (P1 memory fix)
    # Only when meaningful work was done: tool calls executed OR long response generated
    _has_tools = bool(completed_tool_calls and len(completed_tool_calls) > 0)
    _is_long_response = bool(assistant_response and len(assistant_response) > 300)
    if (
        user_message
        and assistant_response
        and (_has_tools or _is_long_response)
        and not skip_semantic
    ):

        async def _save_task_memory():
            from app.services.conversation_memory_service import (
                conversation_memory_service,
            )

            # Build a concise task summary
            tool_names = []
            if completed_tool_calls:
                tool_names = list(
                    {
                        tc.get("tool_name", "")
                        for tc in completed_tool_calls
                        if tc.get("tool_name")
                    }
                )
            tool_part = f"（使用了工具: {', '.join(tool_names)}）" if tool_names else ""
            # Truncate for storage
            task_summary = (
                f"用户请求: {user_message[:200]}\n"
                f"完成结果: {assistant_response[:300]}{tool_part}"
            )
            import hashlib

            task_key = (
                f"task_{hashlib.md5(user_message[:100].encode()).hexdigest()[:10]}"
            )
            await conversation_memory_service.save_memory(
                user_id=user_id,
                key=task_key,
                value=task_summary,
                category="completed_task",
                importance=0.7,
                org_id=org_id,
                db=client,
                metadata={
                    "session_id": session_id,
                    "tools_used": tool_names,
                    "response_length": len(assistant_response),
                },
            )
            logger.info(
                f"[Memory] Saved completed_task memory for user {user_id}: {task_key}"
            )

        extraction_tasks.append(("task_memory", _save_task_memory()))

    # Generate/refresh user observation (throttle: skip if < 1 hour since last)
    async def _update_user_observation():
        try:
            from datetime import UTC, datetime, timedelta

            obs_check = await (
                client.table("memory_consolidations")
                .select("created_at")
                .eq("user_id", user_id)
                .eq("insight_type", "observation")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if obs_check.data:
                last_created = obs_check.data[0].get("created_at", "")
                if last_created:
                    last_dt = datetime.fromisoformat(
                        last_created.replace("Z", "+00:00")
                    )
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=UTC)
                    if datetime.now(UTC) - last_dt < timedelta(hours=1):
                        return  # Throttled: too recent

            from app.services.conversation_memory.consolidation import (
                generate_user_observation,
            )

            await generate_user_observation(user_id=user_id, org_id=org_id, db=client)
        except Exception as e:
            logger.error(f"[Memory] User observation generation failed: {e}")

    extraction_tasks.append(("user_observation", _update_user_observation()))

    # Execute all extraction tasks in parallel
    if extraction_tasks:
        task_names = [name for name, _ in extraction_tasks]
        coros = [coro for _, coro in extraction_tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)

        # Log any failures (non-fatal)
        for name, result in zip(task_names, results, strict=False):
            if isinstance(result, Exception):
                logger.error(f"[Memory] Parallel task '{name}' failed: {result}")
