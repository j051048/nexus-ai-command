"""Memory decay, cleanup, importance re-evaluation, and MMR reranking."""

import logging
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


def compute_decay_score(memory: dict) -> float:
    """Compute a decay-weighted importance score with surprise bonus.

    Formula: score = base_importance * recency_factor * access_factor * surprise_factor
    - recency_factor decays over 30 days half-life
    - access_factor rewards frequently accessed memories (capped)
    - surprise_factor boosts high-similarity + low-access memories (unexpected finds)
    """
    importance = float(memory.get("importance", 0.5) or 0.5)
    access_count = int(memory.get("access_count", 0) or 0)
    similarity = float(memory.get("similarity", 0) or 0)

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

    # Access frequency bonus (logarithmic, capped)
    access_factor = math.log(access_count + 1) / math.log(10) + 0.5  # range ~0.5-2.0
    access_factor = min(access_factor, 2.0)

    # Surprise bonus: high similarity + low access = unexpected valuable find
    # Only applies when similarity is available (from semantic search results)
    surprise_factor = 1.0
    if similarity > 0.3:
        # Novelty: rarely accessed memories are more "surprising"
        # novelty=1.0 when access_count=0, decays toward 0.2 as access grows
        novelty = 1.0 / (1 + access_count * 0.5)
        # surprise = similarity * novelty, scaled to a 1.0-1.5 multiplier
        surprise_factor = 1.0 + 0.5 * similarity * novelty

    return importance * recency_factor * access_factor * surprise_factor


def mmr_rerank(
    memories: list[dict],
    limit: int,
    lambda_param: float = 0.7,
) -> list[dict]:
    """MMR (Maximal Marginal Relevance) diversity reranking.

    Balances relevance and diversity using Jaccard text similarity.
    lambda=1.0 -> pure relevance; lambda=0.0 -> max diversity.
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

    scores = [compute_decay_score(m) for m in memories]
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


async def cleanup_decayed_memories(
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

        score = compute_decay_score(mem)
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


async def reevaluate_importance(
    batch_size: int = 200,
    db: Any = None,
) -> dict:
    """Periodically adjust memory importance based on access patterns.

    Pure math -- no LLM calls. Runs weekly via Celery beat.
    - High access + low importance -> boost
    - Zero access + old + moderate importance -> decay
    """
    client = db or supabase
    if not client:
        return {"boosted": 0, "decayed": 0}

    boosted = 0
    decayed = 0

    try:
        # Boost: frequently accessed but undervalued memories
        boost_res = (
            await client.table("conversation_memories")
            .select("id, importance, access_count")
            .gt("access_count", 2)
            .lt("importance", 0.7)
            .limit(batch_size)
            .execute()
        )
        for mem in boost_res.data or []:
            count = int(mem.get("access_count", 0) or 0)
            old_imp = float(mem.get("importance", 0.5) or 0.5)
            boost = min(0.15 * math.log(count + 1), 0.4)
            new_imp = min(old_imp + boost, 1.0)
            if new_imp > old_imp + 0.01:
                await client.table("conversation_memories").update(
                    {"importance": round(new_imp, 3)}
                ).eq("id", mem["id"]).execute()
                boosted += 1

        # Decay: never-accessed old memories with moderate importance
        cutoff_10d = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        decay_res = (
            await client.table("conversation_memories")
            .select("id, importance, category")
            .eq("access_count", 0)
            .gt("importance", 0.3)
            .lt("created_at", cutoff_10d)
            .not_.in_("category", ["explicit_memory", "policy"])
            .limit(batch_size)
            .execute()
        )
        for mem in decay_res.data or []:
            old_imp = float(mem.get("importance", 0.5) or 0.5)
            new_imp = max(old_imp - 0.15, 0.1)
            await client.table("conversation_memories").update(
                {"importance": round(new_imp, 3)}
            ).eq("id", mem["id"]).execute()
            decayed += 1

        # Deep decay: zero access + 30+ days + still moderate -> drop to floor
        cutoff_30d = (datetime.now(UTC) - timedelta(days=30)).isoformat()
        deep_decay_res = (
            await client.table("conversation_memories")
            .select("id, importance, category")
            .eq("access_count", 0)
            .gt("importance", 0.2)
            .lt("created_at", cutoff_30d)
            .not_.in_("category", ["explicit_memory", "policy"])
            .limit(batch_size)
            .execute()
        )
        for mem in deep_decay_res.data or []:
            await client.table("conversation_memories").update(
                {"importance": 0.15}
            ).eq("id", mem["id"]).execute()
            decayed += 1

    except Exception as e:
        logger.warning(f"Memory importance re-evaluation failed: {e}")

    if boosted or decayed:
        logger.info(f"Memory importance reeval: boosted={boosted}, decayed={decayed}")

    return {"boosted": boosted, "decayed": decayed}
