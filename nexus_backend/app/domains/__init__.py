"""Domain entrypoints for gradual DDD migration."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainDescriptor:
    code: str
    routers: tuple[str, ...]
    services: tuple[str, ...]
    repositories: tuple[str, ...]


DOMAIN_REGISTRY: dict[str, DomainDescriptor] = {
    "crm": DomainDescriptor(
        code="crm",
        routers=("crm", "sales", "sales_leads", "competitors"),
        services=("crm_service", "lead_scoring_service"),
        repositories=("CustomerRepository", "SalesLeadRepository"),
    ),
    "approval": DomainDescriptor(
        code="approval",
        routers=("approval", "approval_flows", "workflows", "workflow_templates"),
        services=("approval_chain", "workflow_definition_service"),
        repositories=("ApprovalRequestRepository", "WorkflowRepository"),
    ),
    "finance": DomainDescriptor(
        code="finance",
        routers=("finance", "billing", "payments", "usage"),
        services=("billing_service", "tenant_credit_service"),
        repositories=("InvoiceRepository", "PaymentRepository"),
    ),
}
