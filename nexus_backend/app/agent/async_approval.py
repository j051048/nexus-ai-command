"""
P1-2: 异步审批系统
"""

import logging
from datetime import datetime

from app.core.database import supabase

logger = logging.getLogger(__name__)

# 需要审批的关键操作
CRITICAL_OPERATIONS = {
    "delete_customer": "删除客户会导致所有关联数据丢失",
    "approve_payment": "此操作将立即转账，无法撤销",
    "terminate_contract": "合同终止后无法恢复",
    "delete_contract": "删除合同记录不可恢复",
    "batch_delete": "批量删除操作风险极高",
}


class AsyncApprovalSystem:
    """异步审批系统"""

    async def request_approval(
        self,
        tool_name: str,
        args: dict,
        user_id: str,
        thread_id: str,
        org_id: str | None = None,
    ) -> str:
        """发起审批请求（非阻塞）"""
        try:
            warning = CRITICAL_OPERATIONS.get(tool_name, "此操作需要审批")

            result = (
                await supabase.table("approval_requests")
                .insert(
                    {
                        "tool_name": tool_name,
                        "args": args,
                        "user_id": user_id,
                        "thread_id": thread_id,
                        "org_id": org_id,
                        "status": "pending",
                        "warning": warning,
                        "created_at": datetime.utcnow().isoformat(),
                    }
                )
                .execute()
            )

            approval_id = result.data[0]["id"]

            # TODO: 发送通知（邮件/IM）
            logger.info(f"Approval request created: {approval_id}")

            return approval_id

        except Exception as e:
            logger.error(f"Failed to create approval request: {e}")
            raise

    async def check_approval_status(self, approval_id: str) -> dict:
        """检查审批状态"""
        result = (
            await supabase.table("approval_requests")
            .select("*")
            .eq("id", approval_id)
            .single()
            .execute()
        )

        return result.data

    def requires_approval(self, tool_name: str) -> bool:
        """检查工具是否需要审批"""
        return tool_name in CRITICAL_OPERATIONS


# 全局实例
async_approval = AsyncApprovalSystem()
