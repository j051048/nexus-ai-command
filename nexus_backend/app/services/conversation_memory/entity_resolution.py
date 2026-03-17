"""Entity Resolution: merge synonymous entities in the knowledge graph.

Prevents garbage duplicate nodes like "Apple Inc." vs "苹果公司" by:
1. Embedding-based similarity matching at write time
2. Alias table for canonical name lookup
3. Periodic batch merging of similar entities
"""

import logging
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)

# Cosine similarity threshold for auto-merge (high confidence)
AUTO_MERGE_THRESHOLD = 0.88
# Threshold for candidate detection (lower, for batch review)
CANDIDATE_THRESHOLD = 0.78


async def resolve_entity(
    org_id: str,
    entity_name: str,
    entity_type: str = "concept",
    db: Any = None,
) -> str:
    """Resolve an entity name to its canonical form.

    Lookup order:
    1. Exact alias match in entity_aliases table
    2. Embedding similarity against existing entities
    3. Return original name if no match

    Returns:
        Canonical entity name (may be the original if no alias found)
    """
    client = db or supabase
    if not client or not entity_name:
        return entity_name

    # Step 1: Check alias table for exact match
    canonical = await _lookup_alias(org_id, entity_name, client)
    if canonical:
        return canonical

    # Step 2: Embedding similarity search
    try:
        from .embedding import generate_embedding

        embedding = await generate_embedding(entity_name, org_id)
        if not embedding:
            return entity_name

        similar = await _find_similar_by_embedding(
            org_id, embedding, AUTO_MERGE_THRESHOLD, client
        )
        if similar:
            # Found a high-confidence match — register alias and return canonical
            best = similar[0]
            canonical_name = best["entity_name"]
            if canonical_name != entity_name:
                await _register_alias(
                    org_id, entity_name, canonical_name,
                    entity_type, best["similarity"], client,
                )
                logger.info(
                    "[EntityRes] Auto-merged '%s' -> '%s' (sim=%.3f)",
                    entity_name, canonical_name, best["similarity"],
                )
                return canonical_name
    except Exception as e:
        logger.debug(f"[EntityRes] Embedding resolution skipped: {e}")

    return entity_name


async def resolve_triple(
    org_id: str,
    triple: dict,
    db: Any = None,
) -> dict:
    """Resolve both source and destination entities in a triple.

    Returns a new dict with resolved entity names.
    """
    resolved = dict(triple)
    resolved["source"] = await resolve_entity(
        org_id, triple["source"], triple.get("source_type", "concept"), db
    )
    resolved["destination"] = await resolve_entity(
        org_id, triple["destination"], triple.get("destination_type", "concept"), db
    )
    return resolved


async def get_entity_embedding(
    entity_name: str,
    org_id: str,
) -> list[float] | None:
    """Generate embedding for an entity name (for storage on triples)."""
    try:
        from .embedding import generate_embedding
        return await generate_embedding(entity_name, org_id)
    except Exception:
        return None


async def batch_merge_similar_entities(
    org_id: str,
    threshold: float = CANDIDATE_THRESHOLD,
    batch_size: int = 100,
    db: Any = None,
) -> dict:
    """Batch scan for similar entities and merge them.

    Intended to run as a periodic Celery task.
    Returns: {"scanned": int, "merged": int}
    """
    client = db or supabase
    if not client:
        return {"scanned": 0, "merged": 0}

    merged = 0

    try:
        # Get distinct active entities without embeddings first (need backfill)
        result = await (
            client.table("knowledge_graph_triples")
            .select("source_entity, source_type")
            .eq("organization_id", org_id)
            .is_("valid_to", "null")
            .is_("source_embedding", "null")
            .limit(batch_size)
            .execute()
        )

        entities_to_embed = {
            r["source_entity"]: r.get("source_type", "concept")
            for r in (result.data or [])
        }

        # Backfill embeddings
        for name, etype in entities_to_embed.items():
            try:
                emb = await get_entity_embedding(name, org_id)
                if emb:
                    await (
                        client.table("knowledge_graph_triples")
                        .update({"source_embedding": emb})
                        .eq("organization_id", org_id)
                        .eq("source_entity", name)
                        .is_("valid_to", "null")
                        .execute()
                    )
            except Exception as e:
                logger.debug(f"[EntityRes] Backfill failed for '{name}': {e}")

        # Now scan for similar pairs
        # Get all distinct entities with embeddings
        all_entities = await (
            client.rpc("get_distinct_kg_entities", {"p_org_id": org_id})
            .execute()
        )
        # Fallback: if RPC doesn't exist, skip batch merge
        if not all_entities.data:
            return {"scanned": len(entities_to_embed), "merged": 0}

        # For each entity, find similar ones
        from .embedding import generate_embedding

        seen_pairs: set[tuple[str, str]] = set()
        for entity in all_entities.data[:batch_size]:
            name = entity.get("entity_name", "")
            if not name:
                continue

            emb = await generate_embedding(name, org_id)
            if not emb:
                continue

            similar = await _find_similar_by_embedding(
                org_id, emb, threshold, client
            )

            for match in similar:
                match_name = match["entity_name"]
                if match_name == name:
                    continue

                pair = tuple(sorted([name, match_name]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                # Merge: keep the one with more occurrences as canonical
                canonical, alias = await _pick_canonical(
                    org_id, name, match_name, client
                )
                await _merge_entities(org_id, canonical, alias, client)
                merged += 1

    except Exception as e:
        logger.warning(f"[EntityRes] Batch merge failed: {e}")

    if merged:
        logger.info(f"[EntityRes] Batch merge for org {org_id}: merged={merged}")

    return {"scanned": len(entities_to_embed) if 'entities_to_embed' in dir() else 0, "merged": merged}


# ── Internal helpers ──


async def _lookup_alias(org_id: str, name: str, db: Any) -> str | None:
    """Look up canonical name from alias table."""
    try:
        result = await (
            db.table("entity_aliases")
            .select("canonical_name")
            .eq("organization_id", org_id)
            .eq("alias", name)
            .maybe_single()
            .execute()
        )
        if result.data:
            return result.data["canonical_name"]
    except Exception:
        pass
    return None


async def _find_similar_by_embedding(
    org_id: str,
    embedding: list[float],
    threshold: float,
    db: Any,
) -> list[dict]:
    """Find similar entities using the find_similar_entities RPC."""
    try:
        result = await db.rpc(
            "find_similar_entities",
            {
                "p_org_id": org_id,
                "p_embedding": embedding,
                "p_threshold": threshold,
                "p_limit": 5,
            },
        ).execute()
        return result.data or []
    except Exception as e:
        logger.debug(f"[EntityRes] Similarity search failed: {e}")
        return []


async def _register_alias(
    org_id: str,
    alias: str,
    canonical_name: str,
    entity_type: str,
    confidence: float,
    db: Any,
) -> None:
    """Register an alias -> canonical_name mapping."""
    try:
        await (
            db.table("entity_aliases")
            .upsert(
                {
                    "organization_id": org_id,
                    "alias": alias,
                    "canonical_name": canonical_name,
                    "entity_type": entity_type,
                    "confidence": round(confidence, 3),
                },
                on_conflict="organization_id,alias",
            )
            .execute()
        )
    except Exception as e:
        logger.debug(f"[EntityRes] Alias registration failed: {e}")


async def _pick_canonical(
    org_id: str,
    name_a: str,
    name_b: str,
    db: Any,
) -> tuple[str, str]:
    """Pick which entity name should be canonical.

    Heuristic: the one with more total occurrences wins.
    Tie-breaker: shorter name (more likely to be the "standard" form).
    """
    try:
        res_a = await (
            db.table("knowledge_graph_triples")
            .select("occurrences")
            .eq("organization_id", org_id)
            .eq("source_entity", name_a)
            .is_("valid_to", "null")
            .execute()
        )
        res_b = await (
            db.table("knowledge_graph_triples")
            .select("occurrences")
            .eq("organization_id", org_id)
            .eq("source_entity", name_b)
            .is_("valid_to", "null")
            .execute()
        )

        sum_a = sum(r.get("occurrences", 1) for r in (res_a.data or []))
        sum_b = sum(r.get("occurrences", 1) for r in (res_b.data or []))

        if sum_a > sum_b:
            return name_a, name_b
        elif sum_b > sum_a:
            return name_b, name_a
        else:
            # Tie-breaker: shorter name
            return (name_a, name_b) if len(name_a) <= len(name_b) else (name_b, name_a)
    except Exception:
        return (name_a, name_b) if len(name_a) <= len(name_b) else (name_b, name_a)


async def _merge_entities(
    org_id: str,
    canonical: str,
    alias: str,
    db: Any,
) -> None:
    """Merge alias entity into canonical: rewrite triples + register alias."""
    try:
        # Rewrite source_entity references
        await (
            db.table("knowledge_graph_triples")
            .update({"source_entity": canonical})
            .eq("organization_id", org_id)
            .eq("source_entity", alias)
            .is_("valid_to", "null")
            .execute()
        )

        # Rewrite destination_entity references
        await (
            db.table("knowledge_graph_triples")
            .update({"destination_entity": canonical})
            .eq("organization_id", org_id)
            .eq("destination_entity", alias)
            .is_("valid_to", "null")
            .execute()
        )

        # Register alias mapping
        await _register_alias(org_id, alias, canonical, "concept", 1.0, db)

        logger.info("[EntityRes] Merged entity '%s' -> '%s'", alias, canonical)
    except Exception as e:
        logger.warning(f"[EntityRes] Merge failed '{alias}' -> '{canonical}': {e}")
