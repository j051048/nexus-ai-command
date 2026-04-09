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
    # P1 Fix: 实体查询模式 "张三的宠物叫什么" → 提取实体名
    {
        "pattern": re.compile(r"([\u4e00-\u9fa5]{2,4})(?:的|负责|管理|喜欢|讨厌)(.{2,20})(?:叫什么|是什么|怎么样)"),
        "category": "entity_query",
        "key_prefix": "query",
        "importance": 0.6,
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
MEMORY_SIGNAL_WORDS = frozenset(
    {
        "记住",
        "以后",
        "每次",
        "总是",
        "永远",
        "我是",
        "我负责",
        "我们公司",
        "规定",
        "偏好",
        "习惯",
        "别给我",
        "不要",
        "我喜欢",
        "我讨厌",
        "我倾向",
        "帮我记",
        "请记住",
        "不是这个意思",
        "你又忘了",
        "你理解错了",
        "说了多少遍",
        # P1 Fix: 添加查询类信号词，触发实体提取
        "叫什么",
        "是什么",
        "喜欢什么",
        "讨厌什么",
        "负责什么",
    }
)

# ── LLM 提取频率控制（进程内，无需持久化）─────────────────────
_EXTRACT_COOLDOWN = 5  # 每 5 轮最多触发 1 次非信号词 LLM 提取
_last_extract: dict[str, int] = {}  # user_id → last_trigger_turn


def _recently_extracted(user_id: str, current_turn: int) -> bool:
    return (current_turn - _last_extract.get(user_id, -999)) < _EXTRACT_COOLDOWN


def _mark_extracted(user_id: str, current_turn: int) -> None:
    _last_extract[user_id] = current_turn
    if len(_last_extract) > 1000:
        sorted_keys = sorted(_last_extract, key=_last_extract.get)
        for k in sorted_keys[:500]:
            del _last_extract[k]


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

# ── Mining Mode Detection ───────────────────────────────────────────────
# Auto-detect conversation scene to select specialized extraction prompts.
_ENTITY_HINT_PATTERN = re.compile(
    r"[\u4e00-\u9fa5]{2,4}(?:的|负责|管理|在|属于|是)" r"|(?:公司|部门|团队|项目|客户)[\u4e00-\u9fa5]{2,8}"
)


def _detect_mining_mode(messages: list[dict[str, str]]) -> str:
    """检测对话挖掘模式，选择最优提取策略。

    Returns:
        'work_ops'    — 含工具调用的工作流对话，重点提取决策和操作模式
        'entity_info' — 涉及人物/组织/项目的实体对话，重点提取事实和关系
        'casual'      — 默认闲聊/偏好对话
    """
    tool_signals = 0
    entity_signals = 0

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # work_ops: tool messages or tool_call JSON in content
        if role == "tool":
            tool_signals += 2
        elif '"tool_call"' in content or '"function_call"' in content:
            tool_signals += 1

        # work_ops: business operation keywords
        if role == "user":
            for kw in TOOL_USAGE_KEYWORDS:
                if kw in content:
                    tool_signals += 1

            # entity_info: person/org/project mentions
            if _ENTITY_HINT_PATTERN.search(content):
                entity_signals += 1

    if tool_signals >= 2:
        return "work_ops"
    if entity_signals >= 1:
        return "entity_info"
    return "casual"


async def _update_behavior_preferences(
    user_id: str,
    detected: dict[str, str],
    db: Any = None,
    org_id: str | None = None,
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
        query = client.table("ai_settings").select("behavior_preferences").eq("user_id", user_id)
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
        effective_org_id = org_id or "00000000-0000-0000-0000-000000000000"

        # Upsert (composite unique: user_id + organization_id)
        upsert_data = {
            "user_id": user_id,
            "organization_id": effective_org_id,
            "base_url": "",  # 必填字段，空字符串表示使用默认
            "behavior_preferences": merged,
        }

        await client.table("ai_settings").upsert(upsert_data, on_conflict="user_id,organization_id").execute()
        logger.info(f"[BehaviorPref] Updated behavior preferences for {user_id} (Org: {effective_org_id}): {detected}")
    except Exception as e:
        logger.error(f"[BehaviorPref] Failed to update preferences: {e}")


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
    recent_msgs = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages[-5:] if m.get("content")]
    context_summary = "\n".join(recent_msgs)[:500]

    # 构建待补全列表
    values_text = "\n".join(f"[{i}] {entries[idx]['value']}" for i, (idx, _) in enumerate(enrichable))

    prompt = (
        f"以下是对话上下文和从中提取的记忆片段。\n"
        f"请对每条记忆做最小改动，使其脱离对话上下文后仍可独立理解：\n"
        f"1. 将代词（他/她/它/该/这个/那个）替换为具体名词\n"
        f"2. 如果片段缺少主语或关键背景，从上下文中补充\n"
        f"3. 不要改变原意、不要添加新信息\n\n"
        f"[对话上下文]\n{context_summary}\n\n"
        f"[记忆片段]\n{values_text}\n\n"
        f'按JSON数组返回补全后的文本，格式: ["补全后的片段0", "补全后的片段1", ...]'
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

        json_match = re.search(r"\[.*\]", clean, re.DOTALL)
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

    # 3) LLM-assisted deep extraction
    #    Skip for subtask conversations — assistant response contains delegated
    #    tool output that may be misinterpreted as user preferences.
    user_texts = " ".join(msg.get("content", "") for msg in messages if msg.get("role") == "user")
    user_msg_count = sum(1 for m in messages if m.get("role") == "user")

    # 三条件触发（满足任一即可）：
    # 1. 信号词命中（快速路径，始终触发）
    has_signal = any(w in user_texts for w in MEMORY_SIGNAL_WORDS)
    # 2. 实质性对话（>= 50 字 + >= 3 轮）且未在冷却期内（捕获隐式偏好）
    is_substantial = len(user_texts) >= 50 and user_msg_count >= 3 and not _recently_extracted(user_id, user_msg_count)
    should_extract = has_signal or is_substantial

    if not is_subtask and should_extract:
        mining_mode = _detect_mining_mode(messages)
        llm_extracted = await extract_with_llm(messages, mining_mode=mining_mode)
        if not has_signal:
            _mark_extracted(user_id, user_msg_count)
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
    mining_mode: str = "casual",
) -> list[dict]:
    """Use LLM to extract implicit preferences and facts from conversation.

    Args:
        messages: Conversation messages
        mining_mode: 'work_ops' | 'entity_info' | 'casual' — selects specialized prompt
    """
    user_texts = [msg["content"] for msg in messages if msg.get("role") == "user" and msg.get("content")]
    if not user_texts:
        return []

    # Only process if there's substantial content
    combined = "\n".join(user_texts[-5:])  # last 5 user messages
    if len(combined) < 10:
        return []

    try:
        # Inject current date so LLM can resolve relative time references
        from datetime import UTC
        from datetime import datetime as _dt

        from app.services.ai_service import AIService

        from .llm_utils import parse_llm_json

        today_str = _dt.now(UTC).strftime("%Y-%m-%d")

        prompt = f"以下是用户在对话中说的话：\n\n{combined}"

        # Shared JSON output format instructions (appended to all modes)
        _json_format = (
            "严格以JSON数组格式返回，每个元素包含：\n"
            '- "category": "preference" 或 "explicit_memory" 或 "fact" 或 "entity_query"\n'
            '- "fact_type": "fact"（客观事实）/ "opinion"（主观偏好）/ "experience"（个人经历）/ "entity_query"（实体查询）\n'
            '- "confidence": 0.0-1.0 置信度\n'
            '- "key": 简短的标识键（如 "张三.宠物"、"李四.喜好"）\n'
            '- "value": 提取的完整信息\n'
            '- "pattern_key": 稳定的模式标识\n'
            '- "importance": 0.0-1.0 的重要性评分\n'
            '- "valid_from": 该信息的生效日期，ISO格式\n'
            '- "valid_until": 该信息的结束日期（可选）\n\n'
            "只返回JSON数组，不要其他文字。最多提取5条。"
        )

        if mining_mode == "work_ops":
            system = (
                f"你是工作流记忆提取专家。当前日期: {today_str}。\n"
                "从用户的工具操作对话中提取值得长期记住的工作模式：\n"
                "- 决策模式（用户选择了什么方案、为什么选择）\n"
                "- 工具链偏好（用户习惯的操作顺序和组合）\n"
                "- 操作上下文（涉及的项目、客户、数据范围）\n"
                "- 失败/重试模式（什么操作失败了、用户如何修正）\n\n"
                "不要提取：工具的原始输出数据、临时性查询结果。\n"
                "如果没有值得提取的信息，返回空数组 []。\n"
                "importance 范围建议: 0.5-0.8（操作模式比闲聊更重要）\n"
                "fact_type 偏向: experience（工作经验）\n\n" + _json_format
            )
        elif mining_mode == "entity_info":
            system = (
                f"你是实体信息提取专家。当前日期: {today_str}。\n"
                "从对话中提取关于人物、组织、项目的事实信息：\n"
                "- 实体属性（某人的职位、某公司的地址、某项目的状态）\n"
                "- 实体关系（谁负责什么、谁汇报给谁、谁是谁的客户）\n"
                "- 实体状态变化（某人从A部门调到B部门、某项目从进行中变为完成）\n"
                "- 用户关心的实体查询（即使答案未知也记录问题本身）\n\n"
                "不要提取：临时性的问题、礼貌用语。\n"
                "如果没有值得提取的信息，返回空数组 []。\n"
                "importance 范围建议: 0.6-0.9（实体事实通常较重要）\n"
                "fact_type 偏向: fact（客观事实）\n\n" + _json_format
            )
        else:  # casual
            system = (
                f"你是记忆提取专家。当前日期: {today_str}。从用户的对话中提取值得长期记住的信息。\n"
                "提取以下类型的信息：\n"
                "- 用户的身份、职位、负责区域等个人信息\n"
                "- 用户的工作习惯和偏好（如报告格式、沟通方式）\n"
                "- 用户提到的重要事实（如客户群体、业务方向）\n"
                "- 用户的明确要求和指令（如'以后都用表格'）\n"
                "- 用户查询的实体信息（如'张三的宠物'、'李四喜欢什么'），即使查询结果为空也要记录\n\n"
                "不要提取：临时性的问题、一次性的查询、礼貌用语。\n"
                "如果没有值得提取的信息，返回空数组 []。\n\n"
                "反例（不要提取）：\n"
                "- ❌ '今天天气怎么样' → 临时查询\n"
                "- ❌ '谢谢你的帮助' → 礼貌用语\n"
                "正例（应该提取）：\n"
                "- ✅ '我是华东区销售经理' → fact, confidence=1.0\n"
                "- ✅ '我喜欢用表格展示数据' → opinion, confidence=0.8\n"
                "- ✅ '张三的宠物叫什么' → entity_query, confidence=0.7（记录用户关心的实体）\n\n" + _json_format
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
                    "valid_from": item.get("valid_from") or today_str,
                    "fact_type": (
                        item.get("fact_type", "fact")
                        if item.get("fact_type") in ("fact", "opinion", "experience")
                        else "fact"
                    ),
                    "confidence": min(max(float(item.get("confidence", 1.0)), 0.0), 1.0),
                    **({"valid_until": item["valid_until"]} if item.get("valid_until") else {}),
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
