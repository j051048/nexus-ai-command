"""
P0 (JP Morgan AskDavid 借鉴): 推理轨迹记忆 (Reasoning Trace Memory)

存储完整推理路径（意图 → 规划步骤 → 工具链 → 反思结果 → 最终方案），
当类似问题再次出现时可直接复用历史推理路径，减少规划耗时。

设计要点:
- 复用 conversation_memories 表 (category='reasoning_trace')，无需新建表
- 存储时生成 embedding，检索时走语义匹配
- 轨迹只存成功 (outcome=success) 的推理路径
- 匹配后作为 planning prompt 的参考，不强制采纳
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_TRACE_CATEGORY = "reasoning_trace"
_MAX_TRACES_PER_ORG = 200  # 每组织最多存储的轨迹数
_SEMANTIC_THRESHOLD = 0.80  # 语义匹配阈值（比 skill 严格一些）


def _intent_hash(intent: str) -> str:
    """生成意图指纹用于去重。"""
    return hashlib.md5(intent.strip().lower().encode()).hexdigest()[:12]


class ReasoningTraceStore:
    """推理轨迹的存储与检索。"""

    async def save_trace(
        self,
        *,
        user_id: str,
        org_id: str | None,
        intent_summary: str,
        complexity: str,
        plan_steps: list[str],
        tool_chain: list[dict],
        outcome: str,
        iterations: int,
        key_decisions: list[str] | None = None,
        duration_ms: int = 0,
        db: Any = None,
    ) -> bool:
        """持久化一条成功的推理轨迹。

        只保存 outcome="success" 的轨迹，失败轨迹由 learning_system 处理。
        """
        if outcome != "success" or not intent_summary or not tool_chain:
            return False

        # SIMPLE 查询不值得记录轨迹
        if complexity and complexity.upper() == "SIMPLE":
            return False

        # 至少 2 个工具调用才有规划价值
        if len(tool_chain) < 2:
            return False

        if not db:
            from app.core.database import supabase
            db = supabase
        if not db:
            return False

        trace_key = f"trace:{_intent_hash(intent_summary)}"

        # 构建轨迹数据
        trace_data = {
            "intent_summary": intent_summary[:300],
            "complexity": complexity,
            "plan_steps": plan_steps[:10],  # 最多保留 10 步
            "tool_chain": [
                {
                    "tool": tc.get("tool_name", ""),
                    "status": tc.get("status", "success"),
                    "param_keys": list(tc.get("tool_args", {}).keys())
                    if isinstance(tc.get("tool_args"), dict)
                    else [],
                }
                for tc in tool_chain[:10]
            ],
            "outcome": outcome,
            "iterations": iterations,
            "key_decisions": (key_decisions or [])[:5],
            "duration_ms": duration_ms,
            "created_at": datetime.now(UTC).isoformat(),
            "use_count": 1,
        }

        try:
            # 生成 embedding
            embedding = None
            try:
                from app.services.conversation_memory.embedding import generate_embedding
                embedding = await generate_embedding(intent_summary, org_id)
            except Exception as e:
                logger.debug(f"[ReasoningTrace] Embedding generation skipped: {e}")

            # 检查是否已存在相同意图的轨迹
            existing = (
                await db.table("conversation_memories")
                .select("id, metadata")
                .eq("user_id", user_id)
                .eq("key", trace_key)
                .eq("category", _TRACE_CATEGORY)
                .limit(1)
                .execute()
            )

            if existing.data:
                # 已存在 → 更新（增加 use_count）
                old_meta = existing.data[0].get("metadata") or {}
                trace_data["use_count"] = old_meta.get("use_count", 0) + 1
                new_importance = min(0.90, 0.55 + trace_data["use_count"] * 0.05)

                update_data = {
                    "value": json.dumps(trace_data, ensure_ascii=False),
                    "metadata": trace_data,
                    "importance": new_importance,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                if embedding is not None:
                    update_data["embedding"] = embedding

                await (
                    db.table("conversation_memories")
                    .update(update_data)
                    .eq("id", existing.data[0]["id"])
                    .execute()
                )
                logger.info(
                    f"[ReasoningTrace] Updated trace: {intent_summary[:40]} "
                    f"(use_count={trace_data['use_count']})"
                )
            else:
                # 新轨迹 → 先淘汰，再插入
                await self._evict_if_needed(db, user_id, org_id)

                insert_data = {
                    "user_id": user_id,
                    "organization_id": org_id,
                    "category": _TRACE_CATEGORY,
                    "key": trace_key,
                    "value": json.dumps(trace_data, ensure_ascii=False),
                    "metadata": trace_data,
                    "importance": 0.55,
                }
                if embedding is not None:
                    insert_data["embedding"] = embedding

                await db.table("conversation_memories").insert(insert_data).execute()
                logger.info(
                    f"[ReasoningTrace] Saved new trace: {intent_summary[:40]} "
                    f"({len(trace_data['tool_chain'])} tools, {iterations} iterations)"
                )

            return True

        except Exception as e:
            logger.warning(f"[ReasoningTrace] Failed to save trace: {e}")
            return False

    async def match_trace(
        self,
        *,
        query: str,
        user_id: str,
        org_id: str | None,
        complexity: str | None = None,
        db: Any = None,
    ) -> dict | None:
        """根据用户查询语义匹配历史推理轨迹。

        Returns:
            匹配到的 trace_data dict（含 confidence），或 None
        """
        if not query or not db:
            return None

        # SIMPLE 查询不需要历史轨迹
        if complexity and complexity.upper() == "SIMPLE":
            return None

        try:
            from app.services.conversation_memory.embedding import generate_embedding

            query_embedding = await generate_embedding(query, org_id)
            if not query_embedding:
                return None

            params: dict[str, Any] = {
                "query_embedding": query_embedding,
                "match_user_id": user_id,
                "match_limit": 5,
            }
            if org_id:
                params["match_org_id"] = org_id

            result = await db.rpc("search_memories_by_embedding", params).execute()
            if not result.data:
                return None

            for row in result.data:
                if row.get("category") != _TRACE_CATEGORY:
                    continue
                similarity = row.get("similarity", 0.0)
                if similarity < _SEMANTIC_THRESHOLD:
                    continue

                # 可选：按复杂度过滤（避免把 MODERATE 的轨迹推给 CRITICAL 任务）
                try:
                    trace_data = json.loads(row.get("value", "{}"))
                except (json.JSONDecodeError, TypeError):
                    trace_data = row.get("metadata") or {}

                if not trace_data:
                    continue

                trace_data["confidence"] = round(similarity, 2)
                trace_data["trace_key"] = row.get("key", "")

                logger.info(
                    f"[ReasoningTrace] Matched trace: "
                    f"{trace_data.get('intent_summary', '')[:40]} "
                    f"(similarity={similarity:.2f})"
                )
                return trace_data

        except Exception as e:
            logger.debug(f"[ReasoningTrace] Match failed: {e}")

        return None

    def trace_to_planning_hint(self, trace: dict) -> str:
        """将匹配到的推理轨迹转换为 planning 提示文本。"""
        intent = trace.get("intent_summary", "类似任务")
        confidence = trace.get("confidence", 0)
        use_count = trace.get("use_count", 0)
        iterations = trace.get("iterations", 0)

        lines = [
            f"[历史推理轨迹] 检测到与「{intent}」相似的任务 "
            f"(置信度: {confidence}, 历史复用: {use_count}次)",
        ]

        # 展示规划步骤
        plan_steps = trace.get("plan_steps", [])
        if plan_steps:
            lines.append("历史规划路径:")
            for i, step in enumerate(plan_steps[:5], 1):
                lines.append(f"  {i}. {step}")

        # 展示工具链
        tool_chain = trace.get("tool_chain", [])
        if tool_chain:
            tools = [tc.get("tool", "?") for tc in tool_chain]
            lines.append(f"成功工具链: {' → '.join(tools)}")

        # 展示关键决策
        decisions = trace.get("key_decisions", [])
        if decisions:
            lines.append("关键决策:")
            for d in decisions[:3]:
                lines.append(f"  • {d}")

        if iterations > 1:
            lines.append(f"（历史执行: {iterations} 轮迭代）")

        lines.append(
            "你可以参考此历史路径，也可以根据当前上下文调整方案。"
        )
        return "\n".join(lines)

    async def _evict_if_needed(
        self, db: Any, user_id: str, org_id: str | None
    ) -> None:
        """按组织维度淘汰最旧最少用的轨迹。"""
        try:
            query = (
                db.table("conversation_memories")
                .select("id", count="exact")
                .eq("category", _TRACE_CATEGORY)
            )
            if org_id:
                query = query.eq("organization_id", org_id)
            else:
                query = query.eq("user_id", user_id)

            count_result = await query.execute()
            if not count_result.count or count_result.count < _MAX_TRACES_PER_ORG:
                return

            # 淘汰 importance 最低 + 最旧的
            evict_query = (
                db.table("conversation_memories")
                .select("id")
                .eq("category", _TRACE_CATEGORY)
                .order("importance", desc=False)
                .order("updated_at", desc=False)
                .limit(1)
            )
            if org_id:
                evict_query = evict_query.eq("organization_id", org_id)
            else:
                evict_query = evict_query.eq("user_id", user_id)

            oldest = await evict_query.execute()
            if oldest.data:
                await (
                    db.table("conversation_memories")
                    .delete()
                    .eq("id", oldest.data[0]["id"])
                    .execute()
                )
                logger.debug("[ReasoningTrace] Evicted oldest trace to stay within limit")
        except Exception as e:
            logger.debug(f"[ReasoningTrace] Eviction check skipped: {e}")


# 全局单例
reasoning_trace_store = ReasoningTraceStore()
