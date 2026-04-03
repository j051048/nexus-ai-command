"""P0 LoCoMo Fix: Temporal normalization - convert relative time to absolute dates."""

import re
from datetime import UTC, datetime, timedelta

# Relative time patterns (Chinese + English)
RELATIVE_TIME_PATTERNS = {
    # Days
    r'今天|today': 0,
    r'昨天|yesterday': -1,
    r'前天|day before yesterday': -2,
    r'明天|tomorrow': 1,
    r'后天|day after tomorrow': 2,

    # Weeks
    r'上周一|last monday': -7,
    r'上周二|last tuesday': -6,
    r'上周三|last wednesday': -5,
    r'上周四|last thursday': -4,
    r'上周五|last friday': -3,
    r'上周六|last saturday': -2,
    r'上周日|上周天|last sunday': -1,

    r'这周一|this monday': 0,
    r'本周一|this monday': 0,

    # Relative weeks
    r'上周|last week': -7,
    r'上上周|two weeks ago': -14,
    r'下周|next week': 7,

    # Months
    r'上个?月|last month': -30,
    r'下个?月|next month': 30,
}


def normalize_temporal_context(
    session_date: str,
    text: str,
    metadata: dict | None = None
) -> dict:
    """
    P0: 在存储前把相对时间转成绝对时间

    Args:
        session_date: 会话的绝对日期 (ISO format)
        text: 用户消息文本
        metadata: 现有 metadata

    Returns:
        增强后的 metadata，包含 session_absolute_date 和 temporal_anchors
    """
    meta = metadata or {}

    # Parse session date
    try:
        base_dt = datetime.fromisoformat(session_date.replace("Z", "+00:00"))
        if base_dt.tzinfo is None:
            base_dt = base_dt.replace(tzinfo=UTC)
    except Exception:
        base_dt = datetime.now(UTC)

    # Extract absolute dates already in text (YYYY-MM-DD, YYYY/MM/DD)
    absolute_dates = re.findall(
        r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b',
        text
    )

    # Convert relative time expressions to absolute dates
    temporal_anchors = []
    text_lower = text.lower()

    for pattern, offset in RELATIVE_TIME_PATTERNS.items():
        if re.search(pattern, text_lower):
            target_dt = base_dt + timedelta(days=offset)
            temporal_anchors.append(target_dt.strftime("%Y-%m-%d"))

    # Add already-absolute dates
    temporal_anchors.extend(absolute_dates)

    # Deduplicate
    temporal_anchors = list(set(temporal_anchors))

    # Update metadata
    meta['session_absolute_date'] = base_dt.strftime("%Y-%m-%d")
    if temporal_anchors:
        meta['temporal_anchors'] = temporal_anchors

    return meta


def extract_time_range_from_query(query: str) -> list[str] | None:
    """
    P1: 从问题中提取时间范围

    Returns:
        时间关键词列表，如 ['2023-06', 'June 2023', 'last week']
    """
    time_keywords = []

    # Extract absolute dates
    dates = re.findall(r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b', query)
    time_keywords.extend(dates)

    # Extract year-month
    year_months = re.findall(r'\b(\d{4}[-/]\d{1,2})\b', query)
    time_keywords.extend(year_months)

    # Extract relative time expressions
    relative_patterns = [
        r'上周|last week',
        r'上个月|last month',
        r'昨天|yesterday',
        r'今天|today',
        r'本周|this week',
        r'最近|recently',
    ]

    for pattern in relative_patterns:
        if re.search(pattern, query.lower()):
            time_keywords.append(pattern.split('|')[0])

    return time_keywords if time_keywords else None


def calculate_temporal_overlap(
    memory_anchors: list[str] | None,
    query_time_range: list[str] | None
) -> float:
    """
    P1: 计算记忆时间锚点与问题时间范围的重叠度

    Returns:
        0.0-1.0 的分数，越高表示时间越匹配
    """
    if not query_time_range or not memory_anchors:
        return 0.5  # 中性分数

    # Simple overlap check
    for q_time in query_time_range:
        for m_anchor in memory_anchors:
            if q_time in m_anchor or m_anchor in q_time:
                return 1.0  # 完全匹配

    return 0.0  # 无匹配


def rerank_by_temporal_relevance(
    query: str,
    memories: list[dict],
    boost_factor: float = 2.0
) -> list[dict]:
    """
    P1: 针对时间敏感问题，重排检索结果

    Args:
        query: 用户问题
        memories: 检索到的记忆列表
        boost_factor: 时间匹配的加权因子

    Returns:
        重排后的记忆列表
    """
    # Check if query is time-sensitive
    time_keywords = ['when', 'what time', '什么时候', '何时', '哪天', '几月', '几号']
    is_temporal_query = any(kw in query.lower() for kw in time_keywords)

    if not is_temporal_query:
        return memories  # 非时间问题，不重排

    # Extract time range from query
    query_time_range = extract_time_range_from_query(query)

    # Score and rerank
    scored = []
    for mem in memories:
        meta = mem.get('metadata', {})
        temporal_anchors = meta.get('temporal_anchors', [])

        time_score = calculate_temporal_overlap(temporal_anchors, query_time_range)

        # Boost score for time-matched memories
        final_score = mem.get('_score', 0.5) * (1 + time_score * boost_factor)

        scored.append((mem, final_score))

    # Sort by final score (descending)
    scored.sort(key=lambda x: x[1], reverse=True)

    return [mem for mem, _ in scored]
