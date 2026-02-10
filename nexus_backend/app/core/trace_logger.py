import json
import uuid
import datetime
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependency at module level
_sanitize_output = None

def _get_sanitizer():
    global _sanitize_output
    if _sanitize_output is None:
        try:
            from app.services.content_moderation import sanitize_output
            _sanitize_output = sanitize_output
        except ImportError:
            _sanitize_output = lambda x: x  # Fallback: no-op
    return _sanitize_output


class TraceLogger:
    """
    Simple Structured JSON Logger for LLM Traces.
    Outputs NDJSON (Newline Delimited JSON) to stdout for easy collection
    (e.g. by Datadog, ELK, or simple grep).
    """
    def __init__(self, user_id: str, agent: str):
        self.trace_id = str(uuid.uuid4())
        self.user_id = user_id
        self.agent = agent
        self.start_time = datetime.datetime.now()

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
                "content": safe_content
            }
            # Print JSON to stdout - standard practice for container logs
            print(f"TRACE_LOG: {json.dumps(entry, ensure_ascii=False)}")
        except Exception as e:
            logger.warning(f"TraceLogger emit failed: {e}")

    def log_start(self, messages: List[Dict]):
        # Sensitive: Don't log full history if massive, but for MVP log last message
        last_msg = messages[-1] if messages else {}
        self._emit("start_conversation", {
            "last_message_role": last_msg.get("role"),
            "last_message_content_preview": str(last_msg.get("content"))[:200]
        })

    def log_tool_plan(self, tool_name: str, args: Dict):
        self._emit("tool_planned", {
            "tool_name": tool_name,
            "arguments": args
        })

    def log_tool_execution(self, tool_name: str, status: str, result_preview: str):
        self._emit("tool_executed", {
            "tool_name": tool_name,
            "status": status,
            "output_preview": result_preview[:500] # Cap output log size
        })

    def log_error(self, error: str):
        self._emit("error", {
            "error_message": str(error)
        })

    def log_end(self):
        duration = (datetime.datetime.now() - self.start_time).total_seconds()
        self._emit("end_conversation", {
            "duration_seconds": round(duration, 3)
        })
