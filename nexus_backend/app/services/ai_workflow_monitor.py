"""AI 工作流监控服务 - 异常预警

Phase 2: 检测报销异常、频率异常、金额异常
"""
import logging
from datetime import datetime, timedelta
from app.core.database import supabase
from app.services.llm_gateway import get_llm

logger = logging.getLogger(__name__)


async def check_expense_anomaly(user_id: str, amount: float, expense_type: str, org_id: str):
    """检测报销异常"""
    try:
        # 获取用户近30天报销记录
        thirty_days_ago = datetime.now() - timedelta(days=30)
        history = await supabase.table("approval_requests").select("*").eq(
            "user_id", user_id
        ).eq("type", "expense").gte("created_at", thirty_days_ago.isoformat()).execute()

        records = history.data or []
        warnings = []

        # 1. 频率异常: 30天内超过10次
        if len(records) > 10:
            warnings.append(f"该用户本月已报销{len(records)}次,频率异常")

        # 2. 金额异常: 超过历史平均3倍
        if records:
            avg_amount = sum(r.get("amount", 0) for r in records) / len(records)
            if amount > avg_amount * 3:
                warnings.append(f"本次金额{amount}元,超过历史平均{avg_amount:.0f}元的3倍")

        # 3. AI 深度分析
        if warnings:
            llm = get_llm(org_id=org_id)
            prompt = f"""分析以下报销异常:
用户: {user_id}
本次报销: {amount}元 ({expense_type})
异常点: {', '.join(warnings)}

请判断风险等级(低/中/高)并给出建议,限50字内。"""

            analysis = await llm.ainvoke(prompt)
            return {
                "has_anomaly": True,
                "risk": "medium",
                "warnings": warnings,
                "suggestion": str(analysis)
            }

        return {"has_anomaly": False}

    except Exception as e:
        logger.error(f"[AI Monitor] Anomaly check failed: {e}")
        return {"has_anomaly": False, "error": str(e)}
