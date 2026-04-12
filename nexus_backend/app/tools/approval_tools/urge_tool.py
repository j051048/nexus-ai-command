import logging
from typing import Any

import app.tools.approval_tools as _pkg

from app.tools._shared import safe_tool_error, _validate_uuid

from ..base_tool import BaseTool

logger = logging.getLogger(__name__)


class UrgeApprovalTool(BaseTool):
    """催办审批请求"""

    name = "urge_approval"
    description = (
        "催办某个正在等待审批的请示或流程，提高它的紧急处理等级并记录催办原因。"
    )
    examples = [
        {
            "input": {"approval_id": "uuid-xxxx", "reason": "客户催得急"},
            "output_summary": "成功催办审批",
        },
    ]
    gotchas = "只能催办状态为'pending'的审批。需要提供催办原因。"
    related_tools = ["get_pending_approvals", "approve_request"]

    parameters = {
        "type": "object",
        "properties": {
            "approval_id": {"type": "string", "description": "要催办的审批单的ID"},
            "reason": {"type": "string", "description": "催办的原因或理由"},
        },
        "required": ["approval_id", "reason"],
    }
    domain = "approval"

    async def run(
        self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None
    ) -> str:
        client = _pkg._get_client(config)
        approval_id = args.get("approval_id")
        reason = args.get("reason", "加急处理")

        if not approval_id:
            return "❌ 请提供要催办的审批单ID"

        if err := _validate_uuid(approval_id, "approval_id"):
            return f"❌ {err}"

        from app.services.approval_service import ApprovalService

        try:
            res = await ApprovalService.urge_approval(
                approval_id, user_id, reason, db=client
            )
            return f"✅ 催办成功！该审批的催单次数为 {res.get('urgency_count', 1)}。已通知管理员处理。"
        except Exception as e:
            return safe_tool_error(e, "催办审批")
