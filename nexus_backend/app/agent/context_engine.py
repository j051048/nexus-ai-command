"""
Context Engine — 可扩展的上下文提供者抽象层。

用法: from app.agent.context_engine import context_engine
      ctx = await context_engine.build_context(user_id, org_id, query)
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import UTC
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

    from app.core.config import settings as _settings

    _BUDGET_RATIO = _settings.CONTEXT_BUDGET_RATIO
    _MIN_BUDGET = _settings.CONTEXT_MIN_BUDGET
    _MAX_BUDGET = _settings.CONTEXT_MAX_BUDGET

    def __init__(self, total_budget: int = 4000):
        self._providers: list[ContextProvider] = []
        self._total_budget = total_budget

    def _budget_for_model(self, context_window: int | None) -> int:
        """Return a request-scoped token budget for a model context window."""
        if not context_window or context_window <= 0:
            return self._total_budget
        new_budget = int(context_window * self._BUDGET_RATIO)
        return max(self._MIN_BUDGET, min(new_budget, self._MAX_BUDGET))

    def adjust_budget_for_model(self, context_window: int | None) -> int:
        """Compatibility helper that no longer mutates the singleton budget."""
        return self._budget_for_model(context_window)

    # -- 注册 ----------------------------------------------------------------

    def register(self, provider: ContextProvider) -> None:
        """注册一个 ContextProvider。相同 name 的旧实例会被替换。"""
        self._providers = [p for p in self._providers if p.name != provider.name]
        self._providers.append(provider)
        self._providers.sort(key=lambda p: p.priority)
        logger.debug(
            f"[ContextEngine] Registered provider: {provider.name} (priority={provider.priority})"
        )

    def unregister(self, name: str) -> None:
        self._providers = [p for p in self._providers if p.name != name]

    @property
    def providers(self) -> list[ContextProvider]:
        return list(self._providers)

    # -- 组装 ----------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Token 估算 — 委托给 TokenCounter 统一实现。"""
        from app.services.token_service import token_counter

        return token_counter.count_tokens(text)

    async def build_context(
        self,
        user_id: str,
        org_id: str | None,
        query: str,
        context_window: int | None = None,
        context_ledger=None,
        **kwargs: Any,
    ) -> str:
        """按优先级并行获取所有上下文，在 token 预算内拼接。"""
        if not self._providers:
            return ""

        sorted_providers = sorted(self._providers, key=lambda p: p.priority)
        total_budget = self._budget_for_model(context_window)
        if context_ledger is not None:
            context_ledger.total_budget = total_budget
            context_ledger.model_context_window = context_window

        # 并行获取（异常在 _safe_get 内部已处理）
        async def _safe_get(prov: ContextProvider) -> tuple[ContextProvider, str]:
            try:
                text = await prov.get_context(
                    user_id=user_id,
                    org_id=org_id,
                    query=query,
                    **kwargs,
                )
                return prov, text or ""
            except Exception as exc:
                logger.warning(
                    f"[ContextEngine] Provider '{prov.name}' failed: {exc}",
                    exc_info=True,
                )
                return prov, ""

        results = await asyncio.gather(*[_safe_get(p) for p in sorted_providers])

        scored_results = []
        for provider, text in results:
            quality = None
            if not text:
                if context_ledger is not None:
                    from app.agent.context_ledger import ContextLedgerEntry

                    context_ledger.add(
                        ContextLedgerEntry(
                            provider=provider.name,
                            priority=provider.priority,
                            tokens_estimated=0,
                            included=False,
                            truncated_reason="empty",
                        )
                    )
                continue

            try:
                from app.services.context_quality import context_quality_service

                quality = context_quality_service.score_context_block(
                    provider=provider.name,
                    text=text,
                    query=query,
                    org_id=org_id,
                    user_id=user_id,
                )
            except Exception:
                quality = None

            priority_score = 1.0 / (1.0 + max(provider.priority, 0) / 20.0)
            if quality is not None:
                utility = (
                    float(quality.relevance) * 0.35
                    + float(quality.authority) * 0.30
                    + float(quality.freshness) * 0.15
                    + float(quality.quality_score) * 0.15
                    + priority_score * 0.05
                )
            else:
                utility = 0.55 + priority_score * 0.25
            scored_results.append((utility, provider, text, quality))

        scored_results.sort(key=lambda item: (-item[0], item[1].priority, item[1].name))

        used_tokens = 0
        parts: list[str] = []

        for utility, provider, text, quality in scored_results:

            text_tokens = self._estimate_tokens(text)
            provider_budget = provider.max_tokens()
            original_text = text
            truncated_reason = None

            # 如果该片段超出 provider 自身限额，先截断
            if text_tokens > provider_budget:
                max_chars = provider_budget * 3
                text = text[:max_chars] + "..."
                text_tokens = provider_budget
                truncated_reason = "provider_budget"

            # 检查总预算
            if used_tokens + text_tokens > total_budget:
                remaining = total_budget - used_tokens
                if remaining > 50:
                    text = text[: remaining * 3] + "..."
                    parts.append(f"[{provider.name}]\n{text}")
                    used_tokens += remaining
                    if context_ledger is not None:
                        from app.agent.context_ledger import (
                            ContextLedgerEntry,
                            estimate_pii_level,
                        )

                        context_ledger.add(
                            ContextLedgerEntry(
                                provider=provider.name,
                                priority=provider.priority,
                                tokens_estimated=remaining,
                                included=True,
                                evidence_ids=quality.evidence_ids if quality else [],
                                relevance=quality.relevance if quality else None,
                                authority=quality.authority if quality else None,
                                freshness_score=quality.freshness if quality else None,
                                quality_score=(
                                    quality.quality_score if quality else None
                                ),
                                permission_scope=(
                                    quality.permission_scope if quality else None
                                ),
                                conflict_flag=(
                                    quality.conflict_flag if quality else False
                                ),
                                pii_level=estimate_pii_level(text),
                                truncated_reason="total_budget",
                                notes={"sample": text[:160], "utility": utility},
                            )
                        )
                elif context_ledger is not None:
                    from app.agent.context_ledger import ContextLedgerEntry

                    context_ledger.add(
                        ContextLedgerEntry(
                            provider=provider.name,
                            priority=provider.priority,
                            tokens_estimated=text_tokens,
                            included=False,
                            evidence_ids=quality.evidence_ids if quality else [],
                            relevance=quality.relevance if quality else None,
                            authority=quality.authority if quality else None,
                            freshness_score=quality.freshness if quality else None,
                            quality_score=quality.quality_score if quality else None,
                            permission_scope=(
                                quality.permission_scope if quality else None
                            ),
                            conflict_flag=(quality.conflict_flag if quality else False),
                            truncated_reason="global_budget",
                            notes={"utility": utility},
                        )
                    )
                continue

            parts.append(f"[{provider.name}]\n{text}")
            used_tokens += text_tokens
            if context_ledger is not None:
                from app.agent.context_ledger import (
                    ContextLedgerEntry,
                    estimate_pii_level,
                )

                context_ledger.add(
                    ContextLedgerEntry(
                        provider=provider.name,
                        priority=provider.priority,
                        tokens_estimated=text_tokens,
                        included=True,
                        evidence_ids=quality.evidence_ids if quality else [],
                        relevance=quality.relevance if quality else None,
                        authority=quality.authority if quality else None,
                        freshness_score=quality.freshness if quality else None,
                        quality_score=quality.quality_score if quality else None,
                        permission_scope=quality.permission_scope if quality else None,
                        conflict_flag=quality.conflict_flag if quality else False,
                        pii_level=estimate_pii_level(original_text),
                        truncated_reason=truncated_reason,
                        notes={"sample": original_text[:160], "utility": utility},
                    )
                )

        logger.info(
            f"[ContextEngine] Built context: {len(parts)} providers, ~{used_tokens}/{total_budget} tokens"
        )
        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# 内置 Provider
# ---------------------------------------------------------------------------
class ChatHistoryProvider(ContextProvider):
    """从最近 N 轮对话历史构建上下文。"""

    name = "你与用户的历史对话"
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

            # Deduplicate rows — DB may contain duplicate messages from retries or multi-org overlap
            seen = set()
            deduped_rows = []
            for r in rows:
                key = (r.get("role", ""), (r.get("content") or "")[:200])
                if key not in seen:
                    seen.add(key)
                    deduped_rows.append(r)
            rows = deduped_rows

            # Filter out error/failure/refusal assistant responses — they pollute
            # context and make the LLM copy the refusal pattern instead of working.
            _ERROR_PHRASES = (
                "抱歉，处理您的请求时遇到了问题",
                "抱歉，系统处理出现异常",
                "无法满足该请求",
                "抱歉，我无法提供",  # generic refusals
                "抱歉，我无法执行",
                "抱歉，我目前无法",
                "请稍后重试",
            )
            # Clean up output_scanner false positive residue in DB
            _SCANNER_RESIDUE = (
                "[检测到提示注入]",
                "[prompt injection detected]",
            )
            cleaned_rows = []
            for r in rows:
                content = r.get("content") or ""
                if r.get("role") == "assistant" and any(
                    p in content for p in _ERROR_PHRASES
                ):
                    # Also remove the preceding user message if it exists
                    if cleaned_rows and cleaned_rows[-1].get("role") == "user":
                        cleaned_rows.pop()
                    continue
                # Strip scanner residue from content (don't discard the whole message)
                for residue in _SCANNER_RESIDUE:
                    if residue in content:
                        content = content.replace(residue, "")
                        r = {**r, "content": content}
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
                            lines.append(
                                f"（上方对话重复了{dup_count}次，已折叠，请勿重复相同回答）"
                            )
                            dup_count = 0
                        lines.append(f"用户: {content}")
                        lines.append(f"助手: {assistant_content}")
                        prev_turn_key = turn_key
                        i += 2
                    else:
                        # User message without following assistant (incomplete turn)
                        if dup_count > 0:
                            lines.append(
                                f"（上方对话重复了{dup_count}次，已折叠，请勿重复相同回答）"
                            )
                            dup_count = 0
                        lines.append(f"用户: {content}")
                        prev_turn_key = None
                        i += 1
                else:
                    # Standalone assistant message
                    if dup_count > 0:
                        lines.append(
                            f"（上方对话重复了{dup_count}次，已折叠，请勿重复相同回答）"
                        )
                        dup_count = 0
                    lines.append(f"助手: {content}")
                    prev_turn_key = None
                    i += 1

            if dup_count > 0:
                lines.append(
                    f"（上方对话重复了{dup_count}次，已折叠，请勿重复相同回答）"
                )

            if not lines:
                return ""

            header = (
                "以下是你与该用户之前的对话记录，你亲身参与了这些对话。"
                "当用户询问「你帮我做过什么」「你还记得吗」等回忆性问题时，"
                "请根据这些记录如实回答，这些都是你真实完成的工作。"
            )
            return f"{header}\n\n" + "\n".join(lines)
        except Exception as e:
            logger.error(f"[ChatHistoryProvider] Failed: {e}")
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
                .select("name, role")
                .eq("id", user_id)
                .limit(1)
                .execute()
            )
            if user_res.data:
                name = user_res.data[0].get("name", "")
                role = user_res.data[0].get("role", "employee")
                parts.append(f"用户: {name}（{role}）")

            # 部门信息
            if org_id:
                try:
                    emp_res = (
                        await supabase.table("users")
                        .select("department")
                        .eq("id", user_id)
                        .maybe_single()
                        .execute()
                    )
                    if emp_res.data:
                        dept_name = emp_res.data.get("department")
                        if dept_name:
                            parts.append(f"部门: {dept_name}")
                except Exception:
                    pass

            return "，".join(parts) if parts else ""
        except Exception as e:
            logger.error(f"[UserProfileProvider] Failed: {e}")
            return ""


class SemanticMemoryProvider(ContextProvider):
    """调用 conversation_memories 语义搜索获取长期记忆。"""

    name = "用户长期记忆"
    priority = 30

    def max_tokens(self) -> int:
        return 500

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        if not user_id or not query:
            return ""
        try:
            from app.services.conversation_memory_service import (
                conversation_memory_service,
            )

            ctx = await conversation_memory_service.build_memory_context(
                user_id=user_id,
                current_query=query,
            )
            return ctx or ""
        except Exception as e:
            logger.error(f"[SemanticMemoryProvider] Failed: {e}")
            return ""


class KnowledgeBaseProvider(ContextProvider):
    """P1b: Two-layer knowledge loading.

    Layer 1 (this provider): Injects a lightweight skill index into context,
    telling the agent WHAT knowledge domains are available.

    Layer 2 (load_knowledge tool): Agent actively loads full content on demand.

    This replaces the old approach of eagerly injecting RAG results into
    every request, which wasted tokens when the query didn't need KB content.
    """

    name = "knowledge_base"
    priority = 50

    def __init__(self, search_limit: int = 3):
        self._search_limit = search_limit

    def max_tokens(self) -> int:
        return 200  # Reduced from 1000 — index is much smaller than full RAG

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        if not user_id or not query:
            return ""
        # Only inject index when org has a knowledge base
        if not org_id:
            return ""
        try:
            from app.tools.load_knowledge_tool import build_skill_index_prompt

            return build_skill_index_prompt()
        except Exception as e:
            logger.error(f"[KnowledgeBaseProvider] Failed to build skill index: {e}")
            return ""


class BusinessGraphContextProvider(ContextProvider):
    """Inject lightweight customer/project/contract/action graph context."""

    name = "business_context_graph"
    priority = 35

    def max_tokens(self) -> int:
        return 700

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        if not org_id:
            return ""
        try:
            from app.core.database import supabase
            from app.services.business_context_graph import build_business_context_graph

            graph = await build_business_context_graph(
                supabase,
                org_id=org_id,
                user_id=user_id,
                role=kwargs.get("user_role"),
            )
            return graph.get("prompt_context") or ""
        except Exception as e:
            logger.error(f"[BusinessGraphContextProvider] Failed: {e}")
            return ""


class CompletedTasksProvider(ContextProvider):
    """跨会话已完成任务注入，让 AI 记住"帮用户做过什么"。"""

    name = "已完成任务"
    priority = 15  # ChatHistory(10) 之后, UserProfile(20) 之前

    def max_tokens(self) -> int:
        return 300

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        if not user_id:
            return ""
        try:
            from datetime import datetime, timedelta

            from app.core.database import supabase

            since = (datetime.now(UTC) - timedelta(days=3)).isoformat()
            result = (
                await supabase.table("agent_tasks")
                .select("title, context_summary, updated_at")
                .eq("user_id", user_id)
                .eq("status", "done")
                .gte("updated_at", since)
                .order("updated_at", desc=True)
                .limit(10)
                .execute()
            )
            tasks = result.data or []
            if not tasks:
                return ""

            lines = [
                "以下是你近期为该用户完成的任务，当用户询问「你帮我做过什么」时请据实回答："
            ]
            for t in tasks:
                date_str = (t.get("updated_at") or "")[:10]
                title = t.get("title", "")
                summary = (t.get("context_summary") or "")[:80]
                line = f"- [{date_str}] {title}"
                if summary:
                    line += f"（{summary}）"
                lines.append(line)
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"[CompletedTasksProvider] Failed: {e}")
            return ""


class BusinessRuleProvider(ContextProvider):
    """注入组织级业务规则，让 Agent 在执行工具前自动遵守企业约束。"""

    name = "业务规则"
    priority = 12  # ChatHistory(10) 之后, CompletedTasks(15) 之前

    def max_tokens(self) -> int:
        return 400

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        if not org_id:
            return ""
        try:
            from app.core.database import supabase

            result = (
                await supabase.table("conversation_memories")
                .select("key, value, recurrence_count")
                .eq("organization_id", org_id)
                .eq("category", "business_rule")
                .is_("superseded_by", "null")
                .order("importance", desc=True)
                .order("recurrence_count", desc=True)
                .limit(10)
                .execute()
            )
            rules = result.data or []
            if not rules:
                return ""

            lines = ["以下是本组织的业务规则，你在执行任何操作时必须遵守："]
            for r in rules:
                count = r.get("recurrence_count") or 1
                prefix = f"[验证×{count}] " if count >= 3 else ""
                lines.append(f"- {prefix}{r['key']}: {r['value']}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"[BusinessRuleProvider] Failed: {e}")
            return ""


class CorrectionHistoryProvider(ContextProvider):
    """注入用户对 Agent 步骤的纠偏历史，避免重复犯错。"""

    name = "历史纠偏"
    priority = 25  # UserProfile(20) 之后, SemanticMemory(30) 之前

    def max_tokens(self) -> int:
        return 300

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        if not user_id:
            return ""
        try:
            from app.core.database import supabase

            result = (
                await supabase.table("ai_feedback")
                .select("metadata, created_at")
                .eq("user_id", user_id)
                .eq("rating", "negative")
                .not_.is_("metadata", "null")
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            )
            rows = result.data or []
            corrections = []
            for r in rows:
                meta = r.get("metadata") or {}
                if meta.get("type") == "step_correction":
                    corrections.append(meta)

            if not corrections:
                return ""

            lines = ["以下是用户之前对你执行步骤的纠偏记录，请避免重复同类错误："]
            for c in corrections[:5]:
                lines.append(
                    f"- 步骤{c.get('step_index', '?')}: {c.get('correction_text', '')}"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"[CorrectionHistoryProvider] Failed: {e}")
            return ""


class SoulDocumentProvider(ContextProvider):
    """注入企业灵魂文档，定义 AI 的核心人格。最高优先级。"""

    name = "灵魂文档"
    priority = 1  # 最高优先级

    def max_tokens(self) -> int:
        return 600

    async def get_context(
        self, user_id: str, org_id: str | None, query: str, **kwargs: Any
    ) -> str:
        if not org_id:
            return ""
        try:
            from app.services.soul_document_service import soul_document_service

            return await soul_document_service.get_compiled_prompt(org_id) or ""
        except Exception as e:
            logger.error(f"[SoulDocumentProvider] Failed: {e}")
            return ""


# 模块级单例
context_engine = ContextEngine(total_budget=4000)

context_engine.register(SoulDocumentProvider())
context_engine.register(ChatHistoryProvider())
context_engine.register(BusinessRuleProvider())
context_engine.register(CompletedTasksProvider())
# UserProfileProvider 已由 memory.py:prepare_initial_state() 第488行覆盖，跳过避免重复注入
# context_engine.register(UserProfileProvider())
context_engine.register(CorrectionHistoryProvider())
# SemanticMemoryProvider 已由 memory.py:prepare_initial_state() 第554行覆盖，跳过避免重复注入
# context_engine.register(SemanticMemoryProvider())
context_engine.register(BusinessGraphContextProvider())
context_engine.register(KnowledgeBaseProvider())
