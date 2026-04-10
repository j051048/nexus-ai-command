"""
S4: Celery task for isolated tool execution.

High-risk tools (isolation_level="celery") are offloaded here to run in a
separate Celery worker process, providing failure isolation and independent
timeout enforcement.
"""

import logging

logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(
        name="execute_tool_isolated",
        bind=True,
        max_retries=1,
        soft_time_limit=120,
        time_limit=150,
    )
    def execute_tool_isolated(
        self, tool_name: str, tool_args: dict, user_id: str, org_id: str | None = None
    ):
        """Execute a tool in an isolated Celery worker process."""
        import asyncio

        async def _run():
            from app.tools import get_tool

            tool = get_tool(tool_name)
            if not tool:
                return f"工具 {tool_name} 不存在"
            result = await tool.run(
                tool_args,
                user_id,
                config={"org_id": org_id},
            )
            return str(result)

        return asyncio.run(_run())

except ImportError:
    # Celery not installed — provide a no-op fallback
    def execute_tool_isolated(*args, **kwargs):
        raise ImportError(
            "Celery is not installed. Install celery to use isolated tool execution."
        )
