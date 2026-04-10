"""Embedding generation for conversation memories."""

import logging

logger = logging.getLogger(__name__)


async def generate_embedding(
    text: str, org_id: str | None = None
) -> list[float] | None:
    """Generate embedding vector for memory text. Returns None on failure."""
    try:
        from app.services.vector_service import vector_service

        return await vector_service.embed_text(text, org_id or "default")
    except Exception as e:
        logger.debug(f"Embedding generation skipped: {e}")
        return None
