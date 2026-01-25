from pydantic import BaseModel, Field
from typing import Optional, Dict, Literal, List
from datetime import datetime
import uuid

# --- Sales Performance Models ---

class PerformanceEvent(BaseModel):
    user_id: str
    event_type: Literal['call_finished', 'email_sent', 'lead_updated', 'deal_won']
    data: Dict = Field(..., description="Context data: duration, sentiment_score, deal_value etc")

class PerformanceResult(BaseModel):
    score_delta: float
    new_daily_score: float
    triggered_incentives: List[str] = []

# --- Approval Models ---

class ApprovalRequest(BaseModel):
    requester_id: str
    type: Literal['purchase', 'travel', 'event', 'expense']
    amount: float
    details: str

class ApprovalDecision(BaseModel):
    decision: Literal['auto_approved', 'manual_review_required', 'auto_rejected']
    reason: str
    boss_notification_sent: bool

# --- Kingdee Mock Models ---

class KingdeeSyncRequest(BaseModel):
    sync_type: Literal['inventory', 'salary', 'purchase']
    period: Optional[str] = None
