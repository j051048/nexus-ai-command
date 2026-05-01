"""
P0 Security: Approval Tools with Human Confirmation
Critical security fix #1: AI cannot directly execute irreversible operations
All approval/reject operations now require explicit confirmation.
P0 Enhancement: Uses advance_step for chain-based approvals.
"""

# ── Re-export shared utilities so external patch paths remain valid ──
# Tests use: patch("app.tools.approval_tools._get_client", ...)
# External modules use: from app.tools.approval_tools import _notify_next_approver
from app.tools._shared import _get_client, _validate_uuid  # noqa: F401

from ._constants import (  # noqa: F401
    _LEVEL_NAMES,
    _LEVEL_ROLE_MAP,
    AI_ASSISTANT_ID,
    MAX_BATCH_SIZE,
)
from ._helpers import _notify_next_approver  # noqa: F401
from .approve_tool import ApprovalTool  # noqa: F401
from .query_tools import (  # noqa: F401
    GetEmployeeApprovalHistoryTool,
    GetEmployeeInfoTool,
    PendingApprovalsTool,
)
from .reject_tool import RejectTool  # noqa: F401
from .submit_tool import SubmitApprovalOnBehalfTool  # noqa: F401
from .urge_tool import UrgeApprovalTool  # noqa: F401
