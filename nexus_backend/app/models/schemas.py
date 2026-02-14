"""
P4 Enhancement: Pydantic Schemas

Centralized location for all API request/response models.
Ensures strong typing and validation across the application.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Literal, List, Any
from datetime import datetime
import uuid

# --- Common Models ---


class StandardResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None


# --- Sales Performance Models ---


class PerformanceEvent(BaseModel):
    user_id: str = Field(..., description="ID of the user performing the action")
    event_type: Literal["call_finished", "email_sent", "lead_updated", "deal_won"]
    data: Dict = Field(
        ..., description="Context data: duration, sentiment_score, deal_value etc"
    )
    timestamp: datetime = Field(default_factory=datetime.now)


class PerformanceResult(BaseModel):
    score_delta: float
    new_daily_score: float
    triggered_incentives: List[str] = []


# --- Approval Models ---


class ApprovalRequest(BaseModel):
    requester_id: Optional[str] = None  # Can be inferred from token
    request_id: Optional[str] = None
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
    suggested_reviewer_role: Optional[str] = None


# --- Incentive Models ---


class IncentiveTrigger(BaseModel):
    user_id: str
    trigger_type: Literal[
        "daily_target_hit", "deal_closed", "rank_top_3", "manual_bonus"
    ]
    context: Dict = Field(default_factory=dict)


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
    period: Optional[str] = None
    force_sync: bool = False


class KingdeeSyncResult(BaseModel):
    sync_id: str
    status: Literal["success", "failed", "partial"]
    records_processed: int
    errors: List[str] = []


# --- Document Models ---


class DocumentMetadata(BaseModel):
    doc_type: Literal["bid", "contract", "other"]
    client_name: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[str] = None
    tags: List[str] = []
    redlines: List[str] = []
    technical_deviations: List[str] = []


class BatchDeleteRequest(BaseModel):
    document_ids: List[str]


# --- Project Models ---


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    userId: str  # owner_id, maybe inferred from token but kept for compatibility


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None


class Project(ProjectBase):
    id: str
    owner_id: str
    status: str
    progress: int
    created_at: datetime
    updated_at: Optional[datetime] = None


# --- Chat Models ---


class Message(BaseModel):
    role: str
    content: str
    id: Optional[str] = None
    timestamp: Optional[str] = None
    agent: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[Message]
    agent: Optional[str] = None
    userId: Optional[str] = None  # Support legacy field
    system_confirmed: bool = (
        False  # P0 Fix #2: Explicit user confirmation from frontend
    )
    sessionId: Optional[str] = "default"
