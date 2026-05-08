"""CRM repositories used by the DDD migration path."""

from app.repositories.base_repository import BaseRepository


class CustomerRepository(BaseRepository):
    def __init__(self):
        super().__init__("crm_customers", tenant_column="organization_id")


class SalesLeadRepository(BaseRepository):
    def __init__(self):
        super().__init__("sales_leads", tenant_column="organization_id")
