"""
Context Engine — 可扩展的上下文提供者抽象层。

用法: from app.agent.context_engine import context_engine
      ctx = await context_engine.build_context(user_id, org_id, query)
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class ContextProvider(ABC):
    """上下文提供者基类。"""

    name: str  # 提供者名称
    priority: int = 100  # 优先级（越小越优先，越先被包含在 token 预算内）

    @abstractmethod
    async def get_context(
        self,
        user_id: str,
        org_id: str | None,
        query: str,
        **kwargs: Any,
    ) -> str:
        """返回上下文文本片段。失败或无内容时应返回空字符串。"""
        ...

    def max_tokens(self) -> int:
        """该提供者最多占用的 token 数。"""
        return 500


class ContextEngine:
    """上下文引擎 -- 按优先级和 token 预算组装上下文。"""

    def __init__(self, total_budget: int = 4000):
        self._providers: list[ContextProvider] = []
        self._total_budget = total_budget

    # -- 注册 ----------------------------------------------------------------

    def register(self, provider: ContextProvider) -> None:
        """注册一个 ContextProvider。相同 name 的旧实例会被替换。"""
        self._providers = [p for p in self._providers if p.name != provider.name]
        self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)
        logger.debug(f"[ContextEngine] Registered provider: {provider.name} (priority={provider.priority})")

    def unregister(self, name: str) -> None:
        self._providers = [p for p in self._providers if p.name != name]

    @property
    def providers(self) -> list[ContextProvider]:
        return list(self._providers)

    # -- 组装 ----------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """简单 token 估算: 中英文混合约 len//3。"""
        return len(text) // 3 if text else 0

    async def build_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any,
    ) -> str:
        """按优先级并行获取所有上下文，在 token 预算内拼接。"""
        if not self._providers:
            return ""

        sorted_providers = sorted(self._providers, key=lambda p: p.priority)

        # 并行获取（异常在 _safe_get 内部已处理）
        async def _safe_get(prov: ContextProvider) -> tuple[ContextProvider, str]:
            try:
                text = await prov.get_context(
                    user_id=user_id, org_id=org_id, query=query, **kwargs,
                )
                return prov, text or ""
            except Exception as exc:
                logger.warning(f"[ContextEngine] Provider '{prov.name}' failed: {exc}", exc_info=True)
                return prov, ""

        results = await asyncio.gather(*[_safe_get(p) for p in sorted_providers])

        used_tokens = 0
        parts: list[str] = []

        for provider, text in results:
            if not text:
                continue

            text_tokens = self._estimate_tokens(text)
            provider_budget = provider.max_tokens()

            # 如果该片段超出 provider 自身限额，先截断
            if text_tokens > provider_budget:
                max_chars = provider_budget * 3
                text = text[:max_chars] + "..."
                text_tokens = provider_budget

            # 检查总预算
            if used_tokens + text_tokens > self._total_budget:
                remaining = self._total_budget - used_tokens
                if remaining > 50:
                    text = text[:remaining * 3] + "..."
                    parts.append(f"[{provider.name}]\n{text}")
                break

            parts.append(f"[{provider.name}]\n{text}")
            used_tokens += text_tokens

        logger.info(f"[ContextEngine] Built context: {len(parts)} providers, ~{used_tokens}/{self._total_budget} tokens")
        return "\n\n".join(parts)

# ---------------------------------------------------------------------------
# 内置 Provider
# ---------------------------------------------------------------------------
class ChatHistoryProvider(ContextProvider):
    """从最近 N 轮对话历史构建上下文。"""

    name = "chat_history"
    priority = 10

    def __init__(self, max_turns: int = 10):
        self._max_turns = max_turns

    def max_tokens(self) -> int:
        return 1500

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        session_id: str | None = kwargs.get("session_id")
        if not user_id or not session_id:
            return ""
        try:
            from app.core.database import supabase

            res = (
                await supabase.table("chat_messages")
                .select("role, content")
                .eq("user_id", user_id)
                .eq("session_id", session_id)
                .order("created_at", desc=True)
                .limit(self._max_turns * 2)
                .execute()
            )
            rows = list(reversed(res.data or []))
            if not rows:
                return ""

            # Filter out error/failure assistant responses — they pollute context
            # and make the LLM more likely to output short/refusal responses too.
            _ERROR_PHRASES = ("抱歉，处理您的请求时遇到了问题", "抱歉，系统处理出现异常", "无法满足该请求")
            cleaned_rows = []
            for r in rows:
                content = r.get("content") or ""
                if r.get("role") == "assistant" and any(p in content for p in _ERROR_PHRASES):
                    # Also remove the preceding user message if it exists
                    if cleaned_rows and cleaned_rows[-1].get("role") == "user":
                        cleaned_rows.pop()
                    continue
                cleaned_rows.append(r)
            rows = cleaned_rows
            if not rows:
                return ""

            # Deduplicate repeated conversation turns (user→assistant pairs).
            # Common pattern: user retries same question → gets same cached answer.
            # Previous code only caught consecutive assistant messages, but NOT
            # the more common "same user+assistant pair repeated N times" pattern.
            lines: list[str] = []
            prev_turn_key: tuple[str, str] | None = None
            dup_count = 0
            i = 0
            while i < len(rows):
                r = rows[i]
                content = (r.get("content") or "")[:300]
                if not content:
                    i += 1
                    continue

                role = r.get("role", "")

                if role == "user":
                    # Look ahead for assistant response to form a (user, assistant) pair
                    assistant_content = None
                    if i + 1 < len(rows) and rows[i + 1].get("role") == "assistant":
                        assistant_content = (rows[i + 1].get("content") or "")[:300]

                    if assistant_content:
                        turn_key = (content, assistant_content)
                        if prev_turn_key is not None and turn_key == prev_turn_key:
                            dup_count += 1
                            i += 2  # Skip both user and assistant
                            continue
                        # Flush pending duplicates
                        if dup_count > 0:
                            lines.append(f"（上方对话重复了{dup_count}次，已折叠，请勿重复相同回答）")
                            dup_count = 0
                        lines.append(f"用户: {content}")
                        lines.append(f"助手: {assistant_content}")
                        prev_turn_key = turn_key
                        i += 2
                    else:
                        # User message without following assistant (incomplete turn)
                        if dup_count > 0:
                            lines.append(f"（上方对话重复了{dup_count}次，已折叠，请勿重复相同回答）")
                            dup_count = 0
                        lines.append(f"用户: {content}")
                        prev_turn_key = None
                        i += 1
                else:
                    # Standalone assistant message
                    if dup_count > 0:
                        lines.append(f"（上方对话重复了{dup_count}次，已折叠，请勿重复相同回答）")
                        dup_count = 0
                    lines.append(f"助手: {content}")
                    prev_turn_key = None
                    i += 1

            if dup_count > 0:
                lines.append(f"（上方对话重复了{dup_count}次，已折叠，请勿重复相同回答）")

            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"[ChatHistoryProvider] Failed: {e}")
            return ""


class UserProfileProvider(ContextProvider):
    """获取用户基本信息（角色、部门、偏好）。"""

    name = "user_profile"
    priority = 20

    def max_tokens(self) -> int:
        return 200

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        if not user_id:
            return ""
        try:
            from app.core.database import supabase

            parts: list[str] = []

            user_res = (
                await supabase.table("users")
                .select("full_name, role")
                .eq("id", user_id)
                .maybe_single()
                .execute()
            )
            if user_res.data:
                name = user_res.data.get("full_name", "")
                role = user_res.data.get("role", "employee")
                parts.append(f"用户: {name}（{role}）")

            # 部门信息
            if org_id:
                try:
                    emp_res = (
                        await supabase.table("employees")
                        .select("departments(name)")
                        .eq("user_id", user_id)
                        .eq("organization_id", org_id)
                        .maybe_single()
                        .execute()
                    )
                    if emp_res.data:
                        dept = emp_res.data.get("departments")
                        if isinstance(dept, dict) and dept.get("name"):
                            parts.append(f"部门: {dept['name']}")
                except Exception:
                    pass

            return "，".join(parts) if parts else ""
        except Exception as e:
            logger.debug(f"[UserProfileProvider] Failed: {e}")
            return ""


class SemanticMemoryProvider(ContextProvider):
    """调用 conversation_memories 语义搜索获取长期记忆。"""

    name = "semantic_memory"
    priority = 30

    def max_tokens(self) -> int:
        return 500

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        if not user_id or not query:
            return ""
        try:
            from app.services.conversation_memory_service import conversation_memory_service

            ctx = await conversation_memory_service.build_memory_context(
                user_id=user_id,
                current_query=query,
            )
            return ctx or ""
        except Exception as e:
            logger.debug(f"[SemanticMemoryProvider] Failed: {e}")
            return ""


class KnowledgeBaseProvider(ContextProvider):
    """当查询涉及知识库时，做 RAG 召回。"""

    name = "knowledge_base"
    priority = 50

    def __init__(self, search_limit: int = 3):
        self._search_limit = search_limit

    def max_tokens(self) -> int:
        return 1000

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        if not user_id or not query:
            return ""
        # 只在有 org_id 时才做知识库检索（安全要求）
        if not org_id:
            return ""
        try:
            from app.services.vector_service import vector_service

            result = await vector_service.search(
                query=query,
                user_id=user_id,
                limit=self._search_limit,
                org_id=org_id,
            )
            # vector_service.search 在没有结果时返回 "未找到" 类文本
            if isinstance(result, str) and "未找到" not in result:
                return result
            return ""
        except Exception as e:
            logger.debug(f"[KnowledgeBaseProvider] Failed: {e}")
            return ""


# 模块级单例
context_engine = ContextEngine(total_budget=4000)

context_engine.register(ChatHistoryProvider())
context_engine.register(UserProfileProvider())
context_engine.register(SemanticMemoryProvider())
context_engine.register(KnowledgeBaseProvider())
