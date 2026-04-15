"""AI辅助API路由
P0-1: 语音意图解析
P0-2: 批量审批建议
P0-4: 语义搜索
P0-7: 客户AI记忆摘要
"""

import json
import logging
from time import time as _time

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.dependencies import get_db, get_org_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.ai_voice_parser import parse_voice_intent
from app.services.llm_gateway import get_llm

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai-assistant"])

# 客户记忆摘要缓存: key=(customer_name, user_id), value=(summary, timestamp)
_memory_summary_cache: dict[tuple[str, str], tuple[dict, float]] = {}
_MEMORY_SUMMARY_TTL = 600  # 10 minutes


@router.post("/parse-voice-intent")
async def parse_voice(
    text: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """解析语音意图"""
    # P0-2 Security Fix: org_id 必须由中间件注入，不允许回退到 "default"
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_ROLE_REQUIRED, "租户上下文缺失，请重新登录")
    result = await parse_voice_intent(
        text=text,
        user_id=user_id,
        org_id=org_id,
    )
    return result


@router.post("/batch-approval-suggestions")
async def batch_approval_suggestions(
    request_ids: list[str],
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """AI批量审批建议"""
    if not request_ids:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "request_ids 不能为空")
    if len(request_ids) > 50:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "批量审批最多支持50条")

    # P0 Security: 使用 scoped DB client（RLS 隔离），不使用全局 supabase
    requests_result = (
        await db.table("approval_requests")
        .select("*")
        .in_("id", request_ids)
        .execute()
    )

    if not requests_result.data:
        return api_success(data={"approve_count": 0, "reject_count": 0, "reason": "未找到匹配的审批申请"})

    # P0-2 Security Fix: org_id 必须由中间件注入，不允许回退到 "default"
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_ROLE_REQUIRED, "租户上下文缺失，请重新登录")
    llm = get_llm(org_id=org_id)
    prompt = f"""分析以下{len(requests_result.data)}个审批申请,给出批量审批建议:
{[f"{r.get('title', '未命名')}: ¥{r.get('amount', 0)}" for r in requests_result.data]}

返回JSON: {{"approve_count": 数字, "reject_count": 数字, "reason": "原因"}}
"""

    try:
        result = await llm.ainvoke(prompt)
        result_text = str(result.content if hasattr(result, "content") else result)

        # P0 Security: 安全解析 LLM 输出，防止注入
        clean = result_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            clean = clean.rsplit("```", 1)[0]
        parsed = json.loads(clean.strip())

        # Schema 校验：只返回预期字段
        suggestion = {
            "approve_count": int(parsed.get("approve_count", 0)),
            "reject_count": int(parsed.get("reject_count", 0)),
            "reason": str(parsed.get("reason", ""))[:500],
        }
        return api_success(data=suggestion)

    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        logger.warning(f"LLM output parse failed for batch-approval: {e}")
        return api_success(
            data={
                "approve_count": 0,
                "reject_count": len(requests_result.data),
                "reason": "AI分析结果解析失败，建议人工逐条审批",
            }
        )
    except Exception as e:
        logger.error(f"Batch approval suggestion failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "AI分析失败，请稍后重试")


@router.get("/customer-memory-summary/{customer_name}")
async def get_customer_memory_summary(
    customer_name: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """获取客户的 AI 记忆摘要

    通过客户名称在 conversation_memories 中搜索相关记忆，
    利用 LLM 生成结构化洞察摘要。结果缓存10分钟。
    """
    # P0-2 Security Fix: org_id 必须由中间件注入，不允许回退到 "default"
    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_ROLE_REQUIRED, "租户上下文缺失，请重新登录")
    cache_key = (customer_name.lower(), user_id)

    # 检查缓存
    if cache_key in _memory_summary_cache:
        cached, ts = _memory_summary_cache[cache_key]
        if (_time() - ts) < _MEMORY_SUMMARY_TTL:
            return api_success(data=cached, message="客户AI洞察（缓存）")

    try:
        # P0-7 Security Fix: 不回退到全局 supabase client，必须使用 scoped client
        db = getattr(request.state, "db", None)
        if db is None:
            raise api_error(ErrorCode.AUTH_ROLE_REQUIRED, "租户上下文缺失，请重新登录")

        # 方法1: 按内容关键字搜索
        result = (
            await db.table("conversation_memories")
            .select("content, category, created_at")
            .eq("user_id", user_id)
            .ilike("content", f"%{customer_name}%")
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )

        memories = result.data if result.data else []

        if not memories:
            summary = {
                "has_insights": False,
                "summary": "暂无洞察",
                "key_points": [],
                "last_mentioned": None,
            }
            _memory_summary_cache[cache_key] = (summary, _time())
            return api_success(data=summary, message="暂无相关AI记忆")

        # 通过 LLM 生成摘要
        memory_texts = "\n".join(
            [f"- [{m.get('category', 'general')}] {m['content']}" for m in memories[:15]]
        )

        llm = get_llm(org_id=org_id)
        prompt = f"""根据以下关于客户「{customer_name}」的对话记忆，生成简洁的客户洞察摘要。

记忆内容：
{memory_texts}

请返回 JSON 格式：
{{
  "summary": "一句话总结（50字以内）",
  "key_points": ["关键洞察1", "关键洞察2", "关键洞察3"],
  "sentiment": "positive/neutral/negative",
  "suggested_action": "建议的下一步行动（可选）"
}}

只返回 JSON，不要其他内容。"""

        llm_result = await llm.ainvoke(prompt)
        llm_text = str(llm_result.content if hasattr(llm_result, "content") else llm_result)

        # 尝试解析 JSON
        try:
            # 清理可能的 markdown 包裹
            clean = llm_text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                clean = clean.rsplit("```", 1)[0]
            insights = json.loads(clean.strip())
        except (json.JSONDecodeError, IndexError):
            insights = {
                "summary": llm_text[:100],
                "key_points": [],
                "sentiment": "neutral",
            }

        summary = {
            "has_insights": True,
            "summary": insights.get("summary", ""),
            "key_points": insights.get("key_points", [])[:5],
            "sentiment": insights.get("sentiment", "neutral"),
            "suggested_action": insights.get("suggested_action"),
            "last_mentioned": memories[0].get("created_at") if memories else None,
            "memory_count": len(memories),
        }

        _memory_summary_cache[cache_key] = (summary, _time())
        return api_success(data=summary, message="客户AI洞察")

    except Exception as e:
        logger.error(f"Customer memory summary error: {e}")
        return api_success(
            data={"has_insights": False, "summary": "获取洞察时出错", "key_points": []},
            message="获取洞察失败",
        )
