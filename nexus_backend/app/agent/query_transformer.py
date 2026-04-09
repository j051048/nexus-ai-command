"""
Query Transformer — HyDE, Multi-Query expansion, and LLM-based reranking for RAG.

Extracted from memory.py for modularity.

Implements:
  QueryTransformer: HyDE + Multi-Query + Query Rewriting
  llm_rerank: LLM-based document relevance reranking
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.state import AgentConfig

logger = logging.getLogger(__name__)


class QueryTransformer:
    """
    P1 Fix #22: Query Transformation for better RAG retrieval.

    Implements:
    1. HyDE (Hypothetical Document Embeddings)
    2. Multi-Query expansion
    3. Query rewriting for better semantic matching
    """

    def __init__(self, config: "AgentConfig"):
        self.config = config
        self._llm_client = None
        self._resolved_model = None

    async def _get_llm(self):
        """Lazy load LLM client, resolving via LLM gateway when available."""
        if self._llm_client is None:
            try:
                from openai import AsyncOpenAI

                from app.core.config import settings

                # Try gateway resolution first
                try:
                    from app.services.llm_helpers import resolve_model_config

                    resolved = await resolve_model_config(
                        org_id=getattr(self.config, "org_id", None) or "default",
                    )
                    api_key = resolved.get("api_key") or self.config.api_key or settings.OPENAI_API_KEY
                    base_url = resolved.get("base_url") or self.config.base_url or settings.AI_BASE_URL

                    if not api_key:
                        logger.warning("[QueryTransformer] No API key found in prompt resolution, config, or settings")

                    self._llm_client = AsyncOpenAI(
                        api_key=api_key,
                        base_url=base_url,
                    )
                    self._resolved_model = resolved.get("model", self.config.mini_model)
                    return self._llm_client
                except Exception:
                    logger.debug("LLM gateway model config unavailable, using default fallback")

                # Fallback to config explicitly or global settings
                api_key = self.config.api_key or settings.OPENAI_API_KEY
                base_url = self.config.base_url or settings.AI_BASE_URL
                self._llm_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            except Exception as e:
                logger.warning(f"Failed to init LLM for query transformation: {e}", exc_info=True)
        return self._llm_client

    async def generate_hyde(self, query: str) -> str:
        """
        Generate a hypothetical document that would answer the query.
        This document is then used for embedding search.
        """
        llm = await self._get_llm()
        if not llm:
            return query

        prompt = f"""请模拟用户在对话中提到这个问题时的自然表达方式，生成一段简短的对话片段。

用户问题: {query}

要求:
1. 使用口语化、自然的表达（而非专业术语或百科风格）
2. 模拟真实聊天记忆的碎片化特征
3. 长度约100-150字
4. 直接输出对话片段，不要解释

对话片段:"""

        try:
            response = await llm.chat.completions.create(
                model=self._resolved_model or self.config.mini_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,
            )
            hyde_doc = response.choices[0].message.content.strip()
            logger.debug(f"[HyDE] Generated hypothetical doc: {hyde_doc[:100]}...")
            return hyde_doc
        except Exception as e:
            logger.warning(f"HyDE generation failed: {e}", exc_info=True)
            return query

    async def expand_multi_query(self, query: str, num_queries: int = 3) -> list[str]:
        """
        Generate multiple related queries for better retrieval coverage.
        """
        llm = await self._get_llm()
        if not llm:
            return [query]

        prompt = f"""请根据用户的问题，生成{num_queries}个语义相近但表达方式不同的问题。
这些问题将用于检索相关知识，以提高检索的全面性。

原问题: {query}

要求:
1. 保持原问题的核心意图
2. 使用不同的词汇和表达方式
3. 覆盖不同的检索角度
4. 每个问题一行，不要编号

生成的问题:"""

        try:
            response = await llm.chat.completions.create(
                model=self._resolved_model or self.config.mini_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.5,
            )
            expanded = response.choices[0].message.content.strip().split("\n")
            expanded = [q.strip() for q in expanded if q.strip()][:num_queries]

            # Always include original query
            all_queries = [query] + expanded
            logger.debug(f"[MultiQuery] Generated {len(all_queries)} query variants")
            return all_queries
        except Exception as e:
            logger.warning(f"Multi-query expansion failed: {e}", exc_info=True)
            return [query]

    async def rewrite_query(self, query: str, messages: list[dict] | None = None) -> str:
        """
        Rewrite query for better semantic matching.
        Supports context-aware rewriting with recent conversation history.
        """
        llm = await self._get_llm()
        if not llm:
            return query

        # 构建对话上下文（最近 3 轮）用于代词消解
        context_block = ""
        if messages:
            recent = messages[-6:]  # 最近 3 轮（每轮 user+assistant）
            context_lines = []
            for msg in recent:
                role = msg.get("role", "")
                content = (msg.get("content") or "")[:150]
                if role in ("user", "assistant") and content:
                    context_lines.append(f"{'用户' if role == 'user' else 'AI'}: {content}")
            if context_lines:
                context_block = "\n对话上下文:\n" + "\n".join(context_lines) + "\n"

        prompt = f"""请将以下问题重写为更适合检索的形式。
{context_block}
当前日期: {datetime.now().strftime('%Y-%m-%d')}

原问题: {query}

要求:
1. 保留核心信息需求
2. 使用更标准、更清晰的表达
3. 移除口语化表达
4. 如果问题中有代词（那个/这个/上次/之前），根据上下文替换为具体指代内容
5. 将相对时间（昨天/上周/前天/上个月）转换为绝对日期 YYYY-MM-DD
6. 添加可能的关键词
7. 直接输出重写后的问题

重写后的问题:"""

        try:
            response = await llm.chat.completions.create(
                model=self._resolved_model or self.config.mini_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.2,
            )
            rewritten = response.choices[0].message.content.strip()
            logger.debug(f"[QueryRewrite] '{query}' -> '{rewritten}'")
            return rewritten
        except Exception as e:
            logger.warning(f"Query rewriting failed: {e}", exc_info=True)
            return query


async def llm_rerank(query: str, docs: list[dict], config: "AgentConfig", top_k: int = 3) -> list[dict]:
    """用 mini_model 对 RAG 文档打相关性分（0-10），取 top_k。

    超时 5s，失败返回原始 docs。
    """
    if len(docs) <= top_k:
        return docs

    from openai import AsyncOpenAI

    try:
        from app.core.config import settings
        api_key = config.api_key or settings.OPENAI_API_KEY
        base_url = config.base_url or settings.AI_BASE_URL
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        doc_list = "\n".join(f"[{i}] {doc.get('content', '')[:200]}" for i, doc in enumerate(docs))
        prompt = (
            f"用户问题: {query}\n\n"
            f"以下是检索到的文档片段，请对每个片段与用户问题的相关性打分（0-10），"
            f"只输出 JSON 数组，格式如 [8, 3, 7, ...]:\n\n{doc_list}"
        )
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=config.mini_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0,
            ),
            timeout=5.0,
        )
        raw = resp.choices[0].message.content.strip()
        arr_match = re.search(r"\[[\d\s,\.]+\]", raw)
        if arr_match:
            scores = json.loads(arr_match.group())
            if len(scores) == len(docs):
                ranked = sorted(zip(scores, docs, strict=False), key=lambda x: x[0], reverse=True)
                return [doc for _, doc in ranked[:top_k]]
    except Exception as e:
        logger.error(f"[LLMRerank] Failed, returning original docs: {e}")

    return docs[:top_k]
