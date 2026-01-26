import json
import uuid
import datetime
from typing import Any, Dict, List

class TraceLogger:
    """
    Simple Structured JSON Logger for LLM Traces.
    Outputs NDJSON (Newline Delimited JSON) to stdout for easy collection (e.g. by Datadog, ELK, or simple grep).
    """
    def __init__(self, user_id: str, agent: str):
        self.trace_id = str(uuid.uuid4())
        self.user_id = user_id
        self.agent = agent
        self.start_time = datetime.datetime.now()
    
    def _emit(self, event_type: str, content: Dict[str, Any]):
        entry = {
            "trace_id": self.trace_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "user_id": self.user_id,
            "agent": self.agent,
            "event": event_type,
            "content": content
        }
        # Print JSON to stdout - standard practice for container logs
        print(f"TRACE_LOG: {json.dumps(entry, ensure_ascii=False)}")

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
