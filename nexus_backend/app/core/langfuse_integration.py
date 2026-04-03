"""
Langfuse integration for LLM observability.

Provides both:
1. CallbackHandler for LangChain/LangGraph integration
2. Langfuse client for direct tracing
"""

import logging
import os

logger = logging.getLogger(__name__)

_langfuse_handler = None
_langfuse_client = None


def get_langfuse_handler():
    """Get or create Langfuse callback handler for LangChain/LangGraph."""
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
        logger.info(f"[Langfuse] CallbackHandler initialized (host: {host})")
        return _langfuse_handler
    except ImportError:
        logger.error("[Langfuse] Library not installed: pip install langfuse")
        return None
    except Exception as e:
        logger.error(f"[Langfuse] Initialization failed: {e}")
        return None


def _get_langfuse_client():
    """Get or create the Langfuse client for direct tracing."""
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        return None

    try:
        from langfuse import Langfuse

        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        return _langfuse_client
    except ImportError:
        logger.error("[Langfuse] Library not installed: pip install langfuse")
        return None
    except Exception as e:
        logger.error(f"[Langfuse] Client init failed: {e}")
        return None


def create_trace(name: str, user_id: str | None = None, metadata: dict | None = None):
    """Create a new Langfuse trace using the Langfuse client (NOT the CallbackHandler)."""
    client = _get_langfuse_client()
    if not client:
        return None

    try:
        trace = client.trace(
            name=name,
            user_id=user_id,
            metadata=metadata or {},
        )
        return trace
    except Exception as e:
        logger.error(f"[Langfuse] Failed to create trace: {e}")
        return None
