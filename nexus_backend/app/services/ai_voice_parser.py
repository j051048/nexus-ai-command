"""AI语音意图解析服务
P0-1: 解析"帮我报销昨天去广德的机票1926元"
"""
import logging
from datetime import datetime, timedelta
from app.services.llm_gateway import get_llm

logger = logging.getLogger(__name__)


async def parse_voice_intent(text: str, user_id: str, org_id: str):
    """AI解析语音意图并提取结构化数据"""
    try:
        llm = get_llm(org_id=org_id)

        prompt = f"""解析用户语音申请,提取结构化数据:
"{text}"

返回JSON格式:
{{
  "type": "expense|leave|travel",
  "amount": 数字,
  "description": "描述",
  "date": "YYYY-MM-DD",
  "expense_type": "交通|住宿|餐饮|其他"
}}

规则:
- "昨天"转换为实际日期
- 识别金额数字
- 识别申请类型(报销/请假/差旅)
"""

        result = await llm.ainvoke(prompt)

        # 解析LLM返回的JSON
        import json
        data = json.loads(str(result))

        # 补充用户信息
        data["user_id"] = user_id
        data["org_id"] = org_id

        return data

    except Exception as e:
        logger.error(f"[AI Voice] Parse failed: {e}")
        return None
