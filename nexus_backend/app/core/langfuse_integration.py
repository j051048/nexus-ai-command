"""
Langfuse integration for LLM observability.

P0 Task: Add Langfuse callback handler to track LLM calls.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_langfuse_handler = None


def get_langfuse_handler():
    """Get or create Langfuse callback handler."""
    global _langfuse_handler
    if _langfuse_handler is not None:
        return _langfuse_handler

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        logger.warning("[Langfuse] Keys not set, tracing disabled")
        return None

    try:
        from langfuse.callback import CallbackHandler

        _langfuse_handler = CallbackHandler(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.info(f"[Langfuse] Initialized (host: {host})")
        return _langfuse_handler
    except ImportError:
        logger.error("[Langfuse] Library not installed: pip install langfuse")
        return None
    except Exception as e:
        logger.error(f"[Langfuse] Initialization failed: {e}")
        return None


def create_trace(name: str, user_id: Optional[str] = None, metadata: Optional[dict] = None):
    """Create a new Langfuse trace."""
    handler = get_langfuse_handler()
    if not handler:
        return None

    try:
        trace = handler.trace(
            name=name,
            user_id=user_id,
            metadata=metadata or {},
        )
        return trace
    except Exception as e:
        logger.error(f"[Langfuse] Failed to create trace: {e}")
        return None
