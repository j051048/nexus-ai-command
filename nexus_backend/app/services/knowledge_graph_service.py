"""
P2-2: Entity Relation Service — Lightweight Knowledge Graph
P3:   Behavior Pattern Learning — Tool Usage Pattern Detection

Provides:
- extract_entities_from_conversation(): Extract entity relationships from chat
- query_entity_context(): Retrieve relationship context for a query
- learn_tool_patterns(): Detect recurring tool usage patterns
- get_pattern_suggestions(): Suggest proactive actions based on learned patterns
"""

import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from difflib import SequenceMatcher

from app.core.database import supabase

logger = logging.getLogger(__name__)


# ─── P2-2: Entity Extraction ────────────────────────────────────────────────


# Common entity types in our domain
ENTITY_TYPES = {
    "customer": ["客户", "公司", "企业", "单位", "院所", "高校", "实验室"],
    "product": ["产品", "仪器", "设备", "型号", "系统"],
    "person": ["联系人", "负责人", "教授", "主任", "经理", "总监"],
    "competitor": ["竞品", "竞争对手", "对手", "友商"],
    "event": ["展会", "会议", "研讨会", "培训", "活动"],
}

RELATION_PATTERNS = [
    # (regex, source_type, relation, target_type)
    (r"(.+?)(?:购买|采购|订购)了?(.+)", "customer", "purchased", "product"),
    (r"(.+?)(?:竞争|竞品|对标)(.+)", "company", "competes_with", "company"),
    (r"(.+?)(?:负责|管理|对接)(.+)", "person", "manages", "customer"),
    (r"(.+?)(?:使用|用了|采用)(.+)", "customer", "uses", "product"),
    (r"(.+?)(?:参加|参展|参与)(.+)", "customer", "attended", "event"),
    (r"(.+?)(?:合同|签约|签了)(.+)", "customer", "contracted", "product"),
    (r"(.+?)(?:的联系人|的对接人)(?:是|为)(.+)", "customer", "contacts", "person"),
    (r"(.+?)(?:报价|询价)(.+)", "customer", "quoted", "product"),
]

# ─── Entity Normalization & Disambiguation ────────────────────────────────────

# Company suffixes to strip for normalization
_COMPANY_SUFFIXES = re.compile(
    r"(有限责任公司|股份有限公司|有限公司|集团公司|集团|科技|技术|生物|医药|电子|信息|控股)$"
)

# Brackets/parenthetical info to strip
_BRACKET_INFO = re.compile(r"[（(][^)）]*[)）]")

# Common prefixes that don't distinguish entities
_TRIVIAL_PREFIXES = re.compile(r"^(中国|北京|上海|深圳|广州|杭州|成都|南京|武汉|西安)")


def normalize_entity(name: str) -> str:
    """Normalize entity name for dedup.

    Strips company suffixes, brackets, whitespace, and lowercases
    so that '华为技术有限公司' and '华为' can be recognized as the same entity.
    """
    name = name.strip()
    # Remove bracketed info: "阿里巴巴（中国）" → "阿里巴巴"
    name = _BRACKET_INFO.sub("", name).strip()
    # Remove company suffixes: "华为技术有限公司" → "华为"
    name = _COMPANY_SUFFIXES.sub("", name).strip()
    # Collapse whitespace
    name = re.sub(r"\s+", "", name)
    return name


def fuzzy_match(a: str, b: str, threshold: float = 0.85) -> bool:
    """Check if two entity names are fuzzy-similar above threshold."""
    if not a or not b:
        return False
    na, nb = normalize_entity(a), normalize_entity(b)
    if na == nb:
        return True
    # Short strings: require exact normalized match
    if len(na) <= 2 or len(nb) <= 2:
        return na == nb
    # One contains the other (e.g., "华为" in "华为技术")
    if na in nb or nb in na:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= threshold


async def extract_entities_from_conversation(
    user_message: str,
    ai_response: str,
    org_id: str | None = None,
    tool_outputs: list[dict] | None = None,
) -> list[dict]:
    """
    Extract entity relationships from a conversation turn.

    Uses rule-based extraction (fast, no LLM cost) for common patterns.
    Returns list of extracted relations ready for DB upsert.
    """
    if not org_id:
        return []

    relations = []
    combined_text = f"{user_message}\n{ai_response}"

    # Rule-based extraction from conversation text
    for pattern, src_type, relation, tgt_type in RELATION_PATTERNS:
        matches = re.finditer(pattern, combined_text)
        for match in matches:
            source = match.group(1).strip()[:100]
            target = match.group(2).strip()[:100]
            if len(source) < 2 or len(target) < 2:
                continue
            # Clean up common prefixes
            for prefix in ["把", "将", "对", "和", "与", "向"]:
                source = source.lstrip(prefix)
                target = target.lstrip(prefix)

            # Normalize entity names for consistent dedup
            source = normalize_entity(source) or source
            target = normalize_entity(target) or target

            relations.append(
                {
                    "org_id": org_id,
                    "source_entity": source,
                    "source_type": src_type,
                    "relation": relation,
                    "target_entity": target,
                    "target_type": tgt_type,
                    "confidence": 0.7,
                    "source_context": combined_text[:200],
                    "extracted_from": "conversation",
                }
            )

    # Extract from tool outputs (higher confidence)
    if tool_outputs:
        for tool_out in tool_outputs:
            tool_name = tool_out.get("tool_name", "")
            result = tool_out.get("result", "")

            # Customer-related tools produce high-quality entity data
            if tool_name in (
                "get_customers",
                "get_customer_detail",
                "customer_profile",
            ):
                _extract_from_customer_tool(result, org_id, relations)
            elif tool_name in ("get_sales_pipeline", "get_contracts"):
                _extract_from_sales_tool(result, org_id, relations)

    # Persist to DB (upsert)
    if relations:
        await _upsert_relations(relations)

    return relations


def _extract_from_customer_tool(result: str, org_id: str, relations: list):
    """Extract entities from customer tool output."""
    try:
        if isinstance(result, str):
            data = (
                json.loads(result)
                if result.startswith("{") or result.startswith("[")
                else {}
            )
        else:
            data = result

        if isinstance(data, list):
            for item in data[:20]:  # Limit
                name = item.get("name") or item.get("customer_name", "")
                if name:
                    # Customer -> stage relation
                    stage = item.get("stage") or item.get("status", "")
                    if stage:
                        relations.append(
                            {
                                "org_id": org_id,
                                "source_entity": name,
                                "source_type": "customer",
                                "relation": "in_stage",
                                "target_entity": stage,
                                "target_type": "stage",
                                "confidence": 0.95,
                                "extracted_from": "tool_output",
                            }
                        )
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass


def _extract_from_sales_tool(result: str, org_id: str, relations: list):
    """Extract entities from sales pipeline tool output."""
    try:
        if isinstance(result, str):
            data = (
                json.loads(result)
                if result.startswith("{") or result.startswith("[")
                else {}
            )
        else:
            data = result

        if isinstance(data, list):
            for item in data[:20]:
                customer = item.get("customer_name", "")
                product = item.get("product_name") or item.get("product", "")
                if customer and product:
                    relations.append(
                        {
                            "org_id": org_id,
                            "source_entity": customer,
                            "source_type": "customer",
                            "relation": "interested_in",
                            "target_entity": product,
                            "target_type": "product",
                            "confidence": 0.9,
                            "extracted_from": "tool_output",
                        }
                    )
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass


async def _upsert_relations(relations: list[dict]):
    """Upsert entity relations into the DB with fuzzy dedup.

    Before inserting, checks existing entities for fuzzy matches to avoid
    duplicate entries like '华为技术有限公司' vs '华为'.
    """
    if not supabase:
        return

    # Pre-fetch existing entities for this org to enable fuzzy matching
    org_ids = {r["org_id"] for r in relations if r.get("org_id")}
    existing_entities: dict[str, list[str]] = {}  # org_id -> list of entity names
    for oid in org_ids:
        try:
            resp = await (
                supabase.table("entity_relations")
                .select("source_entity, target_entity")
                .eq("org_id", oid)
                .limit(500)
                .execute()
            )
            names = set()
            for row in resp.data or []:
                names.add(row.get("source_entity", ""))
                names.add(row.get("target_entity", ""))
            existing_entities[oid] = list(names)
        except Exception:
            existing_entities[oid] = []

    for rel in relations:
        try:
            org_id = rel["org_id"]
            # Fuzzy-match source/target against existing entities to canonicalize
            rel["source_entity"] = _find_canonical(
                rel["source_entity"], existing_entities.get(org_id, [])
            )
            rel["target_entity"] = _find_canonical(
                rel["target_entity"], existing_entities.get(org_id, [])
            )

            await (
                supabase.table("entity_relations")
                .upsert(
                    {
                        "org_id": org_id,
                        "source_entity": rel["source_entity"],
                        "source_type": rel["source_type"],
                        "relation": rel["relation"],
                        "target_entity": rel["target_entity"],
                        "target_type": rel["target_type"],
                        "confidence": rel.get("confidence", 0.8),
                        "source_context": rel.get("source_context", "")[:500],
                        "extracted_from": rel.get("extracted_from", "conversation"),
                        "last_seen_at": datetime.now(UTC).isoformat(),
                    },
                    on_conflict="org_id,source_entity,relation,target_entity",
                )
                .execute()
            )

            # Track newly inserted entity names for subsequent fuzzy matches
            existing = existing_entities.get(org_id, [])
            if rel["source_entity"] not in existing:
                existing.append(rel["source_entity"])
            if rel["target_entity"] not in existing:
                existing.append(rel["target_entity"])
        except Exception as e:
            logger.error(f"[EntityRelation] Upsert failed: {e}")


def _find_canonical(name: str, existing_names: list[str]) -> str:
    """Find the best existing canonical name via fuzzy matching.

    If a similar entity already exists in the DB, reuse its name to prevent
    fragmentation (e.g., '华为技术有限公司' → '华为' if '华为' already stored).
    """
    if not existing_names or not name:
        return name
    norm_new = normalize_entity(name)
    for existing in existing_names:
        if fuzzy_match(name, existing):
            # Prefer the shorter/normalized form as canonical
            norm_exist = normalize_entity(existing)
            return existing if len(norm_exist) <= len(norm_new) else name
    return name


async def query_entity_context(
    query: str,
    org_id: str,
    limit: int = 10,
) -> str:
    """
    Query the knowledge graph for entity relationships relevant to a user query.

    Returns a formatted string to inject into the agent's context.
    """
    if not supabase or not org_id:
        return ""

    try:
        # Extract potential entity names from the query (simple keyword match)
        keywords = [w for w in re.split(r"[，。！？\s,.\?!]+", query) if len(w) >= 2]
        # Also search with normalized forms for fuzzy coverage
        norm_keywords = list(
            {normalize_entity(kw) for kw in keywords if normalize_entity(kw)}
        )
        all_search_terms = list(
            dict.fromkeys(keywords[:5] + norm_keywords[:3])
        )  # dedup, preserve order

        all_results = []
        for kw in all_search_terms[:6]:  # Limit keyword searches
            # Search as source entity
            resp = await (
                supabase.table("entity_relations")
                .select(
                    "source_entity, source_type, relation, target_entity, target_type, confidence"
                )
                .eq("org_id", org_id)
                .ilike("source_entity", f"%{kw}%")
                .order("last_seen_at", desc=True)
                .limit(limit)
                .execute()
            )
            all_results.extend(resp.data or [])

            # Search as target entity
            resp2 = await (
                supabase.table("entity_relations")
                .select(
                    "source_entity, source_type, relation, target_entity, target_type, confidence"
                )
                .eq("org_id", org_id)
                .ilike("target_entity", f"%{kw}%")
                .order("last_seen_at", desc=True)
                .limit(limit)
                .execute()
            )
            all_results.extend(resp2.data or [])

        if not all_results:
            return ""

        # Deduplicate
        seen = set()
        unique = []
        for r in all_results:
            key = (r["source_entity"], r["relation"], r["target_entity"])
            if key not in seen:
                seen.add(key)
                unique.append(r)

        # Format as context string
        lines = ["[实体关系图谱上下文]"]
        for r in unique[:limit]:
            lines.append(
                f"- {r['source_entity']}({r['source_type']}) "
                f"--[{r['relation']}]--> "
                f"{r['target_entity']}({r['target_type']})"
            )
        lines.append("[关系图谱结束]")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"[EntityRelation] Query failed: {e}")
        return ""


# ─── P3: Behavior Pattern Learning ──────────────────────────────────────────


async def learn_tool_patterns(
    user_id: str,
    org_id: str | None,
    tool_calls: list[dict],
    user_message: str,
) -> list[dict]:
    """
    Analyze tool usage patterns from the current session and recent history.

    Detects:
    1. Frequent tool sequences (e.g., user always checks pipeline then follows up)
    2. Time-based patterns (e.g., every Monday morning checks weekly report)
    3. Query-tool correlations (e.g., questions about "客户" always trigger get_customers)

    Returns list of newly detected patterns (if any).
    """
    if not org_id or not tool_calls:
        return []

    new_patterns = []

    try:
        # Get recent tool usage history from org_memories
        if not supabase:
            return []

        # Record current tool sequence
        current_sequence = [
            tc.get("tool_name", "") for tc in tool_calls if tc.get("tool_name")
        ]
        if not current_sequence:
            return []

        # Store this tool sequence as a data point
        now = datetime.now(UTC)
        weekday = now.strftime("%A")
        hour = now.hour

        sequence_record = {
            "tools": current_sequence,
            "query_keywords": _extract_keywords(user_message),
            "weekday": weekday,
            "hour": hour,
            "timestamp": now.isoformat(),
        }

        # Load recent sequences from org_memories (category = tool_sequence)
        resp = await (
            supabase.table("org_memories")
            .select("value, metadata")
            .eq("organization_id", org_id)
            .eq("category", "tool_sequence")
            .order("updated_at", desc=True)
            .limit(50)
            .execute()
        )
        recent_sequences = resp.data or []

        # Store current sequence (use timestamp as unique key)
        await (
            supabase.table("org_memories")
            .insert(
                {
                    "organization_id": org_id,
                    "scope": "organization",
                    "category": "tool_sequence",
                    "key": f"seq_{now.strftime('%Y%m%d_%H%M%S')}_{user_id[:8]}",
                    "value": json.dumps(sequence_record, ensure_ascii=False),
                    "contributed_by": user_id,
                    "metadata": {},
                }
            )
            .execute()
        )

        # Need at least 5 data points to detect patterns
        if len(recent_sequences) < 5:
            return []

        # ── Pattern Detection ──

        # 1. Frequent tool sequences (bigram analysis)
        all_bigrams = []
        for seq_row in recent_sequences:
            try:
                seq_data = json.loads(seq_row.get("value", "{}"))
                tools = seq_data.get("tools", [])
                for i in range(len(tools) - 1):
                    all_bigrams.append(f"{tools[i]} -> {tools[i + 1]}")
            except (json.JSONDecodeError, KeyError):
                continue

        bigram_counts = Counter(all_bigrams)
        for bigram, count in bigram_counts.most_common(5):
            if count >= 3:  # Seen at least 3 times
                pattern = {
                    "type": "tool_sequence",
                    "pattern": bigram,
                    "frequency": count,
                    "description": f"用户经常先用 {bigram.split(' -> ')[0]}，然后用 {bigram.split(' -> ')[1]}",
                }
                new_patterns.append(pattern)

        # 2. Time-based patterns
        weekday_tools = {}
        for seq_row in recent_sequences:
            try:
                seq_data = json.loads(seq_row.get("value", "{}"))
                wd = seq_data.get("weekday", "")
                tools = seq_data.get("tools", [])
                if wd:
                    weekday_tools.setdefault(wd, []).extend(tools)
            except (json.JSONDecodeError, KeyError):
                continue

        for wd, tools in weekday_tools.items():
            tool_counts = Counter(tools)
            for tool, count in tool_counts.most_common(3):
                if count >= 3:
                    pattern = {
                        "type": "time_based",
                        "pattern": f"{wd}: {tool}",
                        "frequency": count,
                        "description": f"每{_translate_weekday(wd)}，用户经常使用 {tool}",
                    }
                    new_patterns.append(pattern)

        # 3. Query-tool correlations
        keyword_tools = {}
        for seq_row in recent_sequences:
            try:
                seq_data = json.loads(seq_row.get("value", "{}"))
                keywords = seq_data.get("query_keywords", [])
                tools = seq_data.get("tools", [])
                for kw in keywords:
                    keyword_tools.setdefault(kw, []).extend(tools)
            except (json.JSONDecodeError, KeyError):
                continue

        for kw, tools in keyword_tools.items():
            tool_counts = Counter(tools)
            for tool, count in tool_counts.most_common(2):
                if count >= 3:
                    pattern = {
                        "type": "query_tool_correlation",
                        "pattern": f"'{kw}' -> {tool}",
                        "frequency": count,
                        "description": f"当用户提到「{kw}」时，经常需要使用 {tool}",
                    }
                    new_patterns.append(pattern)

        # Persist learned patterns to org_memories
        if new_patterns:
            await _persist_learned_patterns(org_id, new_patterns)

    except Exception as e:
        logger.error(f"[PatternLearning] Analysis failed: {e}")

    return new_patterns


async def get_pattern_suggestions(
    user_id: str,
    org_id: str | None,
    current_query: str,
) -> str:
    """
    Generate proactive suggestions based on learned behavior patterns.

    Returns a formatted hint string to inject into the system prompt.
    """
    if not org_id or not supabase:
        return ""

    try:
        # Load recent learned patterns
        resp = await (
            supabase.table("org_memories")
            .select("value")
            .eq("organization_id", org_id)
            .eq("category", "learned_pattern")
            .order("updated_at", desc=True)
            .limit(10)
            .execute()
        )
        patterns = resp.data or []
        if not patterns:
            return ""

        # Match patterns against current query
        query_keywords = _extract_keywords(current_query)
        now = datetime.now(UTC)
        current_weekday = now.strftime("%A")

        suggestions = []
        for p_row in patterns:
            try:
                p_data = json.loads(p_row.get("value", "{}"))
                p_type = p_data.get("type", "")
                pattern = p_data.get("pattern", "")
                desc = p_data.get("description", "")

                if p_type == "query_tool_correlation":
                    # Check if query contains the keyword
                    for kw in query_keywords:
                        if kw in pattern:
                            suggestions.append(f"💡 {desc}")
                            break
                elif p_type == "time_based":
                    # Check if current weekday matches
                    if current_weekday in pattern:
                        suggestions.append(f"⏰ {desc}")
                elif p_type == "tool_sequence":
                    suggestions.append(f"🔗 {desc}")

            except (json.JSONDecodeError, KeyError):
                continue

        if not suggestions:
            return ""

        # Limit to top 3 suggestions
        suggestions = suggestions[:3]
        return "[行为模式洞察]\n" + "\n".join(suggestions) + "\n[洞察结束]"

    except Exception as e:
        logger.error(f"[PatternLearning] Suggestion generation failed: {e}")
        return ""


# ─── Internal Helpers ────────────────────────────────────────────────────────


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from text (simple Chinese-aware splitting)."""
    # Remove common stop words and short tokens
    stop_words = {
        "的",
        "了",
        "吗",
        "呢",
        "吧",
        "啊",
        "是",
        "在",
        "有",
        "和",
        "与",
        "我",
        "你",
        "他",
        "她",
        "它",
        "们",
        "这",
        "那",
        "什么",
        "怎么",
        "请",
        "帮",
        "看",
        "一下",
        "一些",
        "所有",
        "查询",
        "查看",
    }
    words = re.split(r"[，。！？\s,.\?!\n\r]+", text)
    keywords = [
        w.strip() for w in words if len(w.strip()) >= 2 and w.strip() not in stop_words
    ]
    return keywords[:10]  # Limit


def _translate_weekday(wd: str) -> str:
    """Translate English weekday name to Chinese."""
    mapping = {
        "Monday": "周一",
        "Tuesday": "周二",
        "Wednesday": "周三",
        "Thursday": "周四",
        "Friday": "周五",
        "Saturday": "周六",
        "Sunday": "周日",
    }
    return mapping.get(wd, wd)


async def _persist_learned_patterns(org_id: str, patterns: list[dict]):
    """Store learned patterns in org_memories, avoiding duplicates."""
    if not supabase:
        return

    for pattern in patterns:
        try:
            pattern_key = f"{pattern['type']}:{pattern['pattern'][:80]}"

            # Check if this exact pattern already exists
            existing = await (
                supabase.table("org_memories")
                .select("id, value")
                .eq("organization_id", org_id)
                .eq("category", "learned_pattern")
                .eq("key", pattern_key)
                .limit(1)
                .execute()
            )

            if existing.data:
                # Update frequency
                try:
                    old = json.loads(existing.data[0].get("value", "{}"))
                    old["frequency"] = max(
                        old.get("frequency", 0), pattern["frequency"]
                    )
                    await (
                        supabase.table("org_memories")
                        .update({"value": json.dumps(old, ensure_ascii=False)})
                        .eq("id", existing.data[0]["id"])
                        .execute()
                    )
                except (json.JSONDecodeError, KeyError):
                    pass
            else:
                # Insert new pattern
                await (
                    supabase.table("org_memories")
                    .insert(
                        {
                            "organization_id": org_id,
                            "scope": "organization",
                            "category": "learned_pattern",
                            "key": pattern_key,
                            "value": json.dumps(pattern, ensure_ascii=False),
                            "metadata": {},
                        }
                    )
                    .execute()
                )
        except Exception as e:
            logger.error(f"[PatternLearning] Persist pattern failed: {e}")
