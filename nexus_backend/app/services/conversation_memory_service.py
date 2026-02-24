"""
Item 13: AI Conversation Memory Enhancement Service

Provides long-term memory capabilities for the AI agent.
Tracks user preferences, explicit memories, and usage patterns
using a rule-based extraction engine (no LLM calls).
"""

import contextlib
import logging
import re
import uuid
from datetime import UTC, datetime
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
        """保存用户记忆条目（upsert by user_id + key）"""
        client = db or supabase
        if not client:
            raise RuntimeError("数据库连接不可用")

        now = datetime.now(UTC).isoformat()

        # Check if key already exists for this user
        existing = (
            await client.table("conversation_memories")
            .select("id, access_count")
            .eq("user_id", user_id)
            .eq("key", key)
            .maybe_single()
            .execute()
        )

        if existing.data:
            # Update existing memory
            result = (
                await client.table("conversation_memories")
                .update(
                    {
                        "value": value,
                        "category": category,
                        "metadata": metadata or {},
                        "importance": importance,
                        "updated_at": now,
                    }
                )
                .eq("id", existing.data["id"])
                .execute()
            )
        else:
            # Insert new memory
            result = (
                await client.table("conversation_memories")
                .insert(
                    {
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
                )
                .execute()
            )

        if not result.data:
            raise RuntimeError("保存记忆失败")

        saved = result.data[0] if isinstance(result.data, list) else result.data
        logger.info(f"Saved memory for user {user_id}: key={key}, category={category}")
        return saved

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
        db: Any = None,
    ) -> list[dict]:
        """搜索相关记忆（基于关键字匹配）"""
        client = db or supabase
        if not client:
            return []

        # Simple keyword-based search using ilike on key and value
        # For production, consider using pg_trgm or full-text search
        memories: list[dict] = []

        try:
            # Search in key field
            result_key = (
                await client.table("conversation_memories")
                .select("*")
                .eq("user_id", user_id)
                .ilike("key", f"%{query}%")
                .limit(limit)
                .execute()
            )
            if result_key.data:
                memories.extend(result_key.data)

            # Search in value field
            seen_ids = {m["id"] for m in memories}
            result_value = (
                await client.table("conversation_memories")
                .select("*")
                .eq("user_id", user_id)
                .ilike("value", f"%{query}%")
                .limit(limit)
                .execute()
            )
            if result_value.data:
                for item in result_value.data:
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

        return memories[:limit]

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

        logger.info(f"Cleared {count} memories for user {user_id}" f"{f' (category={category})' if category else ''}")
        return count

    # ─── 偏好自动提取（规则引擎，不调 LLM）─────────────────────

    async def extract_preferences(
        self,
        user_id: str,
        messages: list[dict[str, str]],
        org_id: str | None = None,
        db: Any = None,
    ) -> list[dict]:
        """
        从对话中自动提取用户偏好。

        提取模式：
        - "我喜欢..." → preference
        - "以后都..." → preference
        - "记住..." → explicit_memory
        - 常用工具/操作 → usage_pattern
        """
        extracted: list[dict] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            # Only extract from user messages
            if role != "user" or not content:
                continue

            # 1) Pattern-based preference extraction
            for pattern_info in PREFERENCE_PATTERNS:
                matches = pattern_info["pattern"].findall(content)
                for match in matches:
                    match_text = match.strip().rstrip("。，,.")
                    if len(match_text) < 2:
                        continue

                    key = f"{pattern_info['key_prefix']}_{uuid.uuid4().hex[:6]}"
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
        """Save an organization-level memory visible to all users in the tenant."""
        client = db or supabase
        if not client:
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
            res = await client.table("org_memories").upsert(
                record, on_conflict="organization_id,category,key"
            ).execute()
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
        """Get organization-level memories."""
        client = db or supabase
        if not client:
            return []
        try:
            query = (
                client.table("org_memories")
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
        """Search organization memories by keyword."""
        client = db or supabase
        if not client:
            return []
        try:
            res = (
                await client.table("org_memories")
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
        """Delete a specific organization memory."""
        client = db or supabase
        if not client:
            return False
        try:
            await (
                client.table("org_memories")
                .delete()
                .eq("id", memory_id)
                .eq("organization_id", org_id)
                .execute()
            )
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
        """Build organization memory context string for injection into system prompt."""
        if not org_id:
            return ""

        parts: list[str] = []

        # Get org-wide preferences/rules
        prefs = await self.get_org_memories(org_id, category="preference", limit=20, db=db)
        if prefs:
            parts.append("## 组织规则和偏好")
            for m in prefs:
                parts.append(f"- {m['key']}: {m['value']}")

        # Get org knowledge
        knowledge = await self.get_org_memories(org_id, category="knowledge", limit=20, db=db)
        if knowledge:
            parts.append("## 组织共享知识")
            for m in knowledge:
                parts.append(f"- {m['key']}: {m['value']}")

        # If there's a query, search for relevant memories
        if query:
            relevant = await self.search_org_memories(org_id, query, limit=5, db=db)
            # Filter out duplicates already in prefs/knowledge
            existing_keys = {m["key"] for m in prefs + knowledge}
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
        1. 获取高重要性偏好记忆
        2. 搜索与当前查询相关的记忆
        3. 格式化为上下文字符串
        """
        context_parts: list[str] = []

        # 1) High-importance preferences (top 5)
        preferences = await self.get_memories(
            user_id=user_id,
            category="preference",
            limit=5,
            db=db,
        )
        if preferences:
            pref_lines = [f"- {m['value']}" for m in preferences]
            context_parts.append("用户偏好:\n" + "\n".join(pref_lines))

        # 2) Explicit memories (top 3)
        explicit = await self.get_memories(
            user_id=user_id,
            category="explicit_memory",
            limit=3,
            db=db,
        )
        if explicit:
            mem_lines = [f"- {m['value']}" for m in explicit]
            context_parts.append("用户记忆:\n" + "\n".join(mem_lines))

        # 3) Query-relevant memories
        if current_query and len(current_query) >= 2:
            relevant = await self.search_memories(
                user_id=user_id,
                query=current_query,
                limit=3,
                db=db,
            )
            if relevant:
                # Deduplicate against already included memories
                existing_ids = {m["id"] for m in preferences + explicit}
                new_relevant = [m for m in relevant if m["id"] not in existing_ids]
                if new_relevant:
                    rel_lines = [f"- {m['value']}" for m in new_relevant]
                    context_parts.append("相关记忆:\n" + "\n".join(rel_lines))

        if not context_parts:
            return ""

        return "[用户记忆上下文 - 以下信息来自该用户的历史交互]\n" + "\n\n".join(context_parts) + "\n[记忆上下文结束]"


# Global service instance
conversation_memory_service = ConversationMemoryService()
