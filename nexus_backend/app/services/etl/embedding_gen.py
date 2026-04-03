"""
ETL - Embedding Generation Module

Contains semantic chunking, chunk enrichment, and batch embedding generation logic.
"""

import json
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


async def _enrich_chunks(
    chunks: list[str],
    parent_text: str,
    api_key: str,
    base_url: str,
    client: httpx.AsyncClient,
) -> list[str]:
    """P2: 对 child chunks 做滑动窗口上下文增强。

    用 mini 模型批量处理：代词消解 + 隐含上下文补全。
    增强后的文本用于生成 embedding，提高检索命中率。
    失败时返回原始 chunks（非致命）。
    """
    if not chunks:
        return chunks

    # Only enrich chunks that are likely to have pronoun/context issues
    # Skip very short chunks or chunks that are self-contained
    enrichable = [(i, c) for i, c in enumerate(chunks) if len(c) > 80]
    if not enrichable:
        return chunks

    # Batch: group into batches of 10 to avoid token limits
    enriched = list(chunks)  # copy
    batch_size = 10
    parent_summary = parent_text[:500] if len(parent_text) > 500 else parent_text

    for batch_start in range(0, len(enrichable), batch_size):
        batch = enrichable[batch_start : batch_start + batch_size]
        chunks_text = "\n---\n".join(f"[chunk_{idx}]\n{text}" for idx, text in batch)

        prompt = (
            "你是文档预处理助手。下面是一篇文档的摘要和若干片段。"
            "请对每个片段做最小改动，使其独立可理解：\n"
            "1. 将代词（他/她/它/该/这个/那个）替换为具体名词\n"
            "2. 如果片段开头缺少主语或上下文，从摘要中补充一句简短背景\n"
            "3. 不要改变原意、不要添加新信息、不要翻译\n\n"
            f"[文档摘要]\n{parent_summary}\n\n"
            f"[片段列表]\n{chunks_text}\n\n"
            '按JSON数组返回增强后的片段，格式: ["chunk_0增强文本", "chunk_1增强文本", ...]'
        )

        try:
            from app.core.config import settings as app_settings

            mini_model = getattr(app_settings, "AI_MINI_MODEL", "gpt-4o-mini")

            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": mini_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 4000,
                },
                timeout=30.0,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                # Extract JSON array from response
                json_match = re.search(r"\[.*\]", content, re.DOTALL)
                if json_match:
                    results = json.loads(json_match.group())
                    for j, (orig_idx, _) in enumerate(batch):
                        if j < len(results) and isinstance(results[j], str) and len(results[j]) > 20:
                            enriched[orig_idx] = results[j]
            else:
                logger.debug(f"[ETL] Chunk enrichment API returned {resp.status_code}")
        except Exception as e:
            logger.error(f"[ETL] Chunk enrichment batch failed (non-fatal): {e}")

    return enriched


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
        logger.error("[ETL] Embedding config resolution failed, using defaults")

    async with httpx.AsyncClient(timeout=60.0) as shared_client:

        async def _process_batch(batch_texts, chunk_type="child", parent_chunk_ids=None, enriched_texts=None):
            """Embed a batch of texts and insert into DB."""
            try:
                # Use enriched texts for embedding if available, original for content
                embed_inputs = enriched_texts if enriched_texts else batch_texts
                payload = {"model": embedding_model, "input": embed_inputs, "dimensions": 1536}
                headers = {"Authorization": f"Bearer {active_api_key}"}
                resp = await shared_client.post(f"{active_base_url}/embeddings", headers=headers, json=payload)
                if resp.status_code == 200:
                    embeddings_data = resp.json()["data"]
                    records = []
                    for i, item in enumerate(embeddings_data):
                        record = {
                            "document_id": doc_id,
                            "content": batch_texts[i],  # Always store original content
                            "embedding": item["embedding"],
                            "metadata": {"source": filename},
                            "organization_id": organization_id,
                            "chunk_type": chunk_type,
                        }
                        # P2: Store enriched content if different from original
                        if enriched_texts and i < len(enriched_texts) and enriched_texts[i] != batch_texts[i]:
                            record["enriched_content"] = enriched_texts[i]
                        if parent_chunk_ids and i < len(parent_chunk_ids) and parent_chunk_ids[i]:
                            record["parent_chunk_id"] = parent_chunk_ids[i]
                        records.append(record)
                    try:
                        res = await supabase.table("document_embeddings").insert(records).execute()
                    except Exception as insert_err:
                        # Fallback: if enriched_content column doesn't exist
                        if "enriched_content" in str(insert_err):
                            for r in records:
                                r.pop("enriched_content", None)
                            res = await supabase.table("document_embeddings").insert(records).execute()
                        else:
                            raise
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

        # Generate child chunks with per-record parent references + P2 enrichment
        current_batch_text = []
        for parent_id, parent_text in parent_ids:
            child_chunks = list(semantic_chunk(parent_text, size=chunk_size, overlap=chunk_overlap))

            # P2: Enrich child chunks with parent context before embedding
            try:
                enriched_chunks = await _enrich_chunks(
                    child_chunks, parent_text, active_api_key, active_base_url, shared_client
                )
            except Exception:
                enriched_chunks = child_chunks

            for i, chunk in enumerate(child_chunks):
                enriched = enriched_chunks[i] if i < len(enriched_chunks) else chunk
                current_batch_text.append((chunk, parent_id, enriched))
                if len(current_batch_text) >= batch_size:
                    texts = [c[0] for c in current_batch_text]
                    pids = [c[1] for c in current_batch_text]
                    enr_texts = [c[2] for c in current_batch_text]
                    if not await _process_batch(
                        texts, chunk_type="child", parent_chunk_ids=pids, enriched_texts=enr_texts
                    ):
                        all_success = False
                    current_batch_text = []

        if current_batch_text:
            texts = [c[0] for c in current_batch_text]
            pids = [c[1] for c in current_batch_text]
            enr_texts = [c[2] for c in current_batch_text]
            if not await _process_batch(texts, chunk_type="child", parent_chunk_ids=pids, enriched_texts=enr_texts):
                all_success = False

    return all_success
