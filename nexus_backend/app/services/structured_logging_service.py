"""
P2 Enhancement: Structured Logging Service

Implements centralized structured logging with JSON format.
Fixes Issue #28: Missing structured logging.
"""

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class LogLevel(Enum):
    """Log levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class StructuredLogEntry:
    """Structured log entry."""
    timestamp: str
    level: str
    message: str
    service: str
    component: str
    trace_id: str | None = None
    user_id: str | None = None
    org_id: str | None = None
    request_id: str | None = None
    duration_ms: int | None = None
    error_type: str | None = None
    error_stack: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logs."""

    def __init__(self, service_name: str = "nexus-ai"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "service": self.service_name,
            "component": record.name,
            "file": record.filename,
            "line": record.lineno,
        }

        # Add extra fields if present
        extra_fields = [
            "trace_id", "user_id", "org_id", "request_id",
            "duration_ms", "error_type", "error_stack", "metadata"
        ]

        for field_name in extra_fields:
            if hasattr(record, field_name):
                entry[field_name] = getattr(record, field_name)

        # Add exception info if present
        if record.exc_info:
            entry["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            entry["error_stack"] = self.formatException(record.exc_info)

        return json.dumps(entry, ensure_ascii=False)


class StructuredLogger:
    """
    P2 Enhancement: Structured logging with JSON output.

    Features:
    - JSON formatted logs
    - Trace ID correlation
    - Request context tracking
    - Performance metrics
    - Error tracking with stack traces
    - Configurable output (stdout/file)
    """

    def __init__(
        self,
        service_name: str = "nexus-ai",
        log_level: str = "INFO",
        output_format: str = "json"
    ):
        self.service_name = service_name
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.output_format = output_format
        self._logger = self._setup_logger()

        # Context storage for request tracking
        self._context: dict[str, Any] = {}

    def _setup_logger(self) -> logging.Logger:
        """Setup logger with structured formatter."""
        logger = logging.getLogger(self.service_name)
        logger.setLevel(self.log_level)

        # Remove existing handlers
        logger.handlers = []

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)

        if self.output_format == "json":
            console_handler.setFormatter(StructuredFormatter(self.service_name))
        else:
            console_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))

        logger.addHandler(console_handler)
        return logger

    def set_context(self, **kwargs):
        """Set context fields for subsequent logs."""
        self._context.update(kwargs)

    def clear_context(self):
        """Clear context fields."""
        self._context = {}

    def _log(self, level: LogLevel, message: str, **kwargs):
        """Internal log method with context."""
        extra = {**self._context, **kwargs}

        # Map log level
        level_map = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }

        self._logger.log(level_map[level], message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, error: Exception = None, **kwargs):
        """Log error message with optional exception."""
        if error:
            kwargs["error_type"] = type(error).__name__
        self._log(LogLevel.ERROR, message, **kwargs, exc_info=error is not None)

    def critical(self, message: str, error: Exception = None, **kwargs):
        """Log critical message."""
        if error:
            kwargs["error_type"] = type(error).__name__
        self._log(LogLevel.CRITICAL, message, **kwargs, exc_info=error is not None)

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: int,
        user_id: str = None,
        org_id: str = None,
        request_id: str = None
    ):
        """Log HTTP request."""
        self.info(
            f"HTTP {method} {path} - {status_code}",
            metadata={
                "http_method": method,
                "http_path": path,
                "http_status": status_code,
            },
            user_id=user_id,
            org_id=org_id,
            request_id=request_id,
            duration_ms=duration_ms
        )

    def log_llm_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        trace_id: str = None,
        user_id: str = None
    ):
        """Log LLM API call."""
        self.info(
            f"LLM call: {model}",
            metadata={
                "llm_model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            trace_id=trace_id,
            user_id=user_id,
            duration_ms=duration_ms
        )

    def log_tool_call(
        self,
        tool_name: str,
        status: str,
        duration_ms: int,
        trace_id: str = None,
        user_id: str = None,
        error: str = None
    ):
        """Log tool execution."""
        level = LogLevel.INFO if status == "success" else LogLevel.WARNING
        self._log(
            level,
            f"Tool {tool_name}: {status}",
            metadata={
                "tool_name": tool_name,
                "tool_status": status,
                "tool_error": error
            },
            trace_id=trace_id,
            user_id=user_id,
            duration_ms=duration_ms
        )

    def log_agent_step(
        self,
        trace_id: str,
        step_name: str,
        status: str,
        duration_ms: int = None,
        metadata: dict = None
    ):
        """Log agent execution step."""
        self.info(
            f"Agent step: {step_name} - {status}",
            trace_id=trace_id,
            duration_ms=duration_ms,
            metadata=metadata or {}
        )

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        user_id: str = None,
        ip_address: str = None,
        details: dict = None
    ):
        """Log security-related event."""
        level = LogLevel.WARNING if severity == "high" else LogLevel.INFO
        self._log(
            level,
            f"Security event: {event_type}",
            metadata={
                "security_event": True,
                "event_type": event_type,
                "severity": severity,
                "ip_address": ip_address,
                "details": details
            },
            user_id=user_id
        )


# Global structured logger instance
structured_logger = StructuredLogger(
    service_name=os.getenv("SERVICE_NAME", "nexus-ai"),
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    output_format=os.getenv("LOG_FORMAT", "json")
)


def get_logger(component: str = None) -> StructuredLogger:
    """Get structured logger instance."""
    if component:
        structured_logger.set_context(component=component)
    return structured_logger
