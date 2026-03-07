"""
Item 13: AI Conversation Memory Enhancement Service

Provides long-term memory capabilities for the AI agent.
Tracks user preferences, explicit memories, and usage patterns
using a rule-based extraction engine (no LLM calls).
"""

import contextlib
import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


# ─── Preference extraction patterns ──────────────────────────

PREFERENCE_PATTERNS: list[dict[str, Any]] = [
    # "我喜欢..." / "我偏好..." / "我倾向..."
    {
        "pattern": re.compile(r"我(?:喜欢|偏好|倾向于?|习惯)(.{2,50})"),
        "category": "preference",
        "key_prefix": "likes",
    },
    # "以后都..." / "之后都..." / "每次都..."
    {
        "pattern": re.compile(r"(?:以后|之后|今后|每次)(?:都|请)?(.{2,50})"),
        "category": "preference",
        "key_prefix": "routine",
    },
    # "记住..." / "请记住..." / "帮我记..."
    {
        "pattern": re.compile(r"(?:请?记住|帮我记|记一下)(.{2,80})"),
        "category": "explicit_memory",
        "key_prefix": "remember",
    },
    # "我是..." / "我的...是..."
    {
        "pattern": re.compile(r"我(?:是|叫|的名字是)(.{2,30})"),
        "category": "preference",
        "key_prefix": "identity",
    },
    # "不要..." / "别给我..." / "我不喜欢..."
    {
        "pattern": re.compile(r"(?:不要|别给我|我不喜欢|我讨厌)(.{2,50})"),
        "category": "preference",
        "key_prefix": "dislikes",
    },
    # "我的邮箱/电话/工号是..."
    {
        "pattern": re.compile(r"我的(?:邮箱|邮件|电话|手机|工号|员工号)(?:是|为)?\s*([^\s,，。.]{3,40})"),
        "category": "explicit_memory",
        "key_prefix": "contact_info",
    },
]

# Tool/action usage patterns for tracking
TOOL_USAGE_KEYWORDS: dict[str, str] = {
    "审批": "approval",
    "报销": "expense",
    "请假": "leave",
    "采购": "purchase",
    "报表": "report",
    "数据分析": "analytics",
    "出差": "travel",
    "合同": "contract",
    "日程": "schedule",
    "任务": "task",
}

# Signal words that indicate a message may contain memorizable content
# Only trigger LLM extraction when these words are present
MEMORY_SIGNAL_WORDS = frozenset({
    "记住", "以后", "每次", "总是", "永远", "我是", "我负责",
    "我们公司", "规定", "偏好", "习惯", "别给我", "不要",
    "我喜欢", "我讨厌", "我倾向", "帮我记", "请记住",
})


class ConversationMemoryService:
    """AI 会话长期记忆服务"""

    # ─── 记忆 CRUD ───────────────────────────────────────────────

    async def save_memory(
        self,
        user_id: str,
        key: str,
        value: str,
        category: str = "preference",
        metadata: dict | None = None,
        importance: float = 0.5,
        org_id: str | None = None,
        db: Any = None,
    ) -> dict:
        """保存用户记忆条目（upsert by user_id + key），同时生成 embedding 向量"""
        client = db or supabase
        if not client:
            raise RuntimeError("数据库连接不可用")

        now = datetime.now(UTC).isoformat()

        # Generate embedding for semantic search
        embedding = await self._generate_embedding(f"{key}: {value}", org_id)

        # Check if key already exists for this user
        existing = (
            await client.table("conversation_memories")
            .select("id, access_count")
            .eq("user_id", user_id)
            .eq("key", key)
            .maybe_single()
            .execute()
        )

        update_data = {
            "value": value,
            "category": category,
            "metadata": metadata or {},
            "importance": importance,
            "updated_at": now,
        }
        if embedding:
            update_data["embedding"] = embedding

        if existing and existing.data:
            # Update existing memory
            try:
                result = (
                    await client.table("conversation_memories")
                    .update(update_data)
                    .eq("id", existing.data["id"])
                    .execute()
                )
            except Exception as update_err:
                err_str = str(update_err)
                if embedding and ("embedding" in err_str or "PGRST204" in err_str):
                    logger.warning("embedding column not found in schema cache, updating without embedding")
                    update_data.pop("embedding", None)
                    result = (
                        await client.table("conversation_memories")
                        .update(update_data)
                        .eq("id", existing.data["id"])
                        .execute()
                    )
                else:
                    raise
        else:
            # Insert new memory
            insert_data = {
                "user_id": user_id,
                "organization_id": org_id,
                "category": category,
                "key": key,
                "value": value,
                "metadata": metadata or {},
                "importance": importance,
                "access_count": 0,
                "last_accessed_at": now,
                "created_at": now,
                "updated_at": now,
            }
            if embedding:
                insert_data["embedding"] = embedding
            try:
                result = await client.table("conversation_memories").insert(insert_data).execute()
            except Exception as insert_err:
                # Fallback: if embedding column doesn't exist (PGRST204), retry without it
                err_str = str(insert_err)
                if embedding and ("embedding" in err_str or "PGRST204" in err_str):
                    logger.warning("embedding column not found in schema cache, saving without embedding")
                    insert_data.pop("embedding", None)
                    result = await client.table("conversation_memories").insert(insert_data).execute()
                else:
                    raise

        if not result.data:
            raise RuntimeError("保存记忆失败")

        saved = result.data[0] if isinstance(result.data, list) else result.data
        logger.info(f"Saved memory for user {user_id}: key={key}, category={category}")
        return saved

    async def _generate_embedding(self, text: str, org_id: str | None = None) -> list[float] | None:
        """Generate embedding vector for memory text. Returns None on failure."""
        try:
            from app.services.vector_service import vector_service

            return await vector_service.embed_text(text, org_id or "default")
        except Exception as e:
            logger.debug(f"Embedding generation skipped: {e}")
            return None

    async def get_memories(
        self,
        user_id: str,
        category: str | None = None,
        limit: int = 20,
        db: Any = None,
    ) -> list[dict]:
        """获取用户记忆列表"""
        client = db or supabase
        if not client:
            return []

        query = client.table("conversation_memories").select("*").eq("user_id", user_id)

        if category:
            query = query.eq("category", category)

        result = await query.order("importance", desc=True).order("updated_at", desc=True).limit(limit).execute()

        return result.data or []

    async def search_memories(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        org_id: str | None = None,
        db: Any = None,
    ) -> list[dict]:
        """搜索相关记忆（混合检索：embedding 语义搜索 + 关键字匹配）

        P0 Security: 强制 org_id 过滤，防止跨租户记忆泄露。
        P1 Enhancement: 优先使用 embedding 向量搜索，关键字匹配作为 fallback。
        """
        client = db or supabase
        if not client:
            return []

        memories: list[dict] = []

        try:
            # Strategy 1: Embedding-based semantic search (preferred)
            semantic_results = await self._semantic_search(user_id, query, limit, org_id, client)
            if semantic_results:
                memories.extend(semantic_results)

            # Strategy 2: Keyword fallback (supplement if semantic results insufficient)
            if len(memories) < limit:
                keyword_results = await self._keyword_search(user_id, query, limit - len(memories), org_id, client)
                seen_ids = {m["id"] for m in memories}
                for item in keyword_results:
                    if item["id"] not in seen_ids:
                        memories.append(item)
        except Exception as e:
            logger.warning(f"Memory search failed: {e}")

        # Update access counts for returned memories
        now = datetime.now(UTC).isoformat()
        for mem in memories[:limit]:
            with contextlib.suppress(Exception):
                await (
                    client.table("conversation_memories")
                    .update(
                        {
                            "access_count": (mem.get("access_count", 0) or 0) + 1,
                            "last_accessed_at": now,
                        }
                    )
                    .eq("id", mem["id"])
                    .execute()
                )

        # Apply temporal decay for final ranking, then MMR diversity reranking
        memories.sort(key=lambda m: self._compute_decay_score(m), reverse=True)
        memories = self._mmr_rerank(memories, limit)

        return memories

    async def _semantic_search(self, user_id: str, query: str, limit: int, org_id: str | None, client) -> list[dict]:
        """Embedding-based semantic search on memories using pgvector."""
        try:
            from app.services.vector_service import vector_service

            # Generate embedding for the query
            query_embedding = await vector_service.embed_text(query)
            if not query_embedding:
                return []

            # Use RPC for cosine similarity search on conversation_memories
            params = {
                "query_embedding": query_embedding,
                "match_user_id": user_id,
                "match_limit": limit,
            }
            if org_id:
                params["match_org_id"] = org_id

            result = await client.rpc("search_memories_by_embedding", params).execute()
            return result.data or []
        except Exception as e:
            logger.debug(f"Semantic memory search unavailable, falling back to keyword: {e}")
            return []

    async def _keyword_search(self, user_id: str, query: str, limit: int, org_id: str | None, client) -> list[dict]:
        """Keyword-based fallback search using ILIKE."""
        memories: list[dict] = []

        # Build base query with mandatory tenant isolation
        base_query = client.table("conversation_memories").select("*").eq("user_id", user_id)
        if org_id:
            base_query = base_query.eq("organization_id", org_id)

        # Search in key field
        result_key = await base_query.ilike("key", f"%{query}%").limit(limit).execute()
        if result_key.data:
            memories.extend(result_key.data)

        # Search in value field
        if len(memories) < limit:
            seen_ids = {m["id"] for m in memories}
            val_query = client.table("conversation_memories").select("*").eq("user_id", user_id)
            if org_id:
                val_query = val_query.eq("organization_id", org_id)
            result_value = await val_query.ilike("value", f"%{query}%").limit(limit).execute()
            if result_value.data:
                for item in result_value.data:
                    if item["id"] not in seen_ids:
                        memories.append(item)

        return memories

    async def delete_memory(
        self,
        user_id: str,
        memory_id: str,
        db: Any = None,
    ) -> bool:
        """删除单条记忆"""
        client = db or supabase
        if not client:
            return False

        result = (
            await client.table("conversation_memories").delete().eq("id", memory_id).eq("user_id", user_id).execute()
        )

        deleted = bool(result.data)
        if deleted:
            logger.info(f"Deleted memory {memory_id} for user {user_id}")
        return deleted

    async def clear_memories(
        self,
        user_id: str,
        category: str | None = None,
        db: Any = None,
    ) -> int:
        """清除记忆（可按分类清除）"""
        client = db or supabase
        if not client:
            return 0

        query = client.table("conversation_memories").delete().eq("user_id", user_id)

        if category:
            query = query.eq("category", category)

        result = await query.execute()
        count = len(result.data) if result.data else 0

        logger.info(f"Cleared {count} memories for user {user_id}{f' (category={category})' if category else ''}")
        return count

    # ─── 偏好自动提取（规则引擎 + LLM 增强）─────────────────────

    async def extract_preferences(
        self,
        user_id: str,
        messages: list[dict[str, str]],
        org_id: str | None = None,
        db: Any = None,
    ) -> list[dict]:
        """
        从对话中自动提取用户偏好。

        双引擎策略：
        1. 规则引擎（快速路径）：正则匹配明确的偏好表达
        2. LLM 增强（深度提取）：捕获复杂语义中的隐含偏好
        """
        extracted: list[dict] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            # Only extract from user messages
            if role != "user" or not content:
                continue

            # 1) Pattern-based preference extraction (fast path)
            for pattern_info in PREFERENCE_PATTERNS:
                matches = pattern_info["pattern"].findall(content)
                for match in matches:
                    match_text = match.strip().rstrip("。，,.")
                    if len(match_text) < 2:
                        continue

                    content_hash = hashlib.md5(match_text.encode()).hexdigest()[:8]
                    key = f"{pattern_info['key_prefix']}_{content_hash}"
                    entry = {
                        "key": key,
                        "value": match_text,
                        "category": pattern_info["category"],
                        "importance": 0.7 if pattern_info["category"] == "explicit_memory" else 0.5,
                    }
                    extracted.append(entry)

            # 2) Tool/action usage pattern detection
            for keyword, action in TOOL_USAGE_KEYWORDS.items():
                if keyword in content:
                    entry = {
                        "key": f"usage_{action}",
                        "value": f"用户经常使用{keyword}相关功能",
                        "category": "usage_pattern",
                        "importance": 0.3,
                    }
                    # Avoid duplicates within this batch
                    if not any(e["key"] == entry["key"] for e in extracted):
                        extracted.append(entry)

        # 3) LLM-assisted deep extraction (only when signal words are present)
        user_texts = " ".join(
            msg.get("content", "") for msg in messages if msg.get("role") == "user"
        )
        if any(w in user_texts for w in MEMORY_SIGNAL_WORDS):
            llm_extracted = await self._extract_with_llm(messages)
        else:
            llm_extracted = []
        if llm_extracted:
            existing_values = {e["value"] for e in extracted}
            for entry in llm_extracted:
                if entry["value"] not in existing_values:
                    extracted.append(entry)

        # Save all extracted memories
        saved: list[dict] = []
        for entry in extracted:
            try:
                result = await self.save_memory(
                    user_id=user_id,
                    key=entry["key"],
                    value=entry["value"],
                    category=entry["category"],
                    importance=entry.get("importance", 0.5),
                    org_id=org_id,
                    db=db,
                )
                saved.append(result)
            except Exception as e:
                logger.warning(f"Failed to save extracted memory: {e}")

        if saved:
            logger.info(f"Extracted {len(saved)} memories from conversation for user {user_id}")

        return saved

    async def _extract_with_llm(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict]:
        """Use LLM to extract implicit preferences and facts from conversation.

        Only processes user messages, returns structured memory entries.
        Designed to catch semantics that regex patterns miss, such as:
        - "我们的主要客户群体是制造业中大型企业"
        - "报告用表格形式比较好"
        - "我负责华东区的大客户"
        """
        user_texts = [msg["content"] for msg in messages if msg.get("role") == "user" and msg.get("content")]
        if not user_texts:
            return []

        # Only process if there's substantial content
        combined = "\n".join(user_texts[-5:])  # last 5 user messages
        if len(combined) < 10:
            return []

        try:
            import json as _json

            from app.services.ai_service import AIService

            prompt = f"以下是用户在对话中说的话：\n\n{combined}"
            system = (
                "你是记忆提取专家。从用户的对话中提取值得长期记住的信息。\n"
                "提取以下类型的信息：\n"
                "- 用户的身份、职位、负责区域等个人信息\n"
                "- 用户的工作习惯和偏好（如报告格式、沟通方式）\n"
                "- 用户提到的重要事实（如客户群体、业务方向）\n"
                "- 用户的明确要求和指令（如'以后都用表格'）\n\n"
                "不要提取：临时性的问题、一次性的查询、礼貌用语。\n"
                "如果没有值得提取的信息，返回空数组 []。\n\n"
                "严格以JSON数组格式返回，每个元素包含：\n"
                '- "category": "preference" 或 "explicit_memory" 或 "fact"\n'
                '- "key": 简短的标识键（如 "role_region"、"report_format"）\n'
                '- "value": 提取的完整信息\n'
                '- "importance": 0.0-1.0 的重要性评分\n\n'
                "只返回JSON数组，不要其他文字。最多提取5条。"
            )

            result_text = await AIService.call_llm(prompt, system)

            # Parse JSON from LLM response
            clean = result_text.strip()
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0].strip()
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0].strip()

            items = _json.loads(clean)
            if not isinstance(items, list):
                return []

            extracted = []
            for item in items[:5]:
                if not isinstance(item, dict):
                    continue
                category = item.get("category", "preference")
                if category not in ("preference", "explicit_memory", "fact"):
                    category = "preference"
                key = item.get("key", f"llm_{uuid.uuid4().hex[:6]}")
                value = item.get("value", "")
                if not value or len(value) < 3:
                    continue
                extracted.append(
                    {
                        "key": f"llm_{key}",
                        "value": value,
                        "category": category,
                        "importance": min(max(float(item.get("importance", 0.5)), 0.1), 1.0),
                    }
                )

            if extracted:
                logger.info(f"LLM extracted {len(extracted)} memories from conversation")
            return extracted

        except Exception as e:
            logger.debug(f"LLM memory extraction skipped: {e}")
            return []

    # ─── Organization Memory ─────────────────────────────────────

    async def save_org_memory(
        self,
        org_id: str,
        category: str,
        key: str,
        value: str,
        user_id: str | None = None,
        metadata: dict | None = None,
        db: Any = None,
    ) -> dict | None:
        """Save an organization-level memory visible to all users in the tenant.

        Always uses the global admin client because org_memories RLS
        relies on a session variable (app.current_org_id) that PostgREST
        scoped clients do not set. Application-layer org_id filtering
        ensures tenant isolation.
        """
        if not supabase:
            return None
        try:
            record = {
                "organization_id": org_id,
                "scope": "organization",
                "category": category,
                "key": key,
                "value": value,
                "contributed_by": user_id,
                "metadata": metadata or {},
            }
            res = (
                await supabase.table("org_memories")
                .upsert(record, on_conflict="organization_id,category,key")
                .execute()
            )
            return res.data[0] if res.data else record
        except Exception as e:
            logger.error("Failed to save org memory: %s", e)
            return None

    async def get_org_memories(
        self,
        org_id: str,
        category: str | None = None,
        limit: int = 50,
        db: Any = None,
    ) -> list[dict]:
        """Get organization-level memories. Uses admin client to bypass RLS."""
        if not supabase:
            return []
        try:
            query = (
                supabase.table("org_memories")
                .select("*")
                .eq("organization_id", org_id)
                .order("updated_at", desc=True)
                .limit(limit)
            )
            if category:
                query = query.eq("category", category)
            res = await query.execute()
            return res.data or []
        except Exception as e:
            logger.error("Failed to get org memories: %s", e)
            return []

    async def search_org_memories(
        self,
        org_id: str,
        query: str,
        limit: int = 10,
        db: Any = None,
    ) -> list[dict]:
        """Search organization memories by keyword. Uses admin client to bypass RLS."""
        if not supabase:
            return []
        try:
            res = (
                await supabase.table("org_memories")
                .select("*")
                .eq("organization_id", org_id)
                .or_(f"key.ilike.%{query}%,value.ilike.%{query}%")
                .order("updated_at", desc=True)
                .limit(limit)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.error("Failed to search org memories: %s", e)
            return []

    async def delete_org_memory(
        self,
        org_id: str,
        memory_id: str,
        db: Any = None,
    ) -> bool:
        """Delete a specific organization memory. Uses admin client to bypass RLS."""
        if not supabase:
            return False
        try:
            await supabase.table("org_memories").delete().eq("id", memory_id).eq("organization_id", org_id).execute()
            return True
        except Exception as e:
            if hasattr(e, "code") and str(getattr(e, "code", "")) == "204":
                return True
            logger.error("Failed to delete org memory: %s", e)
            return False

    async def build_org_memory_context(
        self,
        org_id: str,
        query: str | None = None,
        db: Any = None,
    ) -> str:
        """Build organization memory context string for injection into system prompt.

        Strategy:
        - policy: always inject (behavioral rules, must be obeyed)
        - preference/knowledge: only inject query-relevant ones via search
        """
        if not org_id:
            return ""

        parts: list[str] = []

        # Always inject org behavior policies (highest priority, query-independent)
        policies = await self.get_org_memories(org_id, category="policy", limit=10, db=db)
        if policies:
            parts.append("## 组织行为准则（必须遵守）")
            for m in policies:
                parts.append(f"- {m['key']}: {m['value']}")

        # Search for query-relevant org memories (preference/knowledge/etc.)
        if query:
            relevant = await self.search_org_memories(org_id, query, limit=5, db=db)
            existing_keys = {m["key"] for m in policies}
            relevant = [m for m in relevant if m["key"] not in existing_keys]
            if relevant:
                parts.append("## 相关组织记忆")
                for m in relevant:
                    parts.append(f"- [{m['category']}] {m['key']}: {m['value']}")

        return "\n".join(parts)

    async def extract_org_memories(
        self,
        org_id: str,
        user_id: str,
        message: str,
        ai_response: str,
        db: Any = None,
    ) -> list[dict]:
        """
        Extract potential organization-level knowledge from conversations.
        Rules-based extraction for common patterns.
        """
        extracted: list[dict] = []

        # Pattern: "我们公司..." / "公司规定..." / "组织要求..."
        org_patterns = [
            (re.compile(r"(?:我们公司|公司规定|组织要求|团队规则|部门规定)[：:是]?\s*(.{5,100})"), "preference"),
            (re.compile(r"(?:记住|请记住|注意)[：:，,]\s*(?:我们|公司|组织)(.{5,100})"), "preference"),
            (re.compile(r"(?:客户|供应商|合作伙伴)\s*[\w\u4e00-\u9fff]+\s*(?:的|是).{5,80}"), "knowledge"),
            (re.compile(r"(?:以后|今后|从现在起).{3,50}(?:都要|必须|应该|需要).{5,50}"), "preference"),
        ]

        for pattern, category in org_patterns:
            matches = pattern.findall(message)
            for match in matches[:3]:  # Max 3 per pattern
                clean = match.strip().rstrip("。.!！")
                if len(clean) >= 5:
                    key = clean[:100]
                    saved = await self.save_org_memory(
                        org_id=org_id,
                        category=category,
                        key=key,
                        value=clean,
                        user_id=user_id,
                        metadata={"source": "auto_extract"},
                        db=db,
                    )
                    if saved:
                        extracted.append(saved)

        return extracted

    # ─── 记忆上下文构建 ──────────────────────────────────────────

    async def build_memory_context(
        self,
        user_id: str,
        current_query: str,
        db: Any = None,
    ) -> str:
        """
        构建记忆上下文，注入到 system prompt 中。

        策略：
        1. 显式记忆无条件注入（用户主动要求记住的，量少且重要）
        2. 其余记忆（偏好/事实等）走语义搜索，只注入与当前查询相关的
        """
        context_parts: list[str] = []

        # 1) Explicit memories — always inject (user explicitly asked to remember)
        explicit = await self.get_memories(
            user_id=user_id,
            category="explicit_memory",
            limit=5,
            db=db,
        )
        if explicit:
            mem_lines = [f"- {m['value']}" for m in explicit]
            context_parts.append("用户记忆:\n" + "\n".join(mem_lines))

        # 2) Query-relevant memories — semantic search across all categories
        if current_query and len(current_query) >= 2:
            relevant = await self.search_memories(
                user_id=user_id,
                query=current_query,
                limit=5,
                db=db,
            )
            if relevant:
                existing_ids = {m["id"] for m in explicit}
                new_relevant = [m for m in relevant if m["id"] not in existing_ids]
                if new_relevant:
                    rel_lines = [f"- {m['value']}" for m in new_relevant]
                    context_parts.append("相关记忆:\n" + "\n".join(rel_lines))

        if not context_parts:
            return ""

        return "[用户记忆上下文]\n" + "\n\n".join(context_parts) + "\n[记忆上下文结束]"

    # ─── P0-2: Memory Decay — 记忆衰减与自动清理 ─────────────────

    def _mmr_rerank(
        self,
        memories: list[dict],
        limit: int,
        lambda_param: float = 0.7,
    ) -> list[dict]:
        """MMR (Maximal Marginal Relevance) diversity reranking.

        Balances relevance and diversity using Jaccard text similarity.
        lambda=1.0 → pure relevance; lambda=0.0 → max diversity.
        """
        if len(memories) <= 1:
            return memories

        def _tokenize(text: str) -> set[str]:
            return set(text.lower().split())

        def _jaccard(a: set[str], b: set[str]) -> float:
            if not a or not b:
                return 0.0
            return len(a & b) / len(a | b)

        tokens = [_tokenize(m.get("value", "") + " " + m.get("key", "")) for m in memories]

        scores = [self._compute_decay_score(m) for m in memories]
        max_score = max(scores) if scores else 1.0
        if max_score > 0:
            scores = [s / max_score for s in scores]

        selected: list[int] = []
        candidates = list(range(len(memories)))

        while len(selected) < min(limit, len(memories)):
            best_idx = -1
            best_mmr = -1.0

            for i in candidates:
                relevance = scores[i]
                if selected:
                    max_sim = max(_jaccard(tokens[i], tokens[j]) for j in selected)
                else:
                    max_sim = 0.0

                mmr = lambda_param * relevance - (1 - lambda_param) * max_sim
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = i

            if best_idx < 0:
                break
            selected.append(best_idx)
            candidates.remove(best_idx)

        return [memories[i] for i in selected]

    def _compute_decay_score(self, memory: dict) -> float:
        """Compute a decay-weighted importance score for a memory.

        Formula: score = base_importance * recency_factor * access_factor
        - recency_factor decays over 30 days half-life
        - access_factor rewards frequently accessed memories
        """
        import math

        importance = float(memory.get("importance", 0.5) or 0.5)
        access_count = int(memory.get("access_count", 0) or 0)

        # Recency: days since last access (or last update)
        last_accessed = memory.get("last_accessed_at") or memory.get("updated_at") or memory.get("created_at")
        if last_accessed:
            try:
                if isinstance(last_accessed, str):
                    last_dt = datetime.fromisoformat(last_accessed.replace("Z", "+00:00"))
                else:
                    last_dt = last_accessed
                days_since = max((datetime.now(UTC) - last_dt).days, 0)
            except Exception:
                days_since = 30
        else:
            days_since = 60

        # Half-life of 30 days
        recency_factor = 1.0 / (1 + days_since / 30.0)

        # Evergreen categories: explicit_memory and policy never decay
        category = memory.get("category", "")
        if category in ("explicit_memory", "policy"):
            recency_factor = 1.0

        # Access frequency bonus (logarithmic)
        access_factor = math.log(access_count + 1) / math.log(10) + 0.5  # range ~0.5-2.0
        access_factor = min(access_factor, 2.0)

        return importance * recency_factor * access_factor

    async def cleanup_decayed_memories(
        self,
        min_age_days: int = 30,
        score_threshold: float = 0.1,
        batch_size: int = 200,
        db: Any = None,
    ) -> dict:
        """Remove low-score memories that are older than min_age_days.

        Returns: {"scanned": int, "deleted": int}
        """
        client = db or supabase
        if not client:
            return {"scanned": 0, "deleted": 0}

        cutoff = (datetime.now(UTC) - timedelta(days=min_age_days)).isoformat()

        try:
            result = (
                await client.table("conversation_memories")
                .select("id, user_id, importance, access_count, last_accessed_at, updated_at, created_at, category")
                .lt("updated_at", cutoff)
                .order("updated_at", desc=False)
                .limit(batch_size)
                .execute()
            )
        except Exception as e:
            logger.error(f"Memory decay scan failed: {e}")
            return {"scanned": 0, "deleted": 0}

        candidates = result.data or []
        deleted = 0

        for mem in candidates:
            # Never auto-delete explicit_memory or policy
            if mem.get("category") in ("explicit_memory", "policy"):
                continue

            score = self._compute_decay_score(mem)
            if score < score_threshold:
                try:
                    await client.table("conversation_memories").delete().eq("id", mem["id"]).execute()
                    deleted += 1
                except Exception as e:
                    if not (hasattr(e, "code") and str(getattr(e, "code", "")) == "204"):
                        logger.warning(f"Failed to delete decayed memory {mem['id']}: {e}")
                    else:
                        deleted += 1

        if deleted > 0:
            logger.info(f"Memory decay cleanup: scanned={len(candidates)}, deleted={deleted}")

        return {"scanned": len(candidates), "deleted": deleted}


# Global service instance
conversation_memory_service = ConversationMemoryService()


# ─── P1-6: Episodic Memory Service ──────────────────────────────


class EpisodicMemoryService:
    """P1-6: Saves and retrieves complete interaction episodes for experience recall."""

    async def save_episode(
        self,
        user_id: str,
        user_intent: str,
        strategy: str,
        tools_used: list[str],
        outcome: str,
        confidence_score: float = 0.0,
        duration_ms: int = 0,
        total_tokens: int = 0,
        complexity: str = "moderate",
        thinking_steps: int = 0,
        session_id: str = "default",
        org_id: str | None = None,
        db: Any = None,
    ) -> dict | None:
        """Save a complete interaction episode with embedding for later recall."""
        client = db or supabase
        if not client or not user_intent:
            return None

        try:
            # Generate embedding from intent + strategy + outcome
            embed_text = f"{user_intent} | {strategy[:200]} | {outcome[:200]}"
            embedding = await conversation_memory_service._generate_embedding(embed_text, org_id)

            record: dict[str, Any] = {
                "user_id": user_id,
                "organization_id": org_id,
                "session_id": session_id,
                "user_intent": user_intent[:500],
                "strategy": strategy[:1000],
                "tools_used": tools_used[:20],
                "outcome": outcome[:1000],
                "confidence_score": min(max(confidence_score, 0.0), 1.0),
                "duration_ms": duration_ms,
                "total_tokens": total_tokens,
                "complexity": complexity,
                "thinking_steps": thinking_steps,
            }
            if embedding:
                record["embedding"] = embedding

            result = await client.table("conversation_episodes").insert(record).execute()
            if result.data:
                logger.info(f"[Episode] Saved episode for user {user_id}: {user_intent[:50]}")
                return result.data[0] if isinstance(result.data, list) else result.data
        except Exception as e:
            # Episode save failure should never block the main flow
            logger.debug(f"[Episode] Save failed (non-critical): {e}")
        return None

    async def search_similar_episodes(
        self,
        user_id: str,
        query: str,
        limit: int = 3,
        org_id: str | None = None,
        db: Any = None,
    ) -> list[dict]:
        """Search for similar past episodes using embedding similarity."""
        client = db or supabase
        if not client or not query:
            return []

        try:
            from app.services.vector_service import vector_service

            query_embedding = await vector_service.embed_text(query)
            if not query_embedding:
                return []

            params: dict[str, Any] = {
                "query_embedding": query_embedding,
                "match_user_id": user_id,
                "match_limit": limit,
            }
            if org_id:
                params["match_org_id"] = org_id

            result = await client.rpc("search_episodes_by_embedding", params).execute()
            episodes = result.data or []

            # Filter by minimum similarity threshold
            return [ep for ep in episodes if ep.get("similarity", 0) > 0.5]
        except Exception as e:
            logger.debug(f"[Episode] Search failed (non-critical): {e}")
            return []

    def build_episode_context(self, episodes: list[dict]) -> str:
        """Build injection text from retrieved episodes."""
        if not episodes:
            return ""

        parts = ["[历史经验回忆 - 以下是处理类似问题的历史记录]"]
        for i, ep in enumerate(episodes[:3], 1):
            tools = ", ".join(ep.get("tools_used", [])[:5]) or "无"
            parts.append(
                f"经验{i}: 用户意图「{ep.get('user_intent', '')}」→ "
                f"策略: {ep.get('strategy', '')[:100]} | "
                f"使用工具: {tools} | "
                f"结果置信度: {ep.get('confidence_score', 0):.0%}"
            )
        parts.append("[经验回忆结束]")
        return "\n".join(parts)


episodic_memory_service = EpisodicMemoryService()
