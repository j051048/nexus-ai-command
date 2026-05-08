"""Approval/workflow repositories used by the DDD migration path."""

from app.repositories.base_repository import BaseRepository


class ApprovalRequestRepository(BaseRepository):
    def __init__(self):
        super().__init__("approval_requests", tenant_column="organization_id")


class WorkflowRepository(BaseRepository):
    def __init__(self):
        super().__init__("workflows", tenant_column="organization_id")
