"""
Friendly error message mapper for tool execution failures.

Maps technical errors to user-friendly Chinese messages with actionable suggestions.
Used by node_execute.py to improve user experience when tools fail.
"""

import re


# ── Pattern → friendly message mapping ──────────────────────────────────

_FRIENDLY_MESSAGES: list[tuple[re.Pattern, str, str | None]] = [
    # (pattern, friendly_message, follow_up_suggestion)

    # --- Duplicate / Conflict ---
    (re.compile(r"duplicate|already\s*exist|unique.*constraint|重复", re.I),
     "该记录已存在，无法重复创建。",
     "要我帮您搜索已有的记录吗？"),

    (re.compile(r"conflict|version.*mismatch|并发冲突", re.I),
     "数据已被其他人修改，请刷新后重试。",
     None),

    # --- Permission / Auth ---
    (re.compile(r"permission|forbidden|403|权限不足|access.*denied|unauthorized|401", re.I),
     "您没有执行此操作的权限。",
     "请联系管理员获取相应权限。"),

    (re.compile(r"row.*level.*security|rls|policy", re.I),
     "数据访问受限，您只能操作自己负责的数据。",
     None),

    # --- Not Found ---
    (re.compile(r"not\s*found|404|找不到|no.*rows|does\s*not\s*exist|PGRST116", re.I),
     "未找到相关记录，可能已被删除或不存在。",
     "要我帮您重新搜索吗？"),

    # --- Column / Schema ---
    (re.compile(r"column.*not.*exist|PGRST204|undefined.*column|未知.*列|字段.*不存在", re.I),
     "数据结构有变化，请联系管理员检查。",
     None),

    (re.compile(r"null.*constraint|not.*null|必填.*为空|required.*missing", re.I),
     "缺少必填信息，请补充完整后再试。",
     "请告诉我缺少的信息，我来帮您补充。"),

    # --- Type / Value ---
    (re.compile(r"type.*mismatch|invalid.*input|格式.*错误|invalid.*value|check.*constraint", re.I),
     "输入的数据格式不正确，请检查后重试。",
     None),

    (re.compile(r"numeric.*overflow|out.*range|value.*too.*large|超出范围", re.I),
     "输入的数值超出允许范围，请调整后重试。",
     None),

    # --- Network / Timeout ---
    (re.compile(r"timeout|timed?\s*out|超时|deadline.*exceeded", re.I),
     "操作超时，系统正在重试中...",
     None),

    (re.compile(r"connection.*(?:refused|reset|error)|network|ECONNREFUSED|网络", re.I),
     "网络连接异常，请稍后再试。",
     None),

    # --- Rate Limit ---
    (re.compile(r"rate.*limit|too.*many.*request|429|请求过于频繁", re.I),
     "请求过于频繁，请稍等片刻后重试。",
     None),

    # --- Foreign Key ---
    (re.compile(r"foreign.*key|reference.*constraint|关联.*不存在", re.I),
     "关联的数据不存在，请先确认相关记录是否已创建。",
     None),

    # --- LLM / AI ---
    (re.compile(r"context.*length|token.*limit|上下文.*过长", re.I),
     "对话内容过长，我来简化一下重新处理。",
     None),

    (re.compile(r"model.*overloaded|capacity|AI.*繁忙|server.*overload|503", re.I),
     "AI 服务暂时繁忙，正在排队处理...",
     None),

    # --- Quota ---
    (re.compile(r"quota.*exceeded|usage.*limit|配额.*用尽|token.*exceeded", re.I),
     "本月使用额度已用完。",
     "请联系管理员升级套餐或等待下月重置。"),
]

# ── Default messages by error type ──────────────────────────────────────

_DEFAULT_BY_TYPE = {
    "retryable": ("操作暂时失败，正在为您重试...", None),
    "param_error": ("参数有误，请检查输入信息后重试。", "请告诉我正确的信息，我来重新处理。"),
    "fatal": ("操作失败，请稍后重试或联系管理员。", None),
}


def map_error_to_friendly(
    error_type: str,
    raw_error: str,
    tool_name: str = "",
) -> tuple[str, str | None]:
    """Map a technical error to a user-friendly Chinese message.

    Args:
        error_type: One of 'retryable', 'param_error', 'fatal'
        raw_error: The raw error string from tool execution
        tool_name: Optional tool name for context-specific messages

    Returns:
        (friendly_message, follow_up_suggestion_or_none)
    """
    for pattern, message, suggestion in _FRIENDLY_MESSAGES:
        if pattern.search(raw_error):
            return message, suggestion

    return _DEFAULT_BY_TYPE.get(error_type, _DEFAULT_BY_TYPE["fatal"])


def format_friendly_error(
    error_type: str,
    raw_error: str,
    tool_name: str = "",
) -> str:
    """Format a complete user-friendly error response.

    Returns a ready-to-display error message with optional follow-up suggestion.
    """
    message, suggestion = map_error_to_friendly(error_type, raw_error, tool_name)

    parts = [f"⚠️ {message}"]
    if suggestion:
        parts.append(f"\n💡 {suggestion}")

    return "".join(parts)
