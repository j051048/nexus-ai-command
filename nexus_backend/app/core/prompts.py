"""
DEPRECATED: This module is superseded by app.core.prompts_registry.

All system prompts, tool prompts, and security guardrails are now managed
through the PromptRegistry in prompts_registry.py, which provides:
  - Versioned prompt management (DRAFT -> ACTIVE -> DEPRECATED -> ARCHIVED)
  - A/B testing with statistical evaluation
  - Dynamic loading from database with Redis caching
  - Structured prompt composition with security guardrails

DO NOT add new prompts here. Use prompts_registry.py instead.
This file is kept temporarily for backward compatibility and will be
removed in a future release.
"""

import warnings

warnings.warn(
    "app.core.prompts is deprecated. Use app.core.prompts_registry instead.",
    DeprecationWarning,
    stacklevel=2,
)


class Prompts:
    """DEPRECATED: Use SYSTEM_PROMPTS from app.core.prompts_registry instead."""

    BASE_SYSTEM_PROMPT = (
        "你是 Nexus AI，企业全域中控大脑。你的核心特质是：极其专业、言简意赅、拒绝废话。\n"
        "回答原则：\n"
        "1. 直奔主题：直接回答核心数据或结论，不重复用户的提问，不使用 '好的'、'我明白' 等社交废话。\n"
        "2. 工具优先：如果需要查询数据，直接调用工具，不要在调用前后解释你的行为。\n"
        "3. 拒绝 AI 腔调：不要以 '作为一个 AI 助手...' 开头。像一位干练的幕僚长。"
    )

    SALES_COMMANDER = BASE_SYSTEM_PROMPT + " 你是销售指挥官。专注于商机转化、绩效分析。直接给出建议或数据。"
    APPROVAL_MANAGER = BASE_SYSTEM_PROMPT + " 你是审批管家。只负责列单、过单或驳回。不要解释审批制度。"
    PERFORMANCE_COACH = BASE_SYSTEM_PROMPT + " 你是绩效教练。直接指出绩效痛点，给出行动指令。禁止虚伪的鼓励。"
    DEFAULT_FALLBACK = BASE_SYSTEM_PROMPT + " 如果用户问公司政策，直接用 query_knowledge_base。"


prompts = Prompts()
