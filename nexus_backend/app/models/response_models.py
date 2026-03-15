"""
Pydantic Response Models for Critical API Endpoints

Provides typed, validated response models to prevent frontend breakage
from unexpected data shapes (e.g., nested objects where flat values expected).
"""

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# VMD Task Response Models
# ---------------------------------------------------------------------------


class VMDSubTaskResponse(BaseModel):
    """Sub-task within a VMD task."""

    id: int | str
    agent_role: str = ""
    title: str = ""
    description: str = ""
    status: str = "todo"
    progress: int = 0
    human_notes: str | None = None
    output: str | None = None
    sort_order: int = 0
    assignee_id: str | None = None
    assignee_name: str | None = None
    weight: int = 1
    start_date: str | None = None
    due_date: str | None = None
    review_status: str | None = None


class VMDTaskSummary(BaseModel):
    """Summary view of a VMD task (used in list endpoints)."""

    id: str
    task_code: str = ""
    title: str = ""
    status: str = "pending"
    priority: str = "medium"
    progress: float = 0.0  # Always a number (percentage), never an object
    scene_code: str = ""
    created_at: str = ""

    model_config = ConfigDict(extra="ignore")


class VMDTaskDetail(VMDTaskSummary):
    """Detail view of a VMD task (used in get_task endpoint)."""

    description: str = ""
    sub_tasks: list[VMDSubTaskResponse] = Field(default_factory=list)
    wbs_structure: dict | None = None
    total_sub_tasks: int = 0
    completed_sub_tasks: int = 0
    user_id: str = ""
    deadline: str | None = None


# ---------------------------------------------------------------------------
# Approval Progress Response Models
# ---------------------------------------------------------------------------


class ApprovalProgressResponse(BaseModel):
    """Approval chain progress response."""

    chain_steps: list[dict] | None = None
    current_step: int = 0
    approval_history: list[dict] = Field(default_factory=list)
    status: str = "pending"
    risk_analysis: dict | None = None
