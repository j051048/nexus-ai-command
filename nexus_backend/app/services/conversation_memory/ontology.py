"""
记忆宫殿 Ontology Schema — 知识图谱的骨架约束。

设计原则：
1. 冷启动时由工程侧预定义核心域（记忆宫殿的"固定房间布局"）
2. 每个 entity_type 绑定 domain，支持跨域关系但类型受控
3. relationship 类型从自由文本收敛为受控词表
4. 未识别的类型/关系通过 normalize 映射到最近的合法类型
5. 支持运行时动态扩展（通过 register_domain 添加新域）

类比说明：
- Domain = 记忆宫殿的"楼层"
- EntityType = 楼层内的"房间类型"
- RelationshipType = 房间之间的"走廊标识"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from difflib import get_close_matches

logger = logging.getLogger(__name__)

# ── 核心数据结构 ──


@dataclass
class DomainSchema:
    """单个业务域的 Schema 定义"""

    name: str
    display_name: str
    entity_types: list[str]
    allowed_relationships: list[str]
    canonical_attributes: dict[str, list[str]] = field(default_factory=dict)


# ── 预定义域 ──

_DOMAIN_REGISTRY: dict[str, DomainSchema] = {}


def _init_domains() -> None:
    """初始化核心业务域"""
    domains = [
        DomainSchema(
            name="crm",
            display_name="客户关系",
            entity_types=["customer", "contact", "deal", "competitor", "lead"],
            allowed_relationships=[
                "属于",
                "负责",
                "合作",
                "竞争",
                "签约",
                "跟进",
                "推荐",
                "转化",
                "流失",
                "关联",
                "报价",
                "成交",
            ],
            canonical_attributes={
                "customer": ["name", "industry", "stage", "region", "value"],
                "deal": ["amount", "stage", "probability", "close_date"],
                "contact": ["name", "role", "phone", "email"],
            },
        ),
        DomainSchema(
            name="hr",
            display_name="人力资源",
            entity_types=["employee", "department", "position", "policy", "team"],
            allowed_relationships=[
                "隶属",
                "管理",
                "汇报给",
                "担任",
                "适用",
                "违反",
                "属于",
                "调动",
                "晋升",
                "带领",
            ],
            canonical_attributes={
                "employee": ["name", "department", "position", "hire_date"],
                "department": ["name", "head", "budget"],
            },
        ),
        DomainSchema(
            name="approval",
            display_name="审批流程",
            entity_types=["approval_flow", "approval_node", "approver", "request"],
            allowed_relationships=[
                "包含",
                "审批",
                "驳回",
                "转交",
                "催办",
                "提交",
                "属于",
                "关联",
                "发起",
                "结束",
            ],
        ),
        DomainSchema(
            name="finance",
            display_name="财务",
            entity_types=["account", "budget", "expense", "invoice", "receipt"],
            allowed_relationships=[
                "归属",
                "报销",
                "预算内",
                "超支",
                "关联",
                "支付",
                "开票",
                "审核",
                "冲销",
            ],
        ),
        DomainSchema(
            name="oa",
            display_name="办公自动化",
            entity_types=["task", "meeting", "announcement", "document", "schedule"],
            allowed_relationships=[
                "分配给",
                "参加",
                "创建",
                "关联",
                "通知",
                "属于",
                "完成",
                "延期",
                "取消",
            ],
        ),
        DomainSchema(
            name="knowledge",
            display_name="知识库",
            entity_types=["article", "category", "tag", "faq"],
            allowed_relationships=[
                "属于",
                "引用",
                "补充",
                "替代",
                "关联",
                "解答",
            ],
        ),
        DomainSchema(
            name="general",
            display_name="通用知识",
            entity_types=[
                "person",
                "organization",
                "project",
                "concept",
                "product",
                "location",
                "event",
                "tool",
            ],
            allowed_relationships=[
                "属于",
                "使用",
                "创建",
                "相关",
                "因果",
                "包含",
                "位于",
                "参与",
                "产生",
            ],
        ),
    ]
    for domain in domains:
        _DOMAIN_REGISTRY[domain.name] = domain


_init_domains()


# ── 公开 API ──


def get_allowed_entity_types() -> list[str]:
    """获取所有合法实体类型的扁平列表（去重 + 排序）"""
    types: set[str] = set()
    for domain in _DOMAIN_REGISTRY.values():
        types.update(domain.entity_types)
    return sorted(types)


def get_allowed_relationship_types() -> list[str]:
    """获取所有合法关系类型的扁平列表（去重 + 排序）"""
    rels: set[str] = set()
    for domain in _DOMAIN_REGISTRY.values():
        rels.update(domain.allowed_relationships)
    return sorted(rels)


def get_domain_for_entity_type(entity_type: str) -> str | None:
    """根据实体类型查找所属域名"""
    for domain_name, schema in _DOMAIN_REGISTRY.items():
        if entity_type in schema.entity_types:
            return domain_name
    return None


def get_domain_schema(domain_name: str) -> DomainSchema | None:
    """获取指定域的完整 schema"""
    return _DOMAIN_REGISTRY.get(domain_name)


def list_domains() -> list[dict]:
    """列出所有域的摘要信息"""
    return [
        {
            "name": d.name,
            "display_name": d.display_name,
            "entity_types": d.entity_types,
            "relationship_count": len(d.allowed_relationships),
        }
        for d in _DOMAIN_REGISTRY.values()
    ]


def normalize_entity_type(raw_type: str) -> str:
    """将 LLM 自由输出的类型映射到 Ontology 内的标准类型

    策略：
    1. 精确匹配 → 直接返回
    2. 模糊匹配（编辑距离最近）→ 返回最近匹配
    3. 中文别名表 → 映射到英文标准名
    4. 无法匹配 → fallback 到 "concept"
    """
    if not raw_type:
        return "concept"

    raw_lower = raw_type.lower().strip()
    allowed = get_allowed_entity_types()

    # 1. 精确匹配
    if raw_lower in allowed:
        return raw_lower

    # 2. 中文别名映射
    cn_alias = _CN_ENTITY_ALIASES.get(raw_lower)
    if cn_alias and cn_alias in allowed:
        return cn_alias

    # 3. 模糊匹配（60% 相似度阈值）
    matches = get_close_matches(raw_lower, allowed, n=1, cutoff=0.6)
    if matches:
        mapped = matches[0]
        if mapped != raw_lower:
            logger.debug(
                f"[Ontology] Normalized entity type: '{raw_type}' → '{mapped}'"
            )
        return mapped

    # 4. Fallback
    logger.warning(
        f"[Ontology] Unknown entity type: '{raw_type}', falling back to 'concept'"
    )
    return "concept"


def normalize_relationship(raw_rel: str) -> str:
    """将 LLM 自由输出的关系映射到受控词表

    策略同 normalize_entity_type，但 fallback 到 "关联"
    """
    if not raw_rel:
        return "关联"

    raw_stripped = raw_rel.strip()
    allowed = get_allowed_relationship_types()

    # 精确匹配
    if raw_stripped in allowed:
        return raw_stripped

    # 中文同义词映射
    synonym = _REL_SYNONYMS.get(raw_stripped)
    if synonym and synonym in allowed:
        return synonym

    # 模糊匹配
    matches = get_close_matches(raw_stripped, allowed, n=1, cutoff=0.6)
    if matches:
        mapped = matches[0]
        if mapped != raw_stripped:
            logger.debug(
                f"[Ontology] Normalized relationship: '{raw_rel}' → '{mapped}'"
            )
        return mapped

    logger.debug(
        f"[Ontology] Unknown relationship: '{raw_rel}', falling back to '关联'"
    )
    return "关联"


def validate_triple(
    source_type: str,
    relationship: str,
    target_type: str,
) -> tuple[bool, str]:
    """验证一个三元组是否符合 Ontology 约束

    Returns: (is_valid, reason)
    """
    allowed_types = get_allowed_entity_types()

    if source_type not in allowed_types:
        return False, f"Unknown source type: {source_type}"
    if target_type not in allowed_types:
        return False, f"Unknown target type: {target_type}"

    # 检查关系是否在 source 或 target 所属域的合法关系列表中
    source_domain = get_domain_for_entity_type(source_type)
    target_domain = get_domain_for_entity_type(target_type)

    valid_rels: set[str] = set()
    if source_domain:
        schema = _DOMAIN_REGISTRY.get(source_domain)
        if schema:
            valid_rels.update(schema.allowed_relationships)
    if target_domain:
        schema = _DOMAIN_REGISTRY.get(target_domain)
        if schema:
            valid_rels.update(schema.allowed_relationships)
    # general 域的关系对所有跨域三元组都适用
    general = _DOMAIN_REGISTRY.get("general")
    if general:
        valid_rels.update(general.allowed_relationships)

    if relationship not in valid_rels:
        return False, (
            f"Relationship '{relationship}' not allowed between "
            f"{source_type}({source_domain}) and {target_type}({target_domain})"
        )

    return True, "OK"


def register_domain(domain: DomainSchema) -> None:
    """运行时动态注册新域（用于插件系统或行业定制化）"""
    if domain.name in _DOMAIN_REGISTRY:
        # 合并到已有域
        existing = _DOMAIN_REGISTRY[domain.name]
        for et in domain.entity_types:
            if et not in existing.entity_types:
                existing.entity_types.append(et)
        for rel in domain.allowed_relationships:
            if rel not in existing.allowed_relationships:
                existing.allowed_relationships.append(rel)
        logger.info(
            f"[Ontology] Extended domain '{domain.name}' with new types/relations"
        )
    else:
        _DOMAIN_REGISTRY[domain.name] = domain
        logger.info(f"[Ontology] Registered new domain: '{domain.name}'")


def get_extraction_prompt_hint() -> str:
    """生成用于注入 graph_extraction 系统提示词的 Ontology 约束说明"""
    types = get_allowed_entity_types()
    rels = get_allowed_relationship_types()

    return (
        "## 实体类型约束\n"
        f"只使用以下实体类型: {', '.join(types)}\n"
        "如果实体不属于以上类型，使用 'concept' 作为默认类型。\n\n"
        "## 关系类型约束\n"
        f"只使用以下关系类型: {', '.join(rels)}\n"
        "如果关系不属于以上类型，使用 '关联' 作为默认关系。\n"
    )


# ── 别名表 ──

_CN_ENTITY_ALIASES: dict[str, str] = {
    "客户": "customer",
    "联系人": "contact",
    "商机": "deal",
    "竞争对手": "competitor",
    "线索": "lead",
    "员工": "employee",
    "部门": "department",
    "职位": "position",
    "政策": "policy",
    "团队": "team",
    "审批流": "approval_flow",
    "审批人": "approver",
    "申请": "request",
    "账户": "account",
    "预算": "budget",
    "费用": "expense",
    "发票": "invoice",
    "任务": "task",
    "会议": "meeting",
    "公告": "announcement",
    "文档": "document",
    "排程": "schedule",
    "文章": "article",
    "分类": "category",
    "标签": "tag",
    "人": "person",
    "人物": "person",
    "组织": "organization",
    "公司": "organization",
    "项目": "project",
    "概念": "concept",
    "产品": "product",
    "地点": "location",
    "事件": "event",
    "工具": "tool",
}

_REL_SYNONYMS: dict[str, str] = {
    "负责人": "负责",
    "归属于": "归属",
    "所属": "属于",
    "是…的一部分": "属于",
    "相关于": "相关",
    "导致": "因果",
    "引起": "因果",
    "结果": "因果",
    "被审批": "审批",
    "审核通过": "审批",
    "拒绝": "驳回",
    "否决": "驳回",
    "加入": "参与",
    "参加了": "参加",
    "催促": "催办",
    "联系": "关联",
    "涉及": "关联",
    "采购": "支付",
    "购买": "支付",
}
