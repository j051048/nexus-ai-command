"""
Celery tasks for isolated tool execution.

High-risk or long-running tools can be executed in a separate Celery worker so
they get process-level timeout, retry and DLQ behavior without blocking the
Agent event loop.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

try:
    from app.core.celery_app import NexusTask, celery_app

    @celery_app.task(
        name="execute_tool_isolated",
        bind=True,
        base=NexusTask,
        max_retries=1,
        soft_time_limit=120,
        time_limit=150,
    )
    def execute_tool_isolated(
        self,
        tool_name: str,
        tool_args: dict,
        user_id: str,
        org_id: str | None = None,
        token: str | None = None,
        trace_id: str | None = None,
    ):
        """Execute a tool in an isolated Celery worker process."""

        async def _run():
            from app.tools import get_tool

            tool = get_tool(tool_name)
            if not tool:
                return f"Tool {tool_name} not found"

            result = await tool.run(
                tool_args,
                user_id,
                config={
                    "org_id": org_id,
                    "organization_id": org_id,
                    "token": token,
                    "trace_id": trace_id,
                    "execution_context": "celery_isolated",
                },
            )
            return str(result)

        return asyncio.run(_run())

except ImportError:

    def execute_tool_isolated(*args, **kwargs):
        raise ImportError(
            "Celery is not installed. Install celery to use isolated tool execution."
        )
