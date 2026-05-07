"""Durable Agent run observability.

This service mirrors the volatile in-memory trace stream into relational tables:
agent_runs, agent_events, and agent_tool_calls.  All methods are best-effort and
must never break the agent execution path.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import asdict, is_dataclass
from typing import Any

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Convert common agent objects into PostgREST-friendly JSON values."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(v) for v in value]
    if hasattr(value, "value"):
        return value.value
    return str(value)


class AgentRunObserver:
    """Best-effort persistence for Agent execution observability."""

    async def start_run(
        self,
        *,
        thread_id: str,
        org_id: str | None,
        user_id: str | None,
        session_id: str | None,
        trace_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        row = {
            "id": run_id,
            "thread_id": thread_id,
            "organization_id": org_id,
            "user_id": user_id,
            "session_id": session_id,
            "trace_id": trace_id,
            "status": "running",
            "metadata": metadata or {},
        }
        await self._insert("agent_runs", row)
        return run_id

    async def finish_run(
        self,
        *,
        run_id: str | None,
        status: str,
        error: str | None = None,
        final_response: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        duration_ms: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        if not run_id:
            return
        patch = {
            "status": status,
            "error": (error or "")[:1000] if error else None,
            "final_response": (final_response or "")[:2000] if final_response else None,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
            "duration_ms": duration_ms,
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if metadata:
            patch["metadata"] = metadata
        try:
            from app.core.database import supabase

            if supabase:
                await supabase.table("agent_runs").update(patch).eq("id", run_id).execute()
        except Exception as exc:
            logger.debug("[AgentRunObserver] finish_run skipped: %s", exc)

    async def event(
        self,
        *,
        run_id: str | None,
        org_id: str | None,
        event_type: str,
        node_name: str | None = None,
        payload: dict | None = None,
    ) -> None:
        if not run_id:
            return
        await self._insert(
            "agent_events",
            {
                "agent_run_id": run_id,
                "organization_id": org_id,
                "event_type": event_type,
                "node_name": node_name,
                "payload": _json_safe(payload or {}),
            },
        )

    async def tool_call(
        self,
        *,
        run_id: str | None,
        org_id: str | None,
        tool_name: str,
        tool_call_id: str | None = None,
        status: str | None = None,
        duration_ms: int | None = None,
        args: dict | None = None,
        result: str | None = None,
        error_type: str | None = None,
    ) -> None:
        if not run_id:
            return
        await self._insert(
            "agent_tool_calls",
            {
                "agent_run_id": run_id,
                "organization_id": org_id,
                "tool_name": tool_name,
                "tool_call_id": tool_call_id,
                "status": status,
                "duration_ms": duration_ms,
                "tool_args": _json_safe(args or {}),
                "result_preview": (result or "")[:1000] if result else None,
                "error_type": error_type,
            },
        )

    async def _insert(self, table: str, row: dict) -> None:
        try:
            from app.core.database import supabase

            if supabase:
                await supabase.table(table).insert(row).execute()
        except Exception as exc:
            logger.debug("[AgentRunObserver] insert into %s skipped: %s", table, exc)


agent_run_observer = AgentRunObserver()
