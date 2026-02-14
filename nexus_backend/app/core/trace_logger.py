import json
import uuid
import datetime
import logging
import os
import asyncio
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency at module level
_sanitize_output = None
_langfuse_client = None


def _get_sanitizer():
    global _sanitize_output
    if _sanitize_output is None:
        try:
            from app.services.content_moderation import sanitize_output

            _sanitize_output = sanitize_output
        except ImportError:

            def _noop(x):
                return x

            _sanitize_output = _noop
    return _sanitize_output


def _get_langfuse():
    """Lazy initialize Langfuse client if configured."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if public_key and secret_key:
        try:
            from langfuse import Langfuse

            _langfuse_client = Langfuse(
                public_key=public_key, secret_key=secret_key, host=host
            )
            logger.info("Langfuse client initialized successfully")
        except ImportError:
            logger.warning("Langfuse package not installed. Run: pip install langfuse")
            _langfuse_client = False  # Mark as unavailable
        except Exception as e:
            logger.warning(f"Failed to initialize Langfuse: {e}")
            _langfuse_client = False
    else:
        _langfuse_client = False  # Not configured

    return _langfuse_client if _langfuse_client else None


class TraceLogger:
    """
    Structured JSON Logger for LLM Traces with Langfuse integration.
    Outputs NDJSON (Newline Delimited JSON) to stdout for easy collection
    (e.g. by Datadog, ELK, or simple grep).
    Also pushes traces to Langfuse if configured.
    """

    def __init__(self, user_id: str, agent: str, session_id: Optional[str] = None):
        self.trace_id = str(uuid.uuid4())
        self.user_id = user_id
        self.agent = agent
        self.session_id = session_id
        self.start_time = datetime.datetime.now()
        self._spans: List[Dict] = []
        self._langfuse_trace = None

        # Initialize Langfuse trace if available
        langfuse = _get_langfuse()
        if langfuse:
            try:
                self._langfuse_trace = langfuse.trace(
                    id=self.trace_id,
                    name=f"chat_{agent}",
                    user_id=user_id,
                    session_id=session_id,
                    metadata={"agent": agent},
                )
            except Exception as e:
                logger.warning(f"Failed to create Langfuse trace: {e}")

    def _sanitize_content(self, content: Any) -> Any:
        """Sanitize content to remove PII before logging."""
        sanitize = _get_sanitizer()
        if isinstance(content, dict):
            sanitized = {}
            for k, v in content.items():
                if isinstance(v, str):
                    sanitized[k] = sanitize(v)
                else:
                    sanitized[k] = v
            return sanitized
        elif isinstance(content, str):
            return sanitize(content)
        return content

    def _emit(self, event_type: str, content: Dict[str, Any]):
        """Emit a structured trace log entry to stdout."""
        try:
            safe_content = self._sanitize_content(content)
            entry = {
                "trace_id": self.trace_id,
                "timestamp": datetime.datetime.now().isoformat(),
                "user_id": self.user_id,
                "agent": self.agent,
                "event": event_type,
                "content": safe_content,
            }
            # Structured JSON to logger for container log collection
            logger.info(f"TRACE_LOG: {json.dumps(entry, ensure_ascii=False)}")
        except Exception as e:
            logger.warning(f"TraceLogger emit failed: {e}")

    def log_start(self, messages: List[Dict]):
        # Sensitive: Don't log full history if massive, but for MVP log last message
        last_msg = messages[-1] if messages else {}
        self._emit(
            "start_conversation",
            {
                "last_message_role": last_msg.get("role"),
                "last_message_content_preview": str(last_msg.get("content"))[:200],
            },
        )

    def log_tool_plan(self, tool_name: str, args: Dict):
        self._emit("tool_planned", {"tool_name": tool_name, "arguments": args})
        # Langfuse span for tool planning
        if self._langfuse_trace:
            try:
                self._langfuse_trace.span(
                    name=f"tool_plan_{tool_name}",
                    input=args,
                    metadata={"phase": "planning"},
                )
            except Exception as e:
                logger.debug(f"Langfuse span failed: {e}")

    def log_tool_execution(self, tool_name: str, status: str, result_preview: str):
        self._emit(
            "tool_executed",
            {
                "tool_name": tool_name,
                "status": status,
                "output_preview": result_preview[:500],  # Cap output log size
            },
        )
        # Langfuse span for tool execution
        if self._langfuse_trace:
            try:
                self._langfuse_trace.span(
                    name=f"tool_exec_{tool_name}",
                    output=result_preview[:500],
                    metadata={"phase": "execution", "status": status},
                )
            except Exception as e:
                logger.debug(f"Langfuse span failed: {e}")

    def log_error(self, error: str):
        self._emit("error", {"error_message": str(error)})

    def log_end(self, total_tokens: int = 0, cost: float = 0.0):
        duration = (datetime.datetime.now() - self.start_time).total_seconds()
        self._emit(
            "end_conversation",
            {
                "duration_seconds": round(duration, 3),
                "total_tokens": total_tokens,
                "cost_usd": cost,
            },
        )

        # Langfuse: Finalize trace with metrics
        if self._langfuse_trace:
            try:
                self._langfuse_trace.update(
                    output={"total_tokens": total_tokens, "cost_usd": cost},
                    metadata={
                        "duration_seconds": round(duration, 3),
                        "total_tokens": total_tokens,
                    },
                )
                # Flush Langfuse in background to avoid blocking
                langfuse = _get_langfuse()
                if langfuse:
                    asyncio.create_task(self._flush_langfuse(langfuse))
            except Exception as e:
                logger.debug(f"Langfuse update failed: {e}")

    async def _flush_langfuse(self, langfuse):
        """Flush Langfuse client in background."""
        try:
            langfuse.flush()
        except Exception as e:
            logger.debug(f"Langfuse flush failed: {e}")

    def log_generation(
        self, model: str, input_messages: List[Dict], output: str, usage: Dict = None
    ):
        """Log a generation event (LLM call) to Langfuse."""
        if self._langfuse_trace:
            try:
                self._langfuse_trace.generation(
                    name="chat_completion",
                    model=model,
                    input=input_messages[-1] if input_messages else None,
                    output=output[:1000],
                    usage=usage or {},
                    metadata={"agent": self.agent},
                )
            except Exception as e:
                logger.debug(f"Langfuse generation failed: {e}")
