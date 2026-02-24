"""
P4 Enhancement: Pydantic Schemas

Centralized location for all API request/response models.
Ensures strong typing and validation across the application.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# --- Common Models ---


class StandardResponse(BaseModel):
    success: bool
    message: str | None = None
    data: Any | None = None


# --- Sales Performance Models ---


class PerformanceEvent(BaseModel):
    user_id: str = Field(..., description="ID of the user performing the action")
    event_type: Literal["call_finished", "email_sent", "lead_updated", "deal_won"]
    data: dict = Field(..., description="Context data: duration, sentiment_score, deal_value etc")
    timestamp: datetime = Field(default_factory=datetime.now)


class PerformanceResult(BaseModel):
    score_delta: float
    new_daily_score: float
    triggered_incentives: list[str] = []


# --- Approval Models ---


class ApprovalRequest(BaseModel):
    requester_id: str | None = None  # Can be inferred from token
    request_id: str | None = None
    type: Literal["purchase", "travel", "expense", "leave", "event", "activity", "custom"]
    amount: float = Field(..., gt=0, description="Monetary amount involved")
    details: str = Field(..., min_length=5, description="Description of the request")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class ApprovalDecision(BaseModel):
    decision: Literal["auto_approved", "manual_review_required", "auto_rejected"]
    reason: str
    boss_notification_sent: bool
    requires_human_review: bool = False
    suggested_reviewer_role: str | None = None


# --- Incentive Models ---


class IncentiveTrigger(BaseModel):
    user_id: str
    trigger_type: Literal["daily_target_hit", "deal_closed", "rank_top_3", "manual_bonus"]
    context: dict = Field(default_factory=dict)


class IncentiveResponse(BaseModel):
    unique_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # bonus, badge, rank
    amount: float
    reason: str
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.now)


# --- Kingdee Models ---


class KingdeeSyncRequest(BaseModel):
    sync_type: Literal["inventory", "salary", "purchase"]
    period: str | None = None
    force_sync: bool = False


class KingdeeSyncResult(BaseModel):
    sync_id: str
    status: Literal["success", "failed", "partial"]
    records_processed: int
    errors: list[str] = []


# --- Document Models ---


class DocumentMetadata(BaseModel):
    doc_type: Literal["tender", "bid", "contract", "product", "proposal", "invoice", "other"]
    client_name: str | None = None
    amount: float | None = None
    date: str | None = None
    tags: list[str] = []
    redlines: list[str] = []
    technical_deviations: list[str] = []


class BatchDeleteRequest(BaseModel):
    document_ids: list[str]


# --- Project Models ---


class ProjectBase(BaseModel):
    name: str
    description: str | None = None


class ProjectCreate(ProjectBase):
    userId: str  # noqa: N815  # owner_id, maybe inferred from token but kept for compatibility


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    progress: int | None = None


class Project(ProjectBase):
    id: str
    owner_id: str
    status: str
    progress: int
    created_at: datetime
    updated_at: datetime | None = None


# --- Chat Models ---


class Message(BaseModel):
    role: str
    content: str
    id: str | None = None
    timestamp: str | None = None
    agent: str | None = None


class ChatRequest(BaseModel):
    messages: list[Message]
    agent: str | None = None
    userId: str | None = None  # noqa: N815  # Support legacy field
    system_confirmed: bool = False  # P0 Fix #2: Explicit user confirmation from frontend
    sessionId: str | None = "default"  # noqa: N815
    # VMD (Virtual Marketing Department) extensions
    scene_code: str | None = None  # Business scene code (e.g., "bid_document", "content_writing")
    agent_code: str | None = None  # Specific agent role code (e.g., "content_agent")
