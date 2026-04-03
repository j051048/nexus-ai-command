"""AI辅助API路由
P0-1: 语音意图解析
P0-2: 批量审批建议
P0-4: 语义搜索
"""
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.core.database import supabase
from app.services.ai_voice_parser import parse_voice_intent
from app.services.llm_gateway import get_llm

router = APIRouter(prefix="/api/ai", tags=["ai-assistant"])


@router.post("/parse-voice-intent")
async def parse_voice(
    text: str,
    current_user=Depends(get_current_user)
):
    """解析语音意图"""
    result = await parse_voice_intent(
        text=text,
        user_id=current_user["id"],
        org_id=current_user.get("org_id", "default")
    )
    return result


@router.post("/batch-approval-suggestions")
async def batch_approval_suggestions(
    request_ids: list[str],
    current_user=Depends(get_current_user)
):
    """AI批量审批建议"""
    # 获取申请详情
    requests = await supabase.table("approval_requests").select("*").in_(
        "id", request_ids
    ).execute()

    # AI分析
    llm = get_llm(org_id=current_user.get("org_id", "default"))
    prompt = f"""分析以下{len(requests.data)}个审批申请,给出批量审批建议:
{[f"{r['title']}: ¥{r.get('amount', 0)}" for r in requests.data]}

返回JSON: {{"approve_count": 数字, "reject_count": 数字, "reason": "原因"}}
"""

    result = await llm.ainvoke(prompt)
    import json
    return json.loads(str(result))
