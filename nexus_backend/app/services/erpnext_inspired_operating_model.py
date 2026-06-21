"""ERPNext-inspired operating model for Nexus enterprise workflows.

The goal is not to copy ERPNext modules. We keep the lessons that matter for
Nexus: metadata-driven business objects, workflow state, immutable ledgers,
portals, hooks, reports, onboarding data, and migration governance.
"""

from __future__ import annotations

from typing import Any

ERP_NEXT_INSPIRED_CAPABILITIES: list[dict[str, str]] = [
    {
        "key": "business_object_meta",
        "title": "DocType 元数据业务对象",
        "learned_from": "ERPNext 用 DocType 把字段、权限、状态、表单和列表视图收敛成同一个业务对象模型。",
        "nexus_application": "把客户、项目、合同、审批、库存、投标统一抽象为可描述、可验证、可生成页面和工具的 Business Object。",
        "acceptance_signal": "新增核心对象时必须声明字段、租户字段、审计字段、权限矩阵、默认视图和 Agent 可调用动作。",
    },
    {
        "key": "unified_workflow_state_machine",
        "title": "统一 Workflow/HITL 状态机",
        "learned_from": "ERPNext 的审批、采购、销售、库存都围绕文档状态和 Workflow Action 运转。",
        "nexus_application": "把审批、合同、线索、投标和 Agent HITL 统一到 draft -> submitted -> reviewed -> approved/rejected -> archived。",
        "acceptance_signal": "每个高价值动作都能回答当前状态、下一步动作、谁可操作、是否需要人工确认。",
    },
    {
        "key": "immutable_business_ledger",
        "title": "不可变业务账本",
        "learned_from": "ERPNext 的总账、库存账和交易流水强调追加式记录，而不是覆盖式状态。",
        "nexus_application": "为 Agent 行动、审批、客户跟进、合同金额、库存变更建立 append-only ledger，支撑审计和价值证明。",
        "acceptance_signal": "关键业务变化必须生成 ledger event，并能从事件回放出当前状态。",
    },
    {
        "key": "customer_supplier_portal",
        "title": "客户/供应商自助门户",
        "learned_from": "ERPNext 内置客户、供应商和员工门户，让外部协作不必进入后台系统。",
        "nexus_application": "把客户报价确认、资料补充、投标澄清、合同查看做成受控门户链接，由 Agent 生成并追踪。",
        "acceptance_signal": "外部用户只看到授权对象，所有门户动作回写到客户、项目和 Agent 证据链。",
    },
    {
        "key": "event_hook_registry",
        "title": "事件钩子与调度注册表",
        "learned_from": "ERPNext/Frappe 用 hooks.py 把文档事件、调度任务和扩展点显式注册。",
        "nexus_application": "把 30 天未跟进、合同到期、审批超时、预算异常等触发器集中登记，替代散落 cron 和临时代码。",
        "acceptance_signal": "每个自动任务都有事件源、触发条件、幂等键、失败重试、限额和负责人。",
    },
    {
        "key": "report_print_export_templates",
        "title": "报表/打印/导出模板",
        "learned_from": "ERPNext 的每个业务模块都配套列表、报表、打印格式和导出。",
        "nexus_application": "把销售周报、投标评分矩阵、客户 360、审批审计单和合同摘要模板化，并允许 Agent 填充。",
        "acceptance_signal": "每个核心对象至少有一个运营报表、一个客户可分享格式和一个审计导出格式。",
    },
    {
        "key": "module_onboarding_demo_data",
        "title": "模块 Onboarding 与 Demo Data",
        "learned_from": "ERPNext 用模块化设置向导和样例数据降低 ERP 首次使用成本。",
        "nexus_application": "为 VMD、CRM、审批、投标、知识库提供首周任务、样例客户、样例合同和可删除 Demo 工作区。",
        "acceptance_signal": "新组织 7 天内能跑通一条线索到跟进、审批、投标分析或周报生成的闭环。",
    },
    {
        "key": "migration_patch_governance",
        "title": "迁移补丁治理",
        "learned_from": "ERPNext 的 patch/migration 体系把长期演进中的数据修复显式化。",
        "nexus_application": "把 Supabase migration、RLS、schema convergence、回填脚本、幂等补丁统一登记和 CI 回放。",
        "acceptance_signal": "每次上线前必须验证空库迁移、重复执行安全、租户列收敛和回滚说明。",
    },
]

BUSINESS_OBJECT_BLUEPRINTS: list[dict[str, Any]] = [
    {
        "object": "customer",
        "tenant_field": "organization_id",
        "agent_actions": ["score_health", "draft_followup", "create_visit_note"],
    },
    {
        "object": "project",
        "tenant_field": "organization_id",
        "agent_actions": ["summarize_status", "detect_risk", "create_next_task"],
    },
    {
        "object": "contract",
        "tenant_field": "organization_id",
        "agent_actions": ["review_terms", "flag_payment_risk", "generate_summary"],
    },
    {
        "object": "approval",
        "tenant_field": "organization_id",
        "agent_actions": ["explain_policy", "risk_review", "route_reviewer"],
    },
    {
        "object": "inventory_item",
        "tenant_field": "organization_id",
        "agent_actions": ["forecast_shortage", "explain_movement", "prepare_reorder"],
    },
    {
        "object": "tender",
        "tenant_field": "organization_id",
        "agent_actions": ["score_bid", "compare_competitor", "draft_response"],
    },
]

UNIFIED_WORKFLOW_BLUEPRINTS = [
    "draft -> submitted -> reviewed -> approved -> executed -> archived",
    "draft -> submitted -> rejected -> revised -> submitted",
    "agent_suggested -> human_review -> gray_release -> auto_execute -> audited",
]

IMMUTABLE_LEDGER_STREAMS = [
    "agent_action_ledger",
    "customer_followup_ledger",
    "approval_decision_ledger",
    "contract_value_ledger",
    "inventory_movement_ledger",
]

PORTAL_EXPERIENCE_BLUEPRINTS = [
    "客户报价确认门户",
    "投标澄清资料门户",
    "供应商资料补充门户",
    "合同与交付状态门户",
]

EVENT_HOOK_BLUEPRINTS = [
    "customer.no_followup_30d -> create_followup_agent_run",
    "contract.expires_in_60d -> create_renewal_playbook",
    "approval.over_sla -> notify_reviewer_and_manager",
    "tender.new_document_uploaded -> run_bid_scoring_agent",
    "inventory.low_stock -> prepare_reorder_recommendation",
]

REPORT_PRINT_BLUEPRINTS = [
    "客户 360 PDF",
    "销售周报",
    "投标评分矩阵",
    "审批审计单",
    "Agent 行为与价值周报",
]

ONBOARDING_DEMO_PACKS = [
    "VMD 科学仪器销售样例空间",
    "CRM 线索到合同样例空间",
    "审批与费用风控样例空间",
    "投标分析样例空间",
]

MIGRATION_GOVERNANCE_RULES = [
    "每个迁移必须可空库回放",
    "每个租户表必须声明 organization_id 或明确豁免",
    "每个新增表必须声明 RLS 与审计策略",
    "每个数据补丁必须幂等并记录执行状态",
]


def get_erpnext_inspired_operating_model() -> dict[str, Any]:
    return {
        "source": "frappe/erpnext inspired enterprise operating model",
        "capabilities": ERP_NEXT_INSPIRED_CAPABILITIES,
        "business_objects": BUSINESS_OBJECT_BLUEPRINTS,
        "workflow_blueprints": UNIFIED_WORKFLOW_BLUEPRINTS,
        "ledger_streams": IMMUTABLE_LEDGER_STREAMS,
        "portal_experiences": PORTAL_EXPERIENCE_BLUEPRINTS,
        "event_hooks": EVENT_HOOK_BLUEPRINTS,
        "report_print_templates": REPORT_PRINT_BLUEPRINTS,
        "onboarding_demo_packs": ONBOARDING_DEMO_PACKS,
        "migration_governance_rules": MIGRATION_GOVERNANCE_RULES,
        "summary": {
            "capability_count": len(ERP_NEXT_INSPIRED_CAPABILITIES),
            "business_object_count": len(BUSINESS_OBJECT_BLUEPRINTS),
            "event_hook_count": len(EVENT_HOOK_BLUEPRINTS),
            "report_template_count": len(REPORT_PRINT_BLUEPRINTS),
        },
    }


def validate_erpnext_inspired_operating_model() -> dict[str, Any]:
    expected_keys = {
        "business_object_meta",
        "unified_workflow_state_machine",
        "immutable_business_ledger",
        "customer_supplier_portal",
        "event_hook_registry",
        "report_print_export_templates",
        "module_onboarding_demo_data",
        "migration_patch_governance",
    }
    actual_keys = {item["key"] for item in ERP_NEXT_INSPIRED_CAPABILITIES}
    missing = sorted(expected_keys - actual_keys)
    incomplete = [
        item["key"]
        for item in ERP_NEXT_INSPIRED_CAPABILITIES
        if not item.get("nexus_application") or not item.get("acceptance_signal")
    ]
    return {
        "passed": not missing and not incomplete,
        "missing_capabilities": missing,
        "incomplete_capabilities": incomplete,
        "capability_count": len(ERP_NEXT_INSPIRED_CAPABILITIES),
    }
