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
        """Tokenize using character bigrams for CJK compatibility.

        Plain split() produces whole sentences for Chinese (no spaces),
        making Jaccard always 0 or 1.  Character bigrams work for any language.
        """
        text = text.lower()
        if len(text) < 2:
            return {text} if text else set()
        return {text[i : i + 2] for i in range(len(text) - 1)}

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


async def decay_kg_strength(
    decay_rate: float = 0.95,
    archive_threshold: float = 0.15,
    protect_occurrences: int = 5,
    batch_size: int = 500,
    db: Any = None,
) -> dict:
    """Decay knowledge graph triple strength based on time since last reinforcement.

    Formula: new_strength = strength * decay_rate ^ weeks_since_last_reinforced
    - Triples below archive_threshold get soft-expired (valid_to = now)
    - High-occurrence triples (>= protect_occurrences) are protected from archival

    Returns: {"scanned": int, "decayed": int, "archived": int}
    """
    client = db or supabase
    if not client:
        return {"scanned": 0, "decayed": 0, "archived": 0}

    decayed_count = 0
    archived = 0

    try:
        # Fetch active triples with their reinforcement timestamps
        result = (
            await client.table("knowledge_graph_triples")
            .select("id, strength, occurrences, last_reinforced_at, updated_at, created_at")
            .is_("valid_to", "null")
            .order("updated_at", desc=False)
            .limit(batch_size)
            .execute()
        )

        triples = result.data or []
        now = datetime.now(UTC)

        for triple in triples:
            # Determine last activity time
            last_active = (
                triple.get("last_reinforced_at")
                or triple.get("updated_at")
                or triple.get("created_at")
            )
            if not last_active:
                continue

            try:
                if isinstance(last_active, str):
                    last_dt = datetime.fromisoformat(last_active.replace("Z", "+00:00"))
                else:
                    last_dt = last_active
                weeks_since = max((now - last_dt).days / 7.0, 0)
            except Exception:
                weeks_since = 4  # Default to ~1 month

            if weeks_since < 1:
                continue  # Skip recently active triples

            old_strength = float(triple.get("strength", 0.5))
            new_strength = old_strength * (decay_rate ** weeks_since)
            new_strength = round(new_strength, 4)

            if new_strength >= old_strength - 0.001:
                continue  # No meaningful change

            occurrences = int(triple.get("occurrences", 1))

            if new_strength < archive_threshold and occurrences < protect_occurrences:
                # Archive: soft-expire the triple
                try:
                    await (
                        client.table("knowledge_graph_triples")
                        .update({"strength": new_strength, "valid_to": now.isoformat()})
                        .eq("id", triple["id"])
                        .execute()
                    )
                    archived += 1
                except Exception as e:
                    logger.error(f"[KG Decay] Archive failed for {triple['id']}: {e}")
            else:
                # Just decay the strength
                try:
                    await (
                        client.table("knowledge_graph_triples")
                        .update({"strength": new_strength})
                        .eq("id", triple["id"])
                        .execute()
                    )
                    decayed_count += 1
                except Exception as e:
                    logger.error(f"[KG Decay] Update failed for {triple['id']}: {e}")

    except Exception as e:
        logger.warning(f"[KG Decay] Scan failed: {e}")

    if decayed_count or archived:
        logger.info(
            f"[KG Decay] scanned={len(triples)}, decayed={decayed_count}, archived={archived}"
        )

    return {"scanned": len(triples) if 'triples' in dir() else 0, "decayed": decayed_count, "archived": archived}


async def promote_high_recurrence_memories(
    recurrence_threshold: int = 3,
    window_days: int = 30,
    db: Any = None,
) -> dict:
    """自动晋升高频记忆为业务规则。

    晋升条件（借鉴 self-improving-agent 的量化门槛）：
    - recurrence_count >= threshold（默认 3）
    - first_seen_at 在 window_days 天内
    - 当前 category 不是 business_rule（避免重复晋升）

    风险分级（借鉴 capability-evolver 的变异风险评估）：
    - low: preference/usage_pattern → 直接晋升为 business_rule
    - medium: fact → 提升 importance 到 0.8，不改 category
    - high: explicit_memory/policy → 仅提升 importance 到 0.75，需人工确认晋升

    Returns: {"scanned": int, "promoted": int, "boosted": int}
    """
    client = db or supabase
    if not client:
        return {"scanned": 0, "promoted": 0, "boosted": 0}

    promoted = 0
    boosted = 0
    try:
        cutoff = (datetime.now(UTC) - timedelta(days=window_days)).isoformat()

        result = (
            await client.table("conversation_memories")
            .select("id, user_id, key, value, category, importance, recurrence_count")
            .gte("recurrence_count", recurrence_threshold)
            .gte("first_seen_at", cutoff)
            .neq("category", "business_rule")
            .is_("superseded_by", "null")
            .limit(50)
            .execute()
        )

        candidates = result.data or []
        now = datetime.now(UTC).isoformat()

        # Risk classification by category
        LOW_RISK = {"preference", "usage_pattern"}       # safe to auto-promote
        MEDIUM_RISK = {"fact"}                            # boost importance only
        # HIGH_RISK: everything else (explicit_memory, policy, etc.)

        for mem in candidates:
            category = mem.get("category", "")
            old_imp = float(mem.get("importance", 0.5) or 0.5)

            try:
                if category in LOW_RISK:
                    # Low risk: full promotion to business_rule
                    await (
                        client.table("conversation_memories")
                        .update({
                            "category": "business_rule",
                            "importance": 0.9,
                            "updated_at": now,
                        })
                        .eq("id", mem["id"])
                        .execute()
                    )
                    promoted += 1
                    action = "PROMOTE"
                    new_desc = "category=business_rule, importance=0.9"

                elif category in MEDIUM_RISK:
                    # Medium risk: boost importance but keep category
                    new_imp = max(old_imp, 0.8)
                    await (
                        client.table("conversation_memories")
                        .update({
                            "importance": new_imp,
                            "updated_at": now,
                        })
                        .eq("id", mem["id"])
                        .execute()
                    )
                    boosted += 1
                    action = "BOOST"
                    new_desc = f"importance={old_imp}->{new_imp} (medium risk, category unchanged)"

                else:
                    # High risk: gentle boost only, needs manual review
                    new_imp = max(old_imp, 0.75)
                    if new_imp <= old_imp:
                        continue
                    await (
                        client.table("conversation_memories")
                        .update({
                            "importance": new_imp,
                            "updated_at": now,
                        })
                        .eq("id", mem["id"])
                        .execute()
                    )
                    boosted += 1
                    action = "BOOST"
                    new_desc = f"importance={old_imp}->{new_imp} (high risk, manual review needed)"

                # Audit log
                try:
                    from .audit import log_memory_change
                    await log_memory_change(
                        memory_id=mem["id"],
                        user_id=mem.get("user_id", ""),
                        action=action,
                        old_value=f"category={category}, importance={old_imp}",
                        new_value=new_desc,
                        reason=f"recurrence_count={mem.get('recurrence_count')} >= {recurrence_threshold}, risk={category}",
                        actor="system_promote",
                        db=client,
                    )
                except Exception:
                    pass  # audit is non-fatal

            except Exception as e:
                logger.warning(f"[Promote] Failed to process memory {mem['id']}: {e}")

        if promoted or boosted:
            logger.info(f"[Promote] Processed {len(candidates)} candidates: promoted={promoted}, boosted={boosted}")

    except Exception as e:
        logger.warning(f"[Promote] Scan failed: {e}")

    return {"scanned": len(candidates) if 'candidates' in dir() else 0, "promoted": promoted, "boosted": boosted}
