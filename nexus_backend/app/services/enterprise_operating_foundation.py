"""Odoo/Dolibarr-inspired enterprise operating foundation for Nexus.

This module turns platform lessons from mature ERP/CRM systems into explicit
contracts that Nexus agents, APIs, and UI surfaces can share.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class NexusExecutionContext:
    """Unified context carried by APIs, tools, Agent runs, and reports."""

    user_id: str
    organization_id: str
    role: str = "employee"
    locale: str = "zh-CN"
    currency: str = "CNY"
    default_llm_model: str = "deepseek-v4-flash"
    trace_id: str | None = None
    monthly_llm_budget_usd: float = 20.0
    allowed_apps: list[str] = field(
        default_factory=lambda: [
            "action_inbox",
            "crm",
            "ai_operating_system",
            "approval",
            "knowledge",
        ]
    )
    feature_flags: list[str] = field(default_factory=lambda: ["ai_server_actions"])


BUSINESS_APP_MANIFESTS: list[dict[str, Any]] = [
    {
        "key": "action_inbox",
        "title": "统一行动收件箱",
        "routes": ["/inbox", "/dashboard"],
        "apis": ["/api/inbox", "/api/action-events"],
        "tables": ["action_events", "notifications", "approvals"],
        "agent_tools": ["summarize_actions", "prioritize_next_best_action"],
        "demo_pack": "first_week_action_pack",
        "quality_gates": ["route_smoke", "rls_policy", "action_event_audit"],
    },
    {
        "key": "crm",
        "title": "科学仪器 CRM",
        "routes": ["/crm", "/sales"],
        "apis": ["/api/crm", "/api/sales-leads"],
        "tables": ["customers", "contacts", "sales_leads", "action_events"],
        "agent_tools": ["score_customer_health", "draft_followup", "create_visit_note"],
        "demo_pack": "scientific_instrument_crm_demo",
        "quality_gates": ["tenant_isolation", "customer_360_contract", "crm_e2e"],
    },
    {
        "key": "ai_operating_system",
        "title": "助手工作台",
        "routes": ["/ai-operating-system", "/agent-improvement-center"],
        "apis": ["/api/ai-operating-system"],
        "tables": ["agent_runs", "agent_ci_runs", "agent_improvement_proposals"],
        "agent_tools": ["run_agent_simulation", "define_agent_from_sop"],
        "demo_pack": "agent_ops_demo",
        "quality_gates": ["release_quality_gate", "production_proof_gate"],
    },
    {
        "key": "approval",
        "title": "审批与风控",
        "routes": ["/approvals", "/approval-flows"],
        "apis": ["/api/approvals", "/api/approval-flows"],
        "tables": ["approvals", "approval_flows", "action_events"],
        "agent_tools": ["approval_risk_review", "route_reviewer", "explain_policy"],
        "demo_pack": "approval_risk_demo",
        "quality_gates": ["hitl_required", "audit_log_immutable", "approval_e2e"],
    },
    {
        "key": "document_template_center",
        "title": "文档模板中心",
        "routes": ["/documents", "/reports"],
        "apis": ["/api/documents", "/api/reports"],
        "tables": ["documents", "reports", "knowledge_chunks"],
        "agent_tools": [
            "fill_template",
            "generate_customer_360",
            "export_audit_packet",
        ],
        "demo_pack": "document_template_demo",
        "quality_gates": ["template_render_contract", "export_security_scan"],
    },
]


AI_SERVER_ACTIONS: list[dict[str, Any]] = [
    {
        "key": "crm.batch_followup_plan",
        "label": "批量生成客户跟进计划",
        "object": "customer",
        "risk_level": "low",
        "requires_hitl": False,
        "max_batch_size": 50,
        "tools": ["score_customer_health", "draft_followup", "create_task"],
        "audit_event": "ai_server_action.crm_followup_plan",
    },
    {
        "key": "crm.batch_risk_score",
        "label": "批量客户流失风险评分",
        "object": "customer",
        "risk_level": "medium",
        "requires_hitl": False,
        "max_batch_size": 100,
        "tools": ["score_customer_health", "build_evidence_pack"],
        "audit_event": "ai_server_action.crm_risk_score",
    },
    {
        "key": "approval.bulk_risk_review",
        "label": "批量审批风控复核",
        "object": "approval",
        "risk_level": "high",
        "requires_hitl": True,
        "max_batch_size": 20,
        "tools": ["approval_risk_review", "explain_policy"],
        "audit_event": "ai_server_action.approval_bulk_risk_review",
    },
    {
        "key": "tender.generate_response_pack",
        "label": "生成投标响应资料包",
        "object": "tender",
        "risk_level": "high",
        "requires_hitl": True,
        "max_batch_size": 5,
        "tools": ["score_tender_response", "generate_matrix", "fill_template"],
        "audit_event": "ai_server_action.tender_response_pack",
    },
]


FIELD_PROMPT_POLICIES: list[dict[str, Any]] = [
    {
        "model": "customers",
        "field": "name",
        "classification": "business_context",
        "prompt_visibility": "visible",
        "masking": "none",
    },
    {
        "model": "customers",
        "field": "phone",
        "classification": "personal_data",
        "prompt_visibility": "masked",
        "masking": "last4",
    },
    {
        "model": "contracts",
        "field": "amount",
        "classification": "commercial_sensitive",
        "prompt_visibility": "summary_only",
        "masking": "range_bucket",
    },
    {
        "model": "payments",
        "field": "bank_account",
        "classification": "financial_secret",
        "prompt_visibility": "blocked",
        "masking": "never_send_to_llm",
    },
    {
        "model": "api_keys",
        "field": "secret",
        "classification": "credential",
        "prompt_visibility": "blocked",
        "masking": "never_send_to_llm",
    },
]


DOCUMENT_TEMPLATE_CENTER: list[dict[str, Any]] = [
    {
        "key": "customer_360_pdf",
        "title": "客户 360 PDF",
        "source_objects": [
            "customer",
            "contact",
            "project",
            "contract",
            "action_event",
        ],
        "output_formats": ["pdf", "docx"],
        "requires_human_review": False,
    },
    {
        "key": "tender_scoring_matrix",
        "title": "投标评分矩阵",
        "source_objects": ["tender", "document", "competitor", "knowledge_chunk"],
        "output_formats": ["xlsx", "pdf"],
        "requires_human_review": True,
    },
    {
        "key": "visit_note",
        "title": "客户拜访纪要",
        "source_objects": ["customer", "contact", "voice_memo", "action_event"],
        "output_formats": ["docx", "markdown"],
        "requires_human_review": False,
    },
    {
        "key": "approval_audit_packet",
        "title": "审批审计单",
        "source_objects": ["approval", "approval_flow", "action_event", "audit_log"],
        "output_formats": ["pdf", "json"],
        "requires_human_review": True,
    },
    {
        "key": "ai_value_weekly_report",
        "title": "AI 行为与价值周报",
        "source_objects": ["agent_run", "action_event", "cost_event", "trust_report"],
        "output_formats": ["pdf", "html"],
        "requires_human_review": False,
    },
]


def build_nexus_execution_context(
    *,
    user_id: str,
    organization_id: str,
    role: str = "employee",
    trace_id: str | None = None,
    allowed_apps: list[str] | None = None,
) -> NexusExecutionContext:
    return NexusExecutionContext(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
        trace_id=trace_id,
        allowed_apps=allowed_apps
        or [
            manifest["key"]
            for manifest in BUSINESS_APP_MANIFESTS
            if manifest["key"] != "document_template_center"
        ],
    )


def get_enterprise_operating_foundation(
    *,
    user_id: str,
    organization_id: str,
    role: str = "employee",
    trace_id: str | None = None,
) -> dict[str, Any]:
    context = build_nexus_execution_context(
        user_id=user_id,
        organization_id=organization_id,
        role=role,
        trace_id=trace_id,
    )
    return {
        "source": "odoo/dolibarr inspired enterprise operating foundation",
        "execution_context": asdict(context),
        "business_app_manifests": BUSINESS_APP_MANIFESTS,
        "ai_server_actions": AI_SERVER_ACTIONS,
        "field_prompt_policies": FIELD_PROMPT_POLICIES,
        "document_template_center": DOCUMENT_TEMPLATE_CENTER,
        "summary": {
            "default_llm_model": context.default_llm_model,
            "business_app_count": len(BUSINESS_APP_MANIFESTS),
            "server_action_count": len(AI_SERVER_ACTIONS),
            "prompt_policy_count": len(FIELD_PROMPT_POLICIES),
            "document_template_count": len(DOCUMENT_TEMPLATE_CENTER),
        },
    }


def validate_enterprise_operating_foundation() -> dict[str, Any]:
    high_risk_without_hitl = [
        action["key"]
        for action in AI_SERVER_ACTIONS
        if action["risk_level"] == "high" and not action["requires_hitl"]
    ]
    prompt_policy_leaks = [
        policy["model"] + "." + policy["field"]
        for policy in FIELD_PROMPT_POLICIES
        if policy["classification"] in {"credential", "financial_secret"}
        and policy["prompt_visibility"] != "blocked"
    ]
    incomplete_manifests = [
        manifest["key"]
        for manifest in BUSINESS_APP_MANIFESTS
        if not manifest.get("routes")
        or not manifest.get("apis")
        or not manifest.get("tables")
        or not manifest.get("quality_gates")
    ]
    incomplete_templates = [
        template["key"]
        for template in DOCUMENT_TEMPLATE_CENTER
        if not template.get("source_objects") or not template.get("output_formats")
    ]

    context = build_nexus_execution_context(
        user_id="contract-test-user",
        organization_id="contract-test-org",
    )
    checks = {
        "nexus_execution_context": context.default_llm_model == "deepseek-v4-flash",
        "business_app_manifest": not incomplete_manifests,
        "ai_server_actions": not high_risk_without_hitl,
        "field_prompt_permissions": not prompt_policy_leaks,
        "document_template_center": not incomplete_templates,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "high_risk_without_hitl": high_risk_without_hitl,
        "prompt_policy_leaks": prompt_policy_leaks,
        "incomplete_manifests": incomplete_manifests,
        "incomplete_templates": incomplete_templates,
    }
