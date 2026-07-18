"""Domain entrypoints for gradual DDD migration."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainDescriptor:
    code: str
    routers: tuple[str, ...]
    services: tuple[str, ...]
    repositories: tuple[str, ...]
    owner: str = "unassigned"
    maturity: str = "emerging"


DOMAIN_REGISTRY: dict[str, DomainDescriptor] = {
    "crm": DomainDescriptor(
        code="crm",
        routers=("crm", "sales", "sales_leads"),
        services=("crm_service", "lead_scoring_service"),
        repositories=("CustomerRepository", "SalesLeadRepository"),
        owner="growth",
        maturity="core",
    ),
    "approval": DomainDescriptor(
        code="approval",
        routers=("approval", "approval_flows", "workflows", "workflow_templates"),
        services=("approval_chain", "workflow_definition_service"),
        repositories=("ApprovalRequestRepository", "WorkflowRepository"),
        owner="enterprise-core",
        maturity="core",
    ),
    "finance": DomainDescriptor(
        code="finance",
        routers=("finance", "billing", "payments", "usage"),
        services=("billing_service", "tenant_credit_service"),
        repositories=("InvoiceRepository", "PaymentRepository"),
        owner="enterprise-core",
        maturity="supported",
    ),
    "growth_vmd": DomainDescriptor(
        code="growth_vmd",
        routers=("vmd_clues", "vmd_dashboard", "vmd_tasks", "competitors"),
        services=("clue_service", "bidding_service", "competitor_service"),
        repositories=(),
        owner="growth",
        maturity="core",
    ),
    "agent_platform": DomainDescriptor(
        code="agent_platform",
        routers=("agent_observability", "agent_replay", "ai_assistant", "memories"),
        services=("agent_trace_service", "agent_replay_service", "llm_gateway"),
        repositories=(),
        owner="agent-platform",
        maturity="core",
    ),
    "enterprise_core": DomainDescriptor(
        code="enterprise_core",
        routers=("organization", "projects", "contracts", "notifications"),
        services=("organization_service", "contract_service", "notification_service"),
        repositories=(),
        owner="enterprise-core",
        maturity="supported",
    ),
    "operations": DomainDescriptor(
        code="operations",
        routers=("inventory", "assets", "work_orders"),
        services=("inventory_service", "asset_service", "work_order_service"),
        repositories=(),
        owner="enterprise-core",
        maturity="supported",
    ),
    "integrations": DomainDescriptor(
        code="integrations",
        routers=("im_callbacks", "im_oauth", "im_settings", "kingdee", "webhooks"),
        services=("oauth_service", "webhook_service", "wecom_service"),
        repositories=(),
        owner="integrations",
        maturity="optional",
    ),
    "admin_trust": DomainDescriptor(
        code="admin_trust",
        routers=("super_admin", "deployment_health", "metrics"),
        services=("super_admin_service", "agent_slo_cost_service", "audit_logger"),
        repositories=(),
        owner="platform",
        maturity="core",
    ),
}
