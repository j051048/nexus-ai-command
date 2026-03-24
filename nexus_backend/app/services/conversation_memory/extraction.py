"""Memory extraction from conversations: regex patterns + LLM-assisted extraction."""

import contextlib
import hashlib
import json as _json
import logging
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)


# --- Preference extraction patterns ---

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
        "importance": 0.65,
    },
    # "记住..." / "请记住..." / "帮我记..."
    {
        "pattern": re.compile(r"(?:请?记住|帮我记|记一下)(.{2,80})"),
        "category": "explicit_memory",
        "key_prefix": "remember",
        "importance": 0.85,
    },
    # "我是..." / "我的...是..."
    {
        "pattern": re.compile(r"我(?:是|叫|的名字是)(.{2,30})"),
        "category": "preference",
        "key_prefix": "identity",
        "importance": 0.8,
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
        "category": "preference",
        "key_prefix": "contact",
        "importance": 0.75,
    },
    # Anti-pattern: user correcting Agent behavior ("你又忘了", "不是这个意思")
    {
        "pattern": re.compile(
            r"(?:不是这个意思|你又忘了|我说的不是|你理解错了|不对[，,]|"
            r"我之前说过|跟你说过|说了多少遍|不是让你|你搞错了|错了[，,])"
            r"(.{2,80})"
        ),
        "category": "anti_pattern",
        "key_prefix": "correction",
        "importance": 0.8,
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

# Signal words that indicate a message may contain memorizable content
# Only trigger LLM extraction when these words are present
MEMORY_SIGNAL_WORDS = frozenset({
    "记住", "以后", "每次", "总是", "永远", "我是", "我负责",
    "我们公司", "规定", "偏好", "习惯", "别给我", "不要",
    "我喜欢", "我讨厌", "我倾向", "帮我记", "请记住",
    "不是这个意思", "你又忘了", "你理解错了", "说了多少遍",
})

# Behavior preference patterns — auto-detect and write to ai_settings.behavior_preferences
# Each entry: (pattern, preference_key, preference_value)
BEHAVIOR_PREF_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # Response style
    (re.compile(r"(?:简洁|简短|精简|简要)(?:一点|些|地)?(?:回答|回复|说)?"), "response_style", "concise"),
    (re.compile(r"(?:详细|详尽|展开|具体)(?:一点|些|地)?(?:回答|回复|说|解释)?"), "response_style", "detailed"),
    # Language preference
    (re.compile(r"(?:用|请用|以后用)英文(?:回答|回复)?"), "language", "en"),
    (re.compile(r"(?:用|请用|以后用)中文(?:回答|回复)?"), "language", "zh"),
    # Chart preference
    (re.compile(r"(?:用|我喜欢|偏好)(?:柱状图|柱形图|条形图)"), "preferred_chart", "bar"),
    (re.compile(r"(?:用|我喜欢|偏好)(?:折线图|线图|趋势图)"), "preferred_chart", "line"),
    (re.compile(r"(?:用|我喜欢|偏好)(?:饼图|饼状图|圆形图)"), "preferred_chart", "pie"),
    (re.compile(r"(?:用|我喜欢|偏好)(?:面积图|区域图)"), "preferred_chart", "area"),
]


async def _update_behavior_preferences(
    user_id: str, detected: dict[str, str], db: Any = None, org_id: str | None = None,
) -> None:
    """Write detected behavior preferences to ai_settings.behavior_preferences (JSONB merge)."""
    if not detected:
        return
    try:
        from app.core.database import supabase
        client = db or supabase
        if not client:
            return
        # Read current preferences
        query = (
            client.table("ai_settings")
            .select("behavior_preferences")
            .eq("user_id", user_id)
        )
        if org_id:
            query = query.eq("organization_id", org_id)
        result = await query.maybe_single().execute()
        current = (result.data or {}).get("behavior_preferences", {}) if result.data else {}
        if not isinstance(current, dict):
            current = {}
        # Merge detected preferences
        merged = {**current, **detected}
        if merged == current:
            return  # No change

        # Ensure we always provide organization_id to match the UNIQUE(user_id, organization_id) constraint
        # Use the system default UUID if org_id is missing, as defined in migration 20260211
        effective_org_id = org_id or '00000000-0000-0000-0000-000000000000'
        
        # Upsert (composite unique: user_id + organization_id)
        upsert_data = {
            "user_id": user_id,
            "organization_id": effective_org_id,
            "behavior_preferences": merged
        }
        
        await (
            client.table("ai_settings")
            .upsert(upsert_data, on_conflict="user_id,organization_id")
            .execute()
        )
        logger.info(f"[BehaviorPref] Updated behavior preferences for {user_id} (Org: {effective_org_id}): {detected}")
    except Exception as e:
        logger.debug(f"[BehaviorPref] Failed to update preferences: {e}")


async def _enrich_memory_values(
    entries: list[dict],
    messages: list[dict[str, str]],
) -> list[dict]:
    """P0 滑动窗口预处理：对提取的记忆做上下文补全，使每条记忆自包含。

    用 mini 模型做代词消解和缺失主语补全。
    例如 "他觉得方案不行" → "华为的张总觉得微服务迁移方案不可行"
    失败时返回原始 entries（非致命）。
    """
    # 只处理长度 > 10 的 value（太短的无需补全）
    enrichable = [(i, e) for i, e in enumerate(entries) if len(e.get("value", "")) > 10]
    if not enrichable:
        return entries

    # 构建对话上下文摘要（最近 5 条消息，截取前 500 字符）
    recent_msgs = [
        f"{m.get('role', 'user')}: {m.get('content', '')}"
        for m in messages[-5:]
        if m.get("content")
    ]
    context_summary = "\n".join(recent_msgs)[:500]

    # 构建待补全列表
    values_text = "\n".join(
        f"[{i}] {entries[idx]['value']}" for i, (idx, _) in enumerate(enrichable)
    )

    prompt = (
        f"以下是对话上下文和从中提取的记忆片段。\n"
        f"请对每条记忆做最小改动，使其脱离对话上下文后仍可独立理解：\n"
        f"1. 将代词（他/她/它/该/这个/那个）替换为具体名词\n"
        f"2. 如果片段缺少主语或关键背景，从上下文中补充\n"
        f"3. 不要改变原意、不要添加新信息\n\n"
        f"[对话上下文]\n{context_summary}\n\n"
        f"[记忆片段]\n{values_text}\n\n"
        f"按JSON数组返回补全后的文本，格式: [\"补全后的片段0\", \"补全后的片段1\", ...]"
    )

    try:
        from app.services.ai_service import AIService

        result_text = await AIService.call_llm(prompt, "你是记忆预处理助手。")

        # Parse JSON array
        clean = result_text.strip()
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()

        json_match = re.search(r'\[.*\]', clean, re.DOTALL)
        if json_match:
            results = _json.loads(json_match.group())
            enriched_count = 0
            for j, (orig_idx, _) in enumerate(enrichable):
                if j < len(results) and isinstance(results[j], str) and len(results[j]) > 5:
                    enriched_val = results[j]
                    # 保存原始 value 和补全后的 enriched_value
                    entries[orig_idx]["enriched_value"] = enriched_val
                    enriched_count += 1

            if enriched_count > 0:
                logger.info(f"[Memory] Enriched {enriched_count} memory values with context")

    except Exception as e:
        logger.debug(f"[Memory] Memory value enrichment skipped (non-fatal): {e}")

    return entries


async def extract_preferences(
    user_id: str,
    messages: list[dict[str, str]],
    org_id: str | None = None,
    db: Any = None,
    *,
    save_memory_fn=None,
    is_subtask: bool = False,
) -> list[dict]:
    """
    从对话中自动提取用户偏好。

    双引擎策略：
    1. 规则引擎（快速路径）：正则匹配明确的偏好表达
    2. LLM 增强（深度提取）：捕获复杂语义中的隐含偏好

    save_memory_fn: async callable used to persist each extracted entry.
    is_subtask: if True, skip LLM deep extraction (subtask outputs may pollute).
                Regex extraction still runs since it only scans user messages.
    """
    extracted: list[dict] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Only extract from user messages
        if role != "user" or not content:
            continue

        # 1) Pattern-based preference extraction (fast path)
        for pattern_info in PREFERENCE_PATTERNS:
            matches = pattern_info["pattern"].findall(content)
            for match in matches:
                match_text = match.strip().rstrip("。，,.")
                if len(match_text) < 2:
                    continue

                content_hash = hashlib.md5(match_text.encode()).hexdigest()[:8]
                key = f"{pattern_info['key_prefix']}_{content_hash}"
                # Use pattern-specific importance if defined, else category defaults
                default_imp = 0.7 if pattern_info["category"] == "explicit_memory" else 0.5
                # Generate stable pattern_key for dedup
                pattern_key = f"{pattern_info['category']}:{pattern_info['key_prefix']}"
                entry = {
                    "key": key,
                    "value": match_text,
                    "category": pattern_info["category"],
                    "importance": pattern_info.get("importance", default_imp),
                    "pattern_key": pattern_key,
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
                    "pattern_key": f"usage_pattern:{action}",
                }
                # Avoid duplicates within this batch
                if not any(e["key"] == entry["key"] for e in extracted):
                    extracted.append(entry)

    # 2.5) Anti-pattern context enrichment — capture what Agent did wrong
    for entry in extracted:
        if entry["category"] == "anti_pattern":
            # Find the user message containing this correction
            for i, msg in enumerate(messages):
                if msg.get("role") == "user" and entry["value"] in msg.get("content", ""):
                    # Look backwards for the nearest assistant response
                    for j in range(i - 1, -1, -1):
                        if messages[j].get("role") == "assistant":
                            prev_resp = messages[j].get("content", "")[:200]
                            entry["value"] = f"用户纠正: {entry['value']} | Agent之前回复: {prev_resp}"
                            break
                    break

    # 3) LLM-assisted deep extraction (only when signal words are present)
    #    Skip for subtask conversations — assistant response contains delegated
    #    tool output that may be misinterpreted as user preferences.
    user_texts = " ".join(
        msg.get("content", "") for msg in messages if msg.get("role") == "user"
    )
    if not is_subtask and any(w in user_texts for w in MEMORY_SIGNAL_WORDS):
        llm_extracted = await extract_with_llm(messages)
    else:
        llm_extracted = []
    if llm_extracted:
        existing_values = {e["value"] for e in extracted}
        for entry in llm_extracted:
            if entry["value"] not in existing_values:
                extracted.append(entry)

    # P0: 滑动窗口预处理 — 上下文补全
    if extracted:
        extracted = await _enrich_memory_values(extracted, messages)

    # S5: Auto-detect behavior preferences and write to ai_settings
    behavior_detected: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        for pattern, pref_key, pref_value in BEHAVIOR_PREF_PATTERNS:
            if pattern.search(content):
                behavior_detected[pref_key] = pref_value
    if behavior_detected:
        with contextlib.suppress(Exception):
            await _update_behavior_preferences(user_id, behavior_detected, db=db, org_id=org_id)

    # Save extracted memories — with conflict resolution if possible
    saved: list[dict] = []

    if save_memory_fn is not None:
        # Custom save function provided (e.g. tests) — use it directly
        for entry in extracted:
            try:
                result = await save_memory_fn(
                    user_id=user_id,
                    key=entry["key"],
                    value=entry["value"],
                    category=entry["category"],
                    importance=entry.get("importance", 0.5),
                    org_id=org_id,
                    db=db,
                    enriched_value=entry.get("enriched_value"),
                    valid_from=entry.get("valid_from"),
                )
                saved.append(result)
            except Exception as e:
                logger.warning(f"Failed to save extracted memory: {e}")
    else:
        # Default path: use conflict resolution for smarter save
        try:
            from .conflict_resolution import resolve_memory_conflicts

            results = await resolve_memory_conflicts(
                user_id=user_id,
                new_memories=extracted,
                org_id=org_id,
                db=db,
            )
            saved = [r for r in results if r.get("event") in ("ADD", "UPDATE", "DEDUP")]
        except Exception as e:
            logger.warning(f"Conflict resolution failed, falling back to direct save: {e}")
            # Fallback: direct save without conflict resolution
            from .storage import save_memory as _save_memory_fn

            for entry in extracted:
                try:
                    result = await _save_memory_fn(
                        user_id=user_id,
                        key=entry["key"],
                        value=entry["value"],
                        category=entry["category"],
                        importance=entry.get("importance", 0.5),
                        org_id=org_id,
                        db=db,
                        enriched_value=entry.get("enriched_value"),
                        valid_from=entry.get("valid_from"),
                        pattern_key=entry.get("pattern_key"),
                    )
                    saved.append(result)
                except Exception as e2:
                    logger.warning(f"Fallback save failed: {e2}")

    if saved:
        logger.info(f"Extracted {len(saved)} memories from conversation for user {user_id}")

    return saved


async def extract_with_llm(
    messages: list[dict[str, str]],
) -> list[dict]:
    """Use LLM to extract implicit preferences and facts from conversation.

    Only processes user messages, returns structured memory entries.
    Designed to catch semantics that regex patterns miss, such as:
    - "我们的主要客户群体是制造业中大型企业"
    - "报告用表格形式比较好"
    - "我负责华东区的大客户"
    """
    user_texts = [msg["content"] for msg in messages if msg.get("role") == "user" and msg.get("content")]
    if not user_texts:
        return []

    # Only process if there's substantial content
    combined = "\n".join(user_texts[-5:])  # last 5 user messages
    if len(combined) < 10:
        return []

    try:
        from app.services.ai_service import AIService

        from .llm_utils import parse_llm_json

        prompt = f"以下是用户在对话中说的话：\n\n{combined}"
        system = (
            "你是记忆提取专家。从用户的对话中提取值得长期记住的信息。\n"
            "提取以下类型的信息：\n"
            "- 用户的身份、职位、负责区域等个人信息\n"
            "- 用户的工作习惯和偏好（如报告格式、沟通方式）\n"
            "- 用户提到的重要事实（如客户群体、业务方向）\n"
            "- 用户的明确要求和指令（如'以后都用表格'）\n\n"
            "不要提取：临时性的问题、一次性的查询、礼貌用语。\n"
            "如果没有值得提取的信息，返回空数组 []。\n\n"
            "严格以JSON数组格式返回，每个元素包含：\n"
            '- "category": "preference" 或 "explicit_memory" 或 "fact"\n'
            '- "key": 简短的标识键（如 "role_region"、"report_format"）\n'
            '- "value": 提取的完整信息\n'
            '- "pattern_key": 稳定的模式标识（如 "preference:report_format"、"fact:role_region"），'
            "格式为 category:主题，同类信息应使用相同的 pattern_key\n"
            '- "importance": 0.0-1.0 的重要性评分，评分标准:\n'
            "  * 0.8-1.0: 身份信息、核心偏好、明确指令（如'以后都用表格'）\n"
            "  * 0.5-0.7: 工作习惯、常用功能、业务方向\n"
            "  * 0.3-0.4: 一般性事实、临时偏好、单次提及\n"
            '- "valid_from": (可选) 如果信息涉及具体时间点（如"上个月搬了新办公室"、'
            '"去年加入公司"），输出该事实的大致生效日期，ISO格式如 "2026-02-01"。'
            "无明确时间信息则不输出此字段。\n\n"
            "只返回JSON数组，不要其他文字。最多提取5条。"
        )

        result_text = await AIService.call_llm(prompt, system)

        # Parse JSON from LLM response (using shared utility)
        items = parse_llm_json(result_text)
        if not isinstance(items, list):
            return []

        extracted = []
        for item in items[:5]:
            if not isinstance(item, dict):
                continue
            category = item.get("category", "preference")
            if category not in ("preference", "explicit_memory", "fact"):
                category = "preference"
            key = item.get("key", f"llm_{uuid.uuid4().hex[:6]}")
            value = item.get("value", "")
            if not value or len(value) < 3:
                continue
            extracted.append(
                {
                    "key": f"llm_{key}",
                    "value": value,
                    "category": category,
                    "importance": min(max(float(item.get("importance", 0.5)), 0.1), 1.0),
                    "pattern_key": item.get("pattern_key") or f"{category}:{key}",
                    **({"valid_from": item["valid_from"]} if item.get("valid_from") else {}),
                }
            )

        if extracted:
            logger.info(f"LLM extracted {len(extracted)} memories from conversation")
        return extracted

    except Exception as e:
        logger.debug(f"LLM memory extraction skipped: {e}")
        return []


async def extract_org_memories(
    org_id: str,
    user_id: str,
    message: str,
    ai_response: str,
    db: Any = None,
    *,
    save_org_memory_fn=None,
) -> list[dict]:
    """
    Extract potential organization-level knowledge from conversations.
    Rules-based extraction for common patterns.

    save_org_memory_fn: async callable used to persist each extracted entry.
    """
    extracted: list[dict] = []

    # Pattern: "我们公司..." / "公司规定..." / "组织要求..."
    org_patterns = [
        (re.compile(r"(?:我们公司|公司规定|组织要求|团队规则|部门规定)[：:是]?\s*(.{5,100})"), "preference"),
        (re.compile(r"(?:记住|请记住|注意)[：:，,]\s*(?:我们|公司|组织)(.{5,100})"), "preference"),
        (re.compile(r"(?:客户|供应商|合作伙伴)\s*[\w\u4e00-\u9fff]+\s*(?:的|是).{5,80}"), "knowledge"),
        (re.compile(r"(?:以后|今后|从现在起).{3,50}(?:都要|必须|应该|需要).{5,50}"), "preference"),
    ]

    if save_org_memory_fn is None:
        from .org_memory import save_org_memory as save_org_memory_fn  # noqa: N811

    for pattern, category in org_patterns:
        matches = pattern.findall(message)
        for match in matches[:3]:  # Max 3 per pattern
            clean = match.strip().rstrip("。.!！")
            if len(clean) >= 5:
                key = clean[:100]
                saved = await save_org_memory_fn(
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
