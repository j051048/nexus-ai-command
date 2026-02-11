"""
P2 Enhancement: Centralized Logging Configuration

Provides structured logging with proper formatting for all modules.
Supports different log levels for development and production.
"""

import logging
import sys
import os
from typing import Optional

# Determine environment
IS_PRODUCTION = os.getenv("ENV", "development") in ("production", "prod")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if IS_PRODUCTION else "DEBUG")


def setup_logging(
    level: Optional[str] = None, format_string: Optional[str] = None
) -> None:
    """
    Configure logging for the entire application.

    Call this once at application startup (e.g., in main.py).

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom format string for log messages
    """
    log_level = getattr(logging, (level or LOG_LEVEL).upper(), logging.INFO)

    # Default format includes timestamp, level, module, and message
    default_format = "[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s"

    # Production format: JSON-like for log aggregation tools
    prod_format = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","line":%(lineno)d,"message":"%(message)s"}'

    if format_string:
        log_format = format_string
    elif IS_PRODUCTION:
        log_format = prod_format
    else:
        log_format = default_format

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,  # Override any existing configuration
    )

    # Set specific loggers to appropriate levels
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(
        logging.WARNING if IS_PRODUCTION else logging.INFO
    )

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
        self.logger.info(f"AUTH_SUCCESS user_id={user_id} method={method}")

    def auth_failure(self, reason: str, ip: Optional[str] = None):
        """Log failed authentication attempt"""
        self.logger.warning(f"AUTH_FAILURE reason={reason} ip={ip}")

    def access_denied(self, user_id: str, resource: str, reason: str):
        """Log access denied event"""
        self.logger.warning(
            f"ACCESS_DENIED user_id={user_id} resource={resource} reason={reason}"
        )

    def rate_limited(self, identifier: str, endpoint: str):
        """Log rate limit hit"""
        self.logger.warning(f"RATE_LIMITED identifier={identifier} endpoint={endpoint}")

    def suspicious_activity(self, user_id: Optional[str], activity: str, details: str):
        """Log suspicious activity for investigation"""
        self.logger.error(
            f"SUSPICIOUS_ACTIVITY user_id={user_id} activity={activity} details={details}"
        )

    def security_config(self, event: str, details: str):
        """Log security configuration events"""
        self.logger.info(f"SECURITY_CONFIG event={event} details={details}")


# Singleton instance
security_logger = SecurityLogger()
