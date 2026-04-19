"""Chat Service for Nexus AI — Shared Utilities

Provides shared helpers used by the LangGraph agent pipeline:
- get_system_prompt: Prompt resolution with cache → DB → registry fallback
- execute_tool: Tool execution with RBAC, confirmation gates, and retry
- save_message: Persistence of chat messages
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.core.database import supabase
from app.core.prompts_registry import SYSTEM_PROMPTS
from app.core.redis_keys import NS_PROMPT, rk
from app.services.cache_service import cache_service
from app.tools import get_tool


def _json(obj: Any) -> str:
    """JSON serialize preserving Chinese characters."""
    return json.dumps(obj, ensure_ascii=False)


logger = logging.getLogger(__name__)

# P1 Fix #12: Make chat history window configurable
MAX_HISTORY = getattr(settings, "MAX_CHAT_HISTORY", 10)


class ChatService:
    @staticmethod
    async def get_system_prompt(
        agent_name: str,
        db_client: Any | None = None,
        user_id: str | None = None,
        org_id: str | None = None,
    ) -> str:
        """Get formatted system prompt for agent (P1 Fix #29: Fetch from DB with local fallback)
        #24: Integrates A/B test variant selection when user_id is provided.
        """
        now_str = datetime.now(timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        prompt_key = "default_fallback"
        if agent_name in ["@销售指挥官", "sales_commander"]:
            prompt_key = "sales_commander"
        elif agent_name in ["@审批管家", "approval_manager"]:
            prompt_key = "approval_manager"
        elif agent_name in ["@绩效教练", "performance_coach"]:
            prompt_key = "performance_coach"
        elif agent_name in ["@总裁助理", "boss_assistant"]:
            prompt_key = "boss_assistant"

        # 0. Try A/B test variant (if user_id provided)
        if user_id:
            try:
                from app.services.prompt_version_service import prompt_version_service

                variant = prompt_version_service.get_ab_test_variant(
                    prompt_key, user_id
                )
                if variant and variant.content:
                    try:
                        return variant.content.replace(
                            "{current_time}", now_str
                        ).replace("{{current_time}}", now_str)
                    except Exception:
                        return variant.content
            except Exception as e:
                logger.error(f"A/B test variant lookup failed: {e}")

        # 1. Try Cache (org-scoped to prevent cross-tenant prompt leakage)
        cache_key = rk(org_id, NS_PROMPT, prompt_key)
        cached_prompt = await cache_service.get(cache_key)
        if cached_prompt:
            try:
                return cached_prompt.replace("{current_time}", now_str).replace(
                    "{{current_time}}", now_str
                )
            except Exception:
                return cached_prompt

        # 2. Try DB
        try:
            client = db_client or supabase
            res = (
                await client.table("prompts")
                .select("content")
                .eq("name", prompt_key)
                .maybe_single()
                .execute()
            )
            if res and res.data:
                raw_prompt = res.data["content"]
                await cache_service.set(cache_key, raw_prompt, ttl=3600)
                return raw_prompt.replace("{current_time}", now_str).replace(
                    "{{current_time}}", now_str
                )
        except Exception as e:
            logger.warning(f"Failed to fetch prompt {prompt_key} from DB: {e}")

        # 3. Fallback to hardcoded registry
        raw_prompt = SYSTEM_PROMPTS.get(prompt_key, SYSTEM_PROMPTS["default_fallback"])
        try:
            return raw_prompt.replace("{current_time}", now_str).replace(
                "{{current_time}}", now_str
            )
        except Exception:
            return raw_prompt

    @staticmethod
    async def _get_cached_user_role(user_id: str, db_client: Any | None = None) -> str:
        """Helper to get user role (cached)"""
        cached = await cache_service.get_user_role(user_id)
        if cached:
            return cached

        try:
            client = db_client or supabase
            res = (
                await client.table("users")
                .select("role")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
            role = res.data.get("role", "employee") if res.data else "employee"
            await cache_service.set_user_role(user_id, role)
            return role
        except Exception as e:
            logger.error(f"Role fetch error: {e}")
            return "employee"

    @staticmethod
    async def execute_tool(
        name: str,
        args: dict[str, Any],
        user_id: str,
        config: dict = None,
        system_confirmed: bool = False,
        db_client: Any | None = None,
    ) -> str:
        """Execute tool with RBAC, System-level Confirmation Gate, and Retry"""
        tool = get_tool(name)
        if not tool:
            return f"Error: Tool {name} not found."

        # 1. RBAC Check
        if tool.required_role not in ["all", "ai_assistant"]:
            user_role = await ChatService._get_cached_user_role(
                user_id, db_client=db_client
            )
            if tool.required_role == "boss" and user_role not in ["boss", "founder"]:
                return f"⛔ Permission Denied: Tool requires [Boss] role. You are [{user_role}]."
            elif tool.required_role == "manager" and user_role not in [
                "manager",
                "boss",
                "founder",
            ]:
                return f"⛔ Permission Denied: Tool requires [Manager] role. You are [{user_role}]."

        # 2. System-level Confirmation Gate (P0 Fix #10)
        # This runs BEFORE the tool's own logic, preventing LLM from bypassing confirm
        # P0 Fix #2: Pass system_confirmed to strict check
        confirmation_msg, _confirmation_type = tool.check_confirmation(
            args, system_confirmed=system_confirmed
        )
        if confirmation_msg is not None:
            logger.info(f"[HITL Gate] Tool {name} blocked - awaiting user confirmation")
            return confirmation_msg

        # 3. Retry Logic with timeout
        for attempt in range(3):
            try:
                result = await asyncio.wait_for(
                    tool.run(args, user_id, config=config),
                    timeout=30.0,  # 30s timeout per tool execution
                )
                return result
            except TimeoutError:
                return f"Error: Tool {name} timed out after 30 seconds."
            except Exception as e:
                if attempt == 2:
                    return f"Error: Tool {name} failed after 3 attempts: {str(e)}"
                await asyncio.sleep(0.5 * (attempt + 1))
        return "Error: Unknown tool execution failure"

    @staticmethod
    async def send_message(
        user_id: str,
        org_id: str = "default",
        message: str = "",
        session_id: str = "default",
    ) -> dict:
        """Non-streaming agent invocation for background tasks (scheduled tasks, system push).

        Builds an AgentState, runs the graph to completion, persists the result,
        and returns {"response": str}.
        """
        from app.agent.graph import get_agent_graph
        from app.agent.memory.persistence import persist_result
        from app.agent.memory.prepare import prepare_initial_state
        from app.agent.state import AgentConfig

        agent_name = "default"
        system_prompt = await ChatService.get_system_prompt(
            agent_name, user_id=user_id, org_id=org_id,
        )
        user_role = await ChatService._get_cached_user_role(user_id)

        agent_config = AgentConfig(
            user_id=user_id,
            session_id=session_id,
            agent_name=agent_name,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.AI_BASE_URL,
            model=settings.AI_DEFAULT_MODEL,
            mini_model=getattr(settings, "AI_MINI_MODEL", "gpt-4o-mini"),
            user_role=user_role,
            org_id=org_id,
            max_iterations=settings.LANGGRAPH_MAX_ITERATIONS,
            tool_timeout=settings.LANGGRAPH_TOOL_TIMEOUT,
            gather_timeout=settings.LANGGRAPH_GATHER_TIMEOUT,
        )

        raw_messages = [{"role": "user", "content": message}]
        initial_state = await prepare_initial_state(
            raw_messages, system_prompt, agent_config,
        )
        # P1 Fix: prepare_initial_state does not return 'config'; graph nodes
        # (node_respond/node_reflect/router/...) rely on state["config"].
        # Without this, background invocations (proactive scheduler, scheduled
        # tasks) fail with KeyError: 'config' and metrics lose user_id/org_id.
        initial_state["config"] = agent_config

        graph = get_agent_graph()
        thread_id = f"{org_id}::{session_id}"
        final_state = await graph.run(initial_state, thread_id=thread_id)

        response = final_state.get("final_response", "")

        # Persist conversation
        try:
            await persist_result(
                user_id=user_id,
                session_id=session_id,
                user_message=message,
                assistant_response=response,
                agent_name=agent_name,
                org_id=org_id,
            )
        except Exception as e:
            logger.error(f"send_message persist failed: {e}")

        return {"response": response}

    @staticmethod
    async def save_message(
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        agent: str = None,
        metadata: dict = None,
        db_client: Any | None = None,
        org_id: str | None = None,
    ):
        """Save a message to the database for persistence.

        Always uses the global (service-key) supabase client to bypass RLS.
        The org_id is stored for tenant-level isolation via RLS SELECT policies.
        """
        try:
            data = {
                "user_id": user_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
            }
            if agent:
                data["agent"] = agent
            if org_id:
                data["organization_id"] = org_id
            await supabase.table("chat_messages").insert(data).execute()
        except Exception as e:
            logger.error(f"Failed to save chat message: {str(e)}")
