"""
ETL - Embedding Generation Module

Contains semantic chunking and batch embedding generation logic.
"""

import logging
import re

import httpx

from app.core.database import supabase

logger = logging.getLogger(__name__)


def semantic_chunk(text: str, size: int = 600, overlap: int = 100):
    """
    Improved chunking strategy.
    Tries to split by double newlines (paragraphs) first, then falls back
    to sliding window if paragraphs are too large.
    """
    text = re.sub(r"\n{3,}", "\n\n", text)
    paragraphs = text.split("\n\n")

    current_chunk = ""

    for p in paragraphs:
        if len(p) > size:
            if current_chunk:
                yield current_chunk
                current_chunk = ""

            start = 0
            while start < len(p):
                end = start + size
                chunk = p[start:end]
                yield chunk
                start += size - overlap
        else:
            if len(current_chunk) + len(p) < size:
                current_chunk += ("\n\n" if current_chunk else "") + p
            else:
                if current_chunk:
                    yield current_chunk
                current_chunk = p

    if current_chunk:
        yield current_chunk


async def generate_embeddings(
    text: str,
    doc_id: str,
    filename: str,
    api_key: str,
    base_url: str,
    organization_id: str = None,
    default_embedding_model: str = "text-embedding-3-large",
    chunk_size: int = 600,
    chunk_overlap: int = 100,
) -> bool:
    """
    Batch Embeddings with partial success tracking.

    Performance optimizations:
    - Reuse a single httpx.AsyncClient across all batches
    - Batch parent chunk embeddings
    - Correctly assign parent_id per-record when a batch spans multiple parents
    """
    batch_size = 50
    all_success = True

    # Resolve embedding model dynamically via gateway
    embedding_model = default_embedding_model
    active_api_key = api_key
    active_base_url = base_url
    try:
        from app.services.llm_helpers import resolve_embedding_config

        emb_config = await resolve_embedding_config(organization_id or "default")
        if emb_config.get("model"):
            embedding_model = emb_config["model"]
        if emb_config.get("api_key"):
            active_api_key = emb_config["api_key"]
        if emb_config.get("base_url"):
            active_base_url = emb_config["base_url"].rstrip("/")
            if "/v1" not in active_base_url and "api.openai.com" not in active_base_url:
                active_base_url = f"{active_base_url}/v1"
    except Exception:
        logger.debug("[ETL] Embedding config resolution failed, using defaults")

    async with httpx.AsyncClient(timeout=60.0) as shared_client:

        async def _process_batch(batch_texts, chunk_type="child", parent_chunk_ids=None):
            """Embed a batch of texts and insert into DB."""
            try:
                payload = {"model": embedding_model, "input": batch_texts, "dimensions": 1536}
                headers = {"Authorization": f"Bearer {active_api_key}"}
                resp = await shared_client.post(f"{active_base_url}/embeddings", headers=headers, json=payload)
                if resp.status_code == 200:
                    embeddings_data = resp.json()["data"]
                    records = []
                    for i, item in enumerate(embeddings_data):
                        record = {
                            "document_id": doc_id,
                            "content": batch_texts[i],
                            "embedding": item["embedding"],
                            "metadata": {"source": filename},
                            "organization_id": organization_id,
                            "chunk_type": chunk_type,
                        }
                        if parent_chunk_ids and i < len(parent_chunk_ids) and parent_chunk_ids[i]:
                            record["parent_chunk_id"] = parent_chunk_ids[i]
                        records.append(record)
                    res = await supabase.table("document_embeddings").insert(records).execute()
                    return [r["id"] for r in (res.data or [])] if res.data else True
                logger.warning(f"[ETL] Embedding API returned {resp.status_code}: {resp.text[:200]}")
                return False
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
                return False

        # Parent-Document Retriever: create parent chunks first, then children
        from app.core.config import settings as app_settings

        parent_chunk_size = getattr(app_settings, "RAG_PARENT_CHUNK_SIZE", 1800)

        # Generate parent chunks (large context)
        parent_chunks = list(semantic_chunk(text, size=parent_chunk_size, overlap=200))
        parent_ids = []

        for batch_start in range(0, len(parent_chunks), batch_size):
            batch = parent_chunks[batch_start : batch_start + batch_size]
            result = await _process_batch(batch, chunk_type="parent")
            if isinstance(result, list):
                for idx, db_id in enumerate(result):
                    parent_ids.append((db_id, batch[idx]))
            else:
                all_success = False
                for pt in batch:
                    parent_ids.append((None, pt))

        # Generate child chunks with per-record parent references
        current_batch_text = []
        for parent_id, parent_text in parent_ids:
            child_chunks = list(semantic_chunk(parent_text, size=chunk_size, overlap=chunk_overlap))
            for chunk in child_chunks:
                current_batch_text.append((chunk, parent_id))
                if len(current_batch_text) >= batch_size:
                    texts = [c[0] for c in current_batch_text]
                    pids = [c[1] for c in current_batch_text]
                    if not await _process_batch(texts, chunk_type="child", parent_chunk_ids=pids):
                        all_success = False
                    current_batch_text = []

        if current_batch_text:
            texts = [c[0] for c in current_batch_text]
            pids = [c[1] for c in current_batch_text]
            if not await _process_batch(texts, chunk_type="child", parent_chunk_ids=pids):
                all_success = False

    return all_success
