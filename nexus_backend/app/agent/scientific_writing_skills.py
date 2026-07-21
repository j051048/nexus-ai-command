"""Versioned writing skills for scientific-instrument deliverables."""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.artifact_contract import ArtifactSpec, ArtifactType


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
        version="2.0.0",
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
        version="2.0.0",
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
        version="1.1.0",
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
        version="1.1.0",
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
        version="1.1.0",
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
    return spec.model_copy(
        update={
            "required_sections": required_sections,
            "retrieval_topics": retrieval_topics,
            "skill_id": skill.skill_id,
            "skill_version": skill.version,
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
    return (
        f"## Deliverable contract ({skill.skill_id}@{skill.version})\n"
        f"Required sections:\n{sections}\n"
        "Every material fact, parameter, policy, competitor claim, and case must cite "
        "an evidence id in the form [EVID:document_id:chunk_id]. "
        "If evidence is absent, write '待核验' and do not infer a value.\n"
        f"Human confirmation is mandatory for: {gates}."
    )
