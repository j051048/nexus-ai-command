"""
P2 Enhancement: Centralized Logging Configuration

Provides structured logging with proper formatting for all modules.
Supports different log levels for development and production.
"""

import json as _json
import logging
import os
import sys
from datetime import UTC, datetime

# Determine environment
IS_PRODUCTION = os.getenv("ENV", "development") in ("production", "prod")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if IS_PRODUCTION else "DEBUG")


class _JSONFormatter(logging.Formatter):
    """JSON-safe log formatter that properly escapes message content.

    Prevents broken JSON when log messages contain quotes, newlines, or
    other special characters that would break naive %-style JSON templates.

    Includes trace_id, user_id, org_id when available on the log record,
    as well as module/function/line for production log aggregation.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # Include exception info if present
        if record.exc_info and record.exc_info[1]:
            log_obj["exception"] = self.formatException(record.exc_info)
        # Include tracing / tenant context fields
        if hasattr(record, "trace_id") and record.trace_id:
            log_obj["trace_id"] = record.trace_id
        if hasattr(record, "user_id") and record.user_id:
            log_obj["user_id"] = record.user_id
        if hasattr(record, "org_id") and record.org_id:
            log_obj["org_id"] = record.org_id
        # Include extra fields from structured logging (e.g., SecurityLogger)
        for key in ("resource", "ip", "event", "activity"):
            val = getattr(record, key, None)
            if val is not None:
                log_obj[key] = val
        return _json.dumps(log_obj, ensure_ascii=False)


def setup_logging(level: str | None = None, format_string: str | None = None, json_output: bool | None = None) -> None:
    """
    Configure logging for the entire application.

    Call this once at application startup (e.g., in main.py).

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string for log messages
        json_output: Force JSON output (True/False). Defaults to auto-detect
                     (JSON in production, human-readable in development).
    """
    log_level = getattr(logging, (level or LOG_LEVEL).upper(), logging.INFO)

    # Default format includes timestamp, level, module, and message
    default_format = "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s"

    log_format = format_string if format_string else default_format

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,  # Override any existing configuration
    )

    # Determine if JSON formatting should be used
    use_json = json_output if json_output is not None else IS_PRODUCTION

    # Production (or explicit json_output): Replace root handler with JSON-safe formatter
    if use_json and not format_string:
        json_formatter = _JSONFormatter()
        for handler in logging.root.handlers:
            handler.setFormatter(json_formatter)

    # Set specific loggers to appropriate levels
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING if IS_PRODUCTION else logging.INFO)

    # P0 Security: Prevent HTTP/2 libraries from leaking sensitive headers
    # (Authorization, apikey) in DEBUG logs
    logging.getLogger("hpack").setLevel(logging.WARNING)
    logging.getLogger("h2").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Supabase / PostgREST client noise
    logging.getLogger("supabase").setLevel(logging.WARNING)
    logging.getLogger("postgrest").setLevel(logging.WARNING)
    logging.getLogger("gotrue").setLevel(logging.WARNING)
    logging.getLogger("realtime").setLevel(logging.WARNING)

    # Ensure our app loggers use the configured level
    logging.getLogger("app").setLevel(log_level)

    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={log_level}, production={IS_PRODUCTION}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    Usage:
        from app.core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")

    Args:
        name: Logger name, typically __name__ of the module

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class SecurityLogger:
    """
    Specialized logger for security-related events.

    Provides methods for logging authentication, authorization,
    and other security events with appropriate context.
    """

    def __init__(self):
        self.logger = logging.getLogger("app.security")

    def auth_success(self, user_id: str, method: str = "jwt"):
        """Log successful authentication"""
        self.logger.info("AUTH_SUCCESS", extra={"user_id": user_id, "event": f"method={method}"})

    def auth_failure(self, reason: str, ip: str | None = None):
        """Log failed authentication attempt"""
        self.logger.warning("AUTH_FAILURE", extra={"ip": ip, "event": f"reason={reason}"})

    def access_denied(self, user_id: str, resource: str, reason: str):
        """Log access denied event"""
        self.logger.warning(
            "ACCESS_DENIED", extra={"user_id": user_id, "resource": resource, "event": f"reason={reason}"}
        )

    def rate_limited(self, identifier: str, endpoint: str):
        """Log rate limit hit"""
        self.logger.warning("RATE_LIMITED", extra={"event": f"identifier={identifier} endpoint={endpoint}"})

    def suspicious_activity(self, user_id: str | None, activity: str, details: str):
        """Log suspicious activity for investigation"""
        self.logger.error(
            "SUSPICIOUS_ACTIVITY", extra={"user_id": user_id, "activity": activity, "event": f"details={details}"}
        )

    def security_config(self, event: str, details: str):
        """Log security configuration events"""
        self.logger.info("SECURITY_CONFIG", extra={"event": f"{event}: {details}"})


# Singleton instance
security_logger = SecurityLogger()
