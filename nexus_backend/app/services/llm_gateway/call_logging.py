"""
LLM Gateway - Call Logging Module

Handles buffered batch-insert of LLM call logs to the database.
"""

import logging
import time
import uuid

from app.core.database import supabase
from app.core.trace_context import get_trace_id

logger = logging.getLogger(__name__)


class CallLoggingMixin:
    """
    Mixin providing buffered call logging for LLM requests.

    Requires:
        self._log_buffer: list[dict]
        self._log_last_flush: float
        self._LOG_BATCH_SIZE: int
        self._LOG_FLUSH_INTERVAL: float
    """

    async def _log_call(
        self,
        org_id: str,
        model_code: str,
        scene_code: str,
        agent_code: str,
        user_id: str,
        request_id: str,
        status: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        latency_ms: int,
        error_msg: str | None = None,
    ) -> None:
        """
        Buffer a log record and flush to DB in batches.

        Flushes when the buffer reaches _LOG_BATCH_SIZE or when
        _LOG_FLUSH_INTERVAL seconds have elapsed since the last flush.
        Failures are logged but never propagated.
        """
        row = {
            "id": str(uuid.uuid4()),
            "tenant_id": org_id,
            "model_code": model_code,
            "scene_code": scene_code,
            "agent_code": agent_code,
            "user_id": user_id,
            "request_id": request_id,
            "status": status,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": cost,
            "latency_ms": latency_ms,
            "error_msg": error_msg,
        }
        # #25: trace_id for end-to-end tracing
        trace_id = get_trace_id()
        if trace_id:
            row["trace_id"] = trace_id

        self._log_buffer.append(row)

        now = time.time()
        should_flush = (
            len(self._log_buffer) >= self._LOG_BATCH_SIZE or (now - self._log_last_flush) >= self._LOG_FLUSH_INTERVAL
        )
        if should_flush:
            await self._flush_log_buffer()

    async def _flush_log_buffer(self) -> None:
        """Flush buffered log records to the database in a single insert."""
        if not self._log_buffer or not supabase:
            return

        batch = self._log_buffer[:]
        self._log_buffer.clear()
        self._log_last_flush = time.time()

        try:
            await supabase.table("llm_call_log").insert(batch).execute()
        except Exception as e:
            logger.warning(f"Failed to batch-insert {len(batch)} LLM call logs: {e}")
