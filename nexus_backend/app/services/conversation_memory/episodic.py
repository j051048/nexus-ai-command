"""P1-6: Episodic Memory Service - saves and retrieves complete interaction episodes."""

import logging
from typing import Any

from app.core.database import supabase

from .embedding import generate_embedding

logger = logging.getLogger(__name__)


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
            embedding = await generate_embedding(embed_text, org_id)

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
            logger.error(f"[Episode] Save failed (non-critical): {e}")
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
            logger.error(f"[Episode] Search failed (non-critical): {e}")
            return []

    def build_episode_context(self, episodes: list[dict]) -> str:
        """Build injection text from retrieved episodes.

        Filters out failed episodes (confidence_score=0) to avoid
        poisoning the LLM into thinking a task is impossible.
        """
        if not episodes:
            return ""

        # Only include episodes with positive outcomes
        useful = [ep for ep in episodes if ep.get("confidence_score", 0) > 0.1]
        if not useful:
            return ""

        parts = ["[历史经验回忆 - 以下是处理类似问题的历史记录]"]
        for i, ep in enumerate(useful[:3], 1):
            tools = ", ".join(ep.get("tools_used", [])[:5]) or "无"
            parts.append(
                f"经验{i}: 用户意图「{ep.get('user_intent', '')}」→ "
                f"策略: {ep.get('strategy', '')[:100]} | "
                f"使用工具: {tools} | "
                f"结果置信度: {ep.get('confidence_score', 0):.0%}"
            )
        parts.append("[经验回忆结束]")
        return "\n".join(parts)
