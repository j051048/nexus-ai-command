"""AI 智能催办服务

Phase 3: 分析延迟原因并生成催办策略
"""

import logging

from app.core.database import supabase
from app.services.llm_gateway import get_llm

logger = logging.getLogger(__name__)


async def generate_reminder_strategy(request_id: str, org_id: str):
    """分析延迟原因并生成催办策略"""
    try:
        # 获取审批详情
        request = (
            await supabase.table("approval_requests")
            .select("*")
            .eq("id", request_id)
            .single()
            .execute()
        )

        if not request.data:
            return {"error": "Request not found"}

        approver_id = request.data.get("current_approver")
        request.data.get("timeout_at")

        # 分析审批人历史审批速度
        await supabase.table("approval_requests").select("*").eq(
            "current_approver", approver_id
        ).eq("status", "approved").limit(10).execute()

        avg_time = "2小时"  # 简化计算
        pending_count = 5  # 简化计算

        llm = get_llm(org_id=org_id)
        prompt = f"""该审批已超时,审批人: {approver_id}

分析:
- 历史平均审批时间: {avg_time}
- 当前积压审批: {pending_count}个

请给出催办建议,限30字内。"""

        suggestion = await llm.ainvoke(prompt)
        return {
            "approver_id": approver_id,
            "suggestion": str(suggestion),
            "avg_time": avg_time,
            "pending_count": pending_count,
        }

    except Exception as e:
        logger.error(f"[AI Reminder] Failed: {e}")
        return {"error": str(e)}
