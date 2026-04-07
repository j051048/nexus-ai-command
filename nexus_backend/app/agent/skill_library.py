"""
P3: 自学习技能循环 (Self-learning Skill Loop)

借鉴 Hermes Agent 的 Skill 系统：
- Agent 执行成功的工具链自动提炼为可复用"技能"模板
- 下次遇到类似意图时，直接匹配技能跳过 planning
- 复用 conversation_memories 表 (category='skill')

技能生命周期:
  extract → store → match → apply → reinforce/decay
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# 技能提炼的最低条件
_MIN_TOOL_CALLS = 2  # 至少 2 个工具调用才值得提炼
_MAX_SKILLS_PER_USER = 50  # 每用户最多保存的技能数
_MATCH_THRESHOLD = 0.75  # 关键词匹配阈值
_SEMANTIC_THRESHOLD = 0.78  # 语义向量匹配阈值
_SKILL_CATEGORY = "skill"


def _make_intent_hash(intent: str) -> str:
    """生成意图指纹，用于去重。"""
    normalized = intent.strip().lower()
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


class SkillLibrary:
    """技能库：提炼、存储、匹配、应用。"""

    async def extract_skill(
        self,
        intent_summary: str,
        tool_chain: list[dict[str, Any]],
        complexity: str,
        user_id: str,
        org_id: str,
        db=None,
    ) -> dict | None:
        """
        从成功的工具调用链中提炼技能模板。

        条件:
        - tool_chain 长度 >= _MIN_TOOL_CALLS
        - 所有工具调用状态为 success
        - 复杂度 >= MODERATE

        Returns:
            提炼出的技能 dict，或 None（不满足条件）
        """
        if not intent_summary or not tool_chain:
            return None

        # 过滤：只保留成功的工具调用
        successful = [tc for tc in tool_chain if tc.get("status") == "success"]
        if len(successful) < _MIN_TOOL_CALLS:
            return None

        # SIMPLE 查询不值得提炼
        if complexity and complexity.upper() == "SIMPLE":
            return None

        intent_hash = _make_intent_hash(intent_summary)
        skill_key = f"skill:{intent_hash}"

        # 构建技能模板
        chain = []
        for tc in successful:
            tool_name = tc.get("tool_name", "")
            # 提取参数模板（去掉具体值，保留键名）
            args = tc.get("args") or tc.get("params") or {}
            param_keys = list(args.keys()) if isinstance(args, dict) else []
            chain.append({"tool": tool_name, "param_keys": param_keys})

        skill = {
            "intent_pattern": intent_summary,
            "intent_hash": intent_hash,
            "tool_chain": chain,
            "tool_count": len(chain),
            "complexity": complexity,
            "success_count": 1,
            "last_used_at": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
        }

        # 存储到 conversation_memories
        if db:
            try:
                await self._upsert_skill(db, user_id, org_id, skill_key, skill)
                logger.info(
                    f"[SkillLibrary] Extracted skill: {intent_summary[:40]} "
                    f"({len(chain)} tools, hash={intent_hash})"
                )
            except Exception as e:
                logger.warning(f"[SkillLibrary] Failed to save skill: {e}")
                return None

        return skill

    async def match_skill(
        self,
        user_message: str,
        user_id: str,
        org_id: str,
        db=None,
    ) -> dict | None:
        """
        根据用户消息匹配已有技能。

        优先使用 embedding 语义匹配（通过 search_memories_by_embedding RPC），
        失败或无结果时回退到关键词重叠度匹配。

        Returns:
            匹配到的技能 dict（含 confidence），或 None
        """
        if not db or not user_message:
            return None

        # ── 1. 尝试语义向量匹配 ──
        try:
            semantic_result = await self._match_skill_semantic(
                user_message, user_id, org_id, db
            )
            if semantic_result:
                return semantic_result
        except Exception as e:
            logger.debug(f"[SkillLibrary] Semantic match unavailable, falling back to keyword: {e}")

        # ── 2. 回退：关键词重叠度匹配 ──
        return await self._match_skill_keyword(user_message, user_id, db)

    async def _match_skill_semantic(
        self,
        user_message: str,
        user_id: str,
        org_id: str,
        db,
    ) -> dict | None:
        """通过 embedding + pgvector RPC 做语义匹配。"""
        from app.services.conversation_memory.embedding import generate_embedding

        query_embedding = await generate_embedding(user_message, org_id)
        if not query_embedding:
            return None

        params: dict[str, Any] = {
            "query_embedding": query_embedding,
            "match_user_id": user_id,
            "match_limit": 10,
        }
        if org_id:
            params["match_org_id"] = org_id

        result = await db.rpc("search_memories_by_embedding", params).execute()
        if not result.data:
            return None

        # 过滤：只保留 category='skill' 且相似度 >= 阈值
        for row in result.data:
            if row.get("category") != _SKILL_CATEGORY:
                continue
            similarity = row.get("similarity", 0.0)
            if similarity < _SEMANTIC_THRESHOLD:
                continue

            try:
                skill_data = json.loads(row.get("value", "{}"))
            except (json.JSONDecodeError, TypeError):
                skill_data = row.get("metadata") or {}

            skill_data["confidence"] = round(similarity, 2)
            skill_data["skill_key"] = row.get("key", "")
            skill_data["match_method"] = "semantic"
            logger.info(
                f"[SkillLibrary] Semantic matched skill: "
                f"{skill_data.get('intent_pattern', '')[:40]} "
                f"(similarity={similarity:.2f})"
            )
            return skill_data

        return None

    async def _match_skill_keyword(
        self,
        user_message: str,
        user_id: str,
        db,
    ) -> dict | None:
        """关键词重叠度匹配（原始逻辑，作为回退）。"""
        try:
            result = (
                await db.table("conversation_memories")
                .select("key, value, metadata, importance")
                .eq("user_id", user_id)
                .eq("category", _SKILL_CATEGORY)
                .order("importance", desc=True)
                .limit(20)
                .execute()
            )

            if not result.data:
                return None

            msg_tokens = set(user_message.lower().split())
            best_match = None
            best_score = 0.0

            for row in result.data:
                metadata = row.get("metadata") or {}
                intent_pattern = metadata.get("intent_pattern", "")
                if not intent_pattern:
                    # 兼容：value 可能是 JSON 字符串
                    try:
                        val = json.loads(row.get("value", "{}"))
                        intent_pattern = val.get("intent_pattern", "")
                    except (json.JSONDecodeError, TypeError):
                        continue

                # 关键词重叠度计算
                pattern_tokens = set(intent_pattern.lower().split())
                if not pattern_tokens:
                    continue

                overlap = len(msg_tokens & pattern_tokens)
                score = overlap / max(len(pattern_tokens), 1)

                if score > best_score:
                    best_score = score
                    best_match = row

            if best_match and best_score >= _MATCH_THRESHOLD:
                metadata = best_match.get("metadata") or {}
                try:
                    skill_data = json.loads(best_match.get("value", "{}"))
                except (json.JSONDecodeError, TypeError):
                    skill_data = metadata

                skill_data["confidence"] = round(best_score, 2)
                skill_data["skill_key"] = best_match.get("key", "")
                skill_data["match_method"] = "keyword"
                logger.info(
                    f"[SkillLibrary] Keyword matched skill: "
                    f"{skill_data.get('intent_pattern', '')[:40]} "
                    f"(confidence={best_score:.2f})"
                )
                return skill_data

        except Exception as e:
            logger.warning(f"[SkillLibrary] Keyword match failed: {e}")

        return None

    async def reinforce_skill(
        self,
        skill_key: str,
        user_id: str,
        db=None,
    ) -> None:
        """技能被成功使用后，增加 success_count 和 importance。"""
        if not db or not skill_key:
            return

        try:
            result = (
                await db.table("conversation_memories")
                .select("metadata, importance, access_count")
                .eq("user_id", user_id)
                .eq("key", skill_key)
                .eq("category", _SKILL_CATEGORY)
                .limit(1)
                .execute()
            )

            if not result.data:
                return

            row = result.data[0]
            metadata = row.get("metadata") or {}
            success_count = metadata.get("success_count", 0) + 1
            metadata["success_count"] = success_count
            metadata["last_used_at"] = datetime.now(UTC).isoformat()

            # importance 随使用次数增长（上限 0.95）
            new_importance = min(0.95, 0.5 + success_count * 0.05)

            await (
                db.table("conversation_memories")
                .update(
                    {
                        "metadata": metadata,
                        "importance": new_importance,
                        "access_count": (row.get("access_count") or 0) + 1,
                        "last_accessed_at": datetime.now(UTC).isoformat(),
                    }
                )
                .eq("user_id", user_id)
                .eq("key", skill_key)
                .eq("category", _SKILL_CATEGORY)
                .execute()
            )

            logger.debug(f"[SkillLibrary] Reinforced: {skill_key} (count={success_count})")

        except Exception as e:
            logger.warning(f"[SkillLibrary] Reinforce failed: {e}")

    def skill_to_tool_hints(self, skill: dict) -> str:
        """将匹配到的技能转换为 planning 提示文本。"""
        chain = skill.get("tool_chain", [])
        if not chain:
            return ""

        intent = skill.get("intent_pattern", "类似任务")
        confidence = skill.get("confidence", 0)
        count = skill.get("success_count", 0)

        lines = [
            f"[技能匹配] 检测到与「{intent}」相似的任务 (置信度: {confidence}, 历史成功: {count}次)",
            "建议工具链:",
        ]
        for i, step in enumerate(chain, 1):
            tool = step.get("tool", "?")
            params = ", ".join(step.get("param_keys", []))
            lines.append(f"  {i}. {tool}({params})")

        lines.append("你可以参考此模板，也可以根据实际情况调整。")
        return "\n".join(lines)

    # ── 内部方法 ──

    async def _upsert_skill(
        self,
        db,
        user_id: str,
        org_id: str,
        skill_key: str,
        skill: dict,
    ) -> None:
        """插入或更新技能记录（含 embedding 生成）。"""
        # 生成 intent_pattern 的 embedding（失败不阻塞保存）
        embedding = None
        try:
            from app.services.conversation_memory.embedding import generate_embedding

            intent_text = skill.get("intent_pattern", "")
            if intent_text:
                embedding = await generate_embedding(intent_text, org_id)
        except Exception as e:
            logger.debug(f"[SkillLibrary] Embedding generation skipped: {e}")

        # 检查是否已存在
        existing = (
            await db.table("conversation_memories")
            .select("id, metadata")
            .eq("user_id", user_id)
            .eq("key", skill_key)
            .eq("category", _SKILL_CATEGORY)
            .limit(1)
            .execute()
        )

        if existing.data:
            # 已存在 → 更新 success_count
            old_meta = existing.data[0].get("metadata") or {}
            old_count = old_meta.get("success_count", 0)
            skill["success_count"] = old_count + 1
            new_importance = min(0.95, 0.5 + skill["success_count"] * 0.05)

            update_data = {
                "value": json.dumps(skill, ensure_ascii=False),
                "metadata": skill,
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
        else:
            # 新技能 → 插入（先检查是否超限）
            count_result = (
                await db.table("conversation_memories")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .eq("category", _SKILL_CATEGORY)
                .execute()
            )
            if count_result.count and count_result.count >= _MAX_SKILLS_PER_USER:
                # 淘汰最旧最少用的技能
                oldest = (
                    await db.table("conversation_memories")
                    .select("id")
                    .eq("user_id", user_id)
                    .eq("category", _SKILL_CATEGORY)
                    .order("importance", desc=False)
                    .order("last_accessed_at", desc=False)
                    .limit(1)
                    .execute()
                )
                if oldest.data:
                    await db.table("conversation_memories").delete().eq("id", oldest.data[0]["id"]).execute()

            insert_data = {
                "user_id": user_id,
                "organization_id": org_id,
                "category": _SKILL_CATEGORY,
                "key": skill_key,
                "value": json.dumps(skill, ensure_ascii=False),
                "metadata": skill,
                "importance": 0.5,
            }
            if embedding is not None:
                insert_data["embedding"] = embedding

            await (
                db.table("conversation_memories")
                .insert(insert_data)
                .execute()
            )


# 全局单例
skill_library = SkillLibrary()
