"""Versioned writing skills for scientific-instrument deliverables."""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.artifact_contract import (
    ArtifactSpec,
    ArtifactType,
    default_content_budget,
)
from app.services.scientific_instrument_domain_packs import (
    build_domain_pack_prompt,
    get_domain_pack,
)


@dataclass(frozen=True)
class WritingSkill:
    skill_id: str
    version: str
    artifact_type: ArtifactType
    required_sections: tuple[str, ...]
    retrieval_topics: tuple[str, ...]
    validators: tuple[str, ...]
    human_gates: tuple[str, ...]


SCIENTIFIC_WRITING_SKILLS: dict[ArtifactType, WritingSkill] = {
    ArtifactType.CUSTOMER_SOLUTION: WritingSkill(
        skill_id="scientific.customer_solution",
        version="3.0.0",
        artifact_type=ArtifactType.CUSTOMER_SOLUTION,
        required_sections=(
            "项目背景与客户目标",
            "需求与验收矩阵",
            "适用政策与标准",
            "推荐配置与选型依据",
            "关键参数与技术优势",
            "竞品横向对比",
            "应用案例与证据",
            "实施交付与培训",
            "售后服务与风险边界",
        ),
        retrieval_topics=(
            "客户行业场景与样品",
            "产品型号参数和检测能力",
            "适用标准政策",
            "竞品参数",
            "授权客户案例",
            "安装培训维保条款",
        ),
        validators=(
            "evidence_coverage",
            "parameter_integrity",
            "policy_currency",
            "competitor_fairness",
            "case_authorization",
            "service_commitment_safety",
        ),
        human_gates=("价格", "交期", "性能保证", "客户案例授权", "外发"),
    ),
    ArtifactType.TENDER: WritingSkill(
        skill_id="scientific.tender_response",
        version="3.0.0",
        artifact_type=ArtifactType.TENDER,
        required_sections=(
            "招标要求摘要",
            "逐条响应矩阵",
            "技术方案",
            "技术偏离表",
            "商务响应",
            "实施与验收",
            "售后服务",
            "资格与证据清单",
            "风险与人工复核项",
        ),
        retrieval_topics=(
            "招标强制条款和评分项",
            "产品参数和检测能力",
            "资质证书",
            "案例证明",
            "交付验收售后条款",
        ),
        validators=(
            "requirement_traceability",
            "evidence_coverage",
            "parameter_integrity",
            "commercial_safety",
        ),
        human_gates=("投标承诺", "报价", "交期", "偏离项", "提交"),
    ),
    ArtifactType.COMPETITOR_ANALYSIS: WritingSkill(
        skill_id="scientific.competitor_analysis",
        version="2.0.0",
        artifact_type=ArtifactType.COMPETITOR_ANALYSIS,
        required_sections=(
            "分析范围",
            "同口径参数矩阵",
            "应用场景差异",
            "我方优势与边界",
            "证据与数据日期",
            "销售行动建议",
        ),
        retrieval_topics=("我方产品参数", "竞品公开参数", "应用差异", "证据版本和日期"),
        validators=("evidence_coverage", "competitor_fairness", "parameter_integrity"),
        human_gates=("竞品事实", "对外发布"),
    ),
    ArtifactType.POLICY_BRIEF: WritingSkill(
        skill_id="scientific.policy_brief",
        version="2.0.0",
        artifact_type=ArtifactType.POLICY_BRIEF,
        required_sections=(
            "政策背景",
            "适用范围",
            "关键条款",
            "业务影响",
            "行动清单",
            "来源与生效日期",
        ),
        retrieval_topics=("现行政策原文", "适用范围", "生效失效日期", "监管解释"),
        validators=("evidence_coverage", "policy_currency", "scope_safety"),
        human_gates=("法律结论", "监管提交", "公开发布"),
    ),
    ArtifactType.SERVICE_PROPOSAL: WritingSkill(
        skill_id="scientific.service_proposal",
        version="2.0.0",
        artifact_type=ArtifactType.SERVICE_PROPOSAL,
        required_sections=(
            "设备与服务范围",
            "现场条件",
            "维护校准计划",
            "响应级别",
            "备件与耗材",
            "验收记录",
            "责任边界",
        ),
        retrieval_topics=(
            "设备型号和序列",
            "维护校准规范",
            "SLA条款",
            "备件耗材",
            "现场服务记录",
        ),
        validators=(
            "asset_traceability",
            "service_commitment_safety",
            "evidence_coverage",
        ),
        human_gates=("SLA承诺", "费用", "停机窗口", "外发"),
    ),
    ArtifactType.TECHNICAL_REPORT: WritingSkill(
        skill_id="scientific.technical_report",
        version="1.0.0",
        artifact_type=ArtifactType.TECHNICAL_REPORT,
        required_sections=(
            "报告目的与范围",
            "样品、仪器与方法",
            "技术依据与数据质量",
            "结果与分析",
            "异常、限制与不确定性",
            "结论与建议",
            "证据与复核清单",
        ),
        retrieval_topics=(
            "实验目标与样品信息",
            "仪器型号参数与方法",
            "原始数据与质量控制",
            "适用标准规范",
            "异常记录与复核要求",
        ),
        validators=(
            "evidence_coverage",
            "parameter_integrity",
            "method_traceability",
            "result_uncertainty",
        ),
        human_gates=("实验结论", "异常处置", "监管或客户外发"),
    ),
}

_AUTHORING_RULES: dict[ArtifactType, tuple[str, ...]] = {
    ArtifactType.CUSTOMER_SOLUTION: (
        "需求与验收矩阵必须用表格呈现客户需求、响应方案、证据和验收方式",
        "推荐配置必须区分核心配置、可选配置与适用边界，不能只罗列型号",
        "关键参数、竞品横向对比和实施计划优先使用同口径表格",
        "应用案例只能引用已授权企业案例；没有证据时保留待核验位，不得编造",
        "结论必须落到客户价值、实施动作和下一步确认事项",
    ),
    ArtifactType.TENDER: (
        "逐条响应矩阵、技术偏离表、资格证据清单和实施验收计划必须表格化",
        "每个强制条款必须能回溯到招标原文和我方证据",
        "不得将待核验内容写成无偏离或完全满足",
    ),
    ArtifactType.COMPETITOR_ANALYSIS: (
        "同口径参数矩阵必须区分已核验事实、公开资料与待核验项",
        "优势必须同时说明适用场景和边界，禁止贬损性或绝对化表达",
    ),
    ArtifactType.POLICY_BRIEF: (
        "关键条款应给出来源、版本、生效日期和业务动作",
        "政策原文、解释性判断和企业建议必须明确区分",
    ),
    ArtifactType.SERVICE_PROPOSAL: (
        "维护校准计划、响应级别和备件耗材应采用可执行表格",
        "所有 SLA、费用与停机窗口必须标记确认责任人和确认状态",
    ),
    ArtifactType.TECHNICAL_REPORT: (
        "仪器、方法、样品、结果和异常必须能够回溯到企业记录",
        "结果表格必须区分实测值、判定依据、结论和复核状态",
        "不得把推断写成实验事实，限制与不确定性必须单独披露",
    ),
}


def resolve_writing_skill(spec: ArtifactSpec | dict) -> WritingSkill | None:
    if not isinstance(spec, ArtifactSpec):
        spec = ArtifactSpec.model_validate(spec)
    return SCIENTIFIC_WRITING_SKILLS.get(spec.artifact_type)


def enrich_artifact_spec(spec: ArtifactSpec | dict) -> ArtifactSpec:
    if not isinstance(spec, ArtifactSpec):
        spec = ArtifactSpec.model_validate(spec)
    skill = resolve_writing_skill(spec)
    if not skill:
        return spec
    required_sections = list(
        dict.fromkeys([*spec.required_sections, *skill.required_sections])
    )
    retrieval_topics = list(
        dict.fromkeys([*spec.retrieval_topics, *skill.retrieval_topics])
    )
    domain_pack = get_domain_pack(spec.instrument_line)
    if domain_pack:
        retrieval_topics = list(
            dict.fromkeys(
                [
                    *retrieval_topics,
                    *domain_pack["decision_dimensions"],
                    *domain_pack["acceptance_checks"],
                    *domain_pack["standards_focus"],
                ]
            )
        )
    target, minimum, minimum_tables = default_content_budget(spec.artifact_type)
    content_contract: dict[str, int] = {}
    if "target_character_count" not in spec.model_fields_set:
        content_contract["target_character_count"] = target
    if "minimum_character_count" not in spec.model_fields_set:
        content_contract["minimum_character_count"] = minimum
    if "minimum_table_count" not in spec.model_fields_set:
        content_contract["minimum_table_count"] = minimum_tables
    return spec.model_copy(
        update={
            "required_sections": required_sections,
            "retrieval_topics": retrieval_topics,
            "skill_id": skill.skill_id,
            "skill_version": skill.version,
            **content_contract,
        }
    )


def build_writing_skill_prompt(spec: ArtifactSpec | dict) -> str:
    spec = enrich_artifact_spec(spec)
    skill = resolve_writing_skill(spec)
    if not skill:
        return ""
    sections = "\n".join(
        f"{index}. {title}" for index, title in enumerate(skill.required_sections, 1)
    )
    gates = "、".join(skill.human_gates)
    section_minimum = max(
        120,
        int(spec.minimum_character_count / max(1, len(skill.required_sections)) * 0.48),
    )
    authoring_rules = "\n".join(
        f"- {item}" for item in _AUTHORING_RULES.get(spec.artifact_type, ())
    )
    return (
        f"## Deliverable contract ({skill.skill_id}@{skill.version})\n"
        f"Required sections:\n{sections}\n"
        f"Target length: {spec.target_character_count} Chinese characters; "
        f"hard minimum: {spec.minimum_character_count}.\n"
        f"Each required section should normally contain at least {section_minimum} "
        "Chinese characters of substantive prose, unless a dense evidence table carries the detail.\n"
        f"Use at least {spec.minimum_table_count} meaningful Markdown tables; "
        "tables must compare repeated fields rather than package ordinary prose.\n"
        "Every material fact, parameter, policy, competitor claim, and case must cite "
        "an evidence id in the form [EVID:document_id:chunk_id]. "
        "If evidence is absent, write '待核验' and do not infer a value.\n"
        "Do not return an outline with empty headings. Every heading must contain analysis, "
        "evidence, a conclusion, and when relevant a next action.\n"
        f"{authoring_rules}\n"
        f"Human confirmation is mandatory for: {gates}."
        f"{build_domain_pack_prompt(spec.instrument_line)}"
    )
