"""P2.1 Semantic Tagging for Memory Fingerprinting.

Generates semantic tags from memory content for pre-filtering before
expensive vector search. Tags enable coarse-grained routing so that
retrieval can first filter by tag overlap, then do fine-grained cosine 
similarity within the smaller candidate set.

Tag taxonomy:
  - Domain tags:   crm, hr, finance, project, ...
  - Action tags:   preference, decision, instruction, fact, query, ...
  - Entity tags:   person_name, company, product, location, ...

Usage:
    from .semantic_tags import generate_semantic_tags

    tags = generate_semantic_tags(category, key, value)
    # → ["crm", "preference", "person:张总"]
"""

import logging
import re

logger = logging.getLogger(__name__)

# ── Domain keyword → tag mapping ─────────────────────────────────────────
_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "crm": ["客户", "商机", "线索", "跟进", "合同", "销售", "成交", "订单",
            "customer", "deal", "lead", "pipeline", "contract"],
    "hr": ["员工", "请假", "考勤", "入职", "离职", "薪资", "绩效", "招聘",
           "employee", "leave", "attendance", "salary", "onboarding"],
    "finance": ["报销", "预算", "发票", "账款", "财务", "费用", "收入",
                "expense", "budget", "invoice", "revenue"],
    "project": ["项目", "排期", "里程碑", "迭代", "冲刺", "需求", "版本",
                "project", "sprint", "milestone", "release"],
    "approval": ["审批", "审核", "签字", "流程", "工单",
                 "approval", "review", "workflow"],
    "document": ["文档", "报告", "手册", "规范", "制度", "政策",
                 "document", "report", "policy", "manual"],
    "communication": ["邮件", "会议", "通知", "消息", "日程",
                      "email", "meeting", "notification", "schedule"],
}

# ── Action tags inferred from category ────────────────────────────────────
_CATEGORY_ACTION_MAP: dict[str, str] = {
    "preference": "preference",
    "explicit_memory": "instruction",
    "fact": "fact",
    "behavior_pattern": "pattern",
    "usage_pattern": "usage",
    "tool_usage": "tool",
    "anti_pattern": "correction",
    "entity_query": "query",
    "policy": "policy",
    "document": "document",
    "episodic": "episode",
}

# ── Entity extraction patterns (lightweight, no LLM) ─────────────────────
_PERSON_PATTERN = re.compile(
    r"([\u4e00-\u9fff]{1,3}(?:总|经理|老师|先生|女士|主管|老板|组长|领导))"
)
_COMPANY_PATTERN = re.compile(
    r"([\u4e00-\u9fff]{2,8}(?:公司|集团|企业|科技|有限|股份|控股))"
)
_PRODUCT_PATTERN = re.compile(
    r"([\u4e00-\u9fff\w]{2,10}(?:系统|平台|产品|软件|工具|服务|方案))"
)


def generate_semantic_tags(
    category: str,
    key: str,
    value: str,
    *,
    fact_type: str | None = None,
) -> list[str]:
    """Generate semantic tags for a memory entry.

    Returns a deduplicated list of tags (max 8) for pre-filtering.

    Args:
        category: Memory category (preference, fact, etc.)
        key: Memory key identifier
        value: Memory content text
        fact_type: Optional fact type (fact/opinion/experience)

    Returns:
        List of semantic tag strings, e.g. ["crm", "preference", "person:张总"]
    """
    tags: list[str] = []
    combined_text = f"{key} {value}".lower()

    # 1) Domain tags — scan for domain keyword matches
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in combined_text:
                tags.append(domain)
                break  # One match per domain is enough

    # 2) Action tag from category
    action = _CATEGORY_ACTION_MAP.get(category)
    if action:
        tags.append(action)

    # 3) Fact type tag
    if fact_type and fact_type != "fact":
        tags.append(f"type:{fact_type}")

    # 4) Entity tags (lightweight regex extraction)
    # Person names
    persons = _PERSON_PATTERN.findall(value)
    for p in persons[:2]:
        tags.append(f"person:{p}")

    # Company names
    companies = _COMPANY_PATTERN.findall(value)
    for c in companies[:2]:
        tags.append(f"company:{c}")

    # Product/system names
    products = _PRODUCT_PATTERN.findall(value)
    for prod in products[:1]:
        tags.append(f"product:{prod}")

    # 5) Importance hints
    if any(kw in combined_text for kw in ["记住", "永远", "总是", "必须", "绝对"]):
        tags.append("high_priority")

    # Deduplicate and cap at 8
    seen: set[str] = set()
    unique: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:8]


def compute_tag_overlap(query_tags: list[str], memory_tags: list[str]) -> float:
    """Compute Jaccard-like overlap between query tags and memory tags.

    Returns a score between 0.0 and 1.0 indicating tag relevance.
    Used for coarse pre-filtering before vector similarity search.
    """
    if not query_tags or not memory_tags:
        return 0.0

    q_set = set(query_tags)
    m_set = set(memory_tags)
    intersection = q_set & m_set

    if not intersection:
        return 0.0

    # Use min-overlap (Szymkiewicz–Simpson) instead of full Jaccard
    # to avoid penalizing memories with many tags
    return len(intersection) / min(len(q_set), len(m_set))


def extract_query_tags(query: str) -> list[str]:
    """Extract semantic tags from a search query for pre-filtering.

    This is a lightweight tag extraction without LLM, optimized for
    real-time retrieval (< 1ms).
    """
    tags: list[str] = []
    lower_query = query.lower()

    # Domain tags
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in lower_query:
                tags.append(domain)
                break

    # Entity tags
    persons = _PERSON_PATTERN.findall(query)
    for p in persons[:2]:
        tags.append(f"person:{p}")

    companies = _COMPANY_PATTERN.findall(query)
    for c in companies[:1]:
        tags.append(f"company:{c}")

    # Deduplicate
    return list(dict.fromkeys(tags))[:6]
