"""Finance repositories used by the DDD migration path."""

from app.repositories.base_repository import BaseRepository


class InvoiceRepository(BaseRepository):
    def __init__(self):
        super().__init__("invoices", tenant_column="organization_id")


class PaymentRepository(BaseRepository):
    def __init__(self):
        super().__init__("payments", tenant_column="organization_id")
