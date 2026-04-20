"""AI辅助API路由
P0-1: 语音意图解析
P0-2: 批量审批建议 → 改为后台任务 + 轮询
P0-4: 语义搜索
P0-7: 客户AI记忆摘要 → 改为后台任务 + 轮询
"""

import json
import logging
import uuid
from time import time as _time

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.core.auth import get_current_user_id
from app.core.dependencies import get_db, get_org_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.ai_voice_parser import parse_voice_intent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai-assistant"])

# 客户记忆摘要缓存: key=(customer_name, user_id), value=(summary, timestamp)
_memory_summary_cache: dict[tuple[str, str], tuple[dict, float]] = {}
_MEMORY_SUMMARY_TTL = 600  # 10 minutes

# ── 后台任务结果存储 ────────────────────────────────────────────────
# 生产环境应替换为 Redis，这里用进程内 dict 保证快速可用
_task_results: dict[str, dict] = {}
_TASK_RESULT_TTL = 300  # 5 minutes


def _store_task_result(task_id: str, data: dict) -> None:
    """存储后台任务结果（带 TTL 自动清理过期项）。"""
    now = _time()
    _task_results[task_id] = {"data": data, "ts": now}
    # 惰性清理过期结果
    expired = [k for k, v in _task_results.items() if now - v["ts"] > _TASK_RESULT_TTL]
    for k in expired:
        _task_results.pop(k, None)


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


# ── 批量审批建议（异步后台任务版） ─────────────────────────────────

async def _run_batch_approval_analysis(
    task_id: str,
    requests_data: list[dict],
    org_id: str,
) -> None:
    """后台执行 LLM 分析，完成后存储结果。"""
    try:
        from app.services.llm_gateway import llm_gateway

        prompt = f"""分析以下{len(requests_data)}个审批申请,给出批量审批建议:
{[f"{r.get('title', '未命名')}: ¥{r.get('amount', 0)}" for r in requests_data]}

返回JSON: {{"approve_count": 数字, "reject_count": 数字, "reason": "原因"}}
"""
        response = await llm_gateway.chat(
            scene_code="batch_approval",
            agent_code="analyzer",
            user_id="system",
            org_id=org_id,
            system_prompt="你是一个审批分析助手，只返回 JSON 格式的分析结果。",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.3,
        )

        if response.finish_reason == "error":
            _store_task_result(task_id, {
                "status": "error",
                "result": {
                    "approve_count": 0,
                    "reject_count": len(requests_data),
                    "reason": "AI分析失败，建议人工逐条审批",
                },
            })
            return

        result_text = response.content
        # 安全解析 LLM 输出
        clean = result_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            clean = clean.rsplit("```", 1)[0]
        parsed = json.loads(clean.strip())

        suggestion = {
            "approve_count": int(parsed.get("approve_count", 0)),
            "reject_count": int(parsed.get("reject_count", 0)),
            "reason": str(parsed.get("reason", ""))[:500],
        }
        _store_task_result(task_id, {"status": "completed", "result": suggestion})

    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        logger.warning(f"LLM output parse failed for batch-approval: {e}")
        _store_task_result(task_id, {
            "status": "completed",
            "result": {
                "approve_count": 0,
                "reject_count": len(requests_data),
                "reason": "AI分析结果解析失败，建议人工逐条审批",
            },
        })
    except Exception as e:
        logger.error(f"Batch approval background task failed: {e}")
        _store_task_result(task_id, {
            "status": "error",
            "result": {
                "approve_count": 0,
                "reject_count": len(requests_data),
                "reason": f"AI分析出错: {str(e)[:100]}",
            },
        })


@router.post("/batch-approval-suggestions")
async def batch_approval_suggestions(
    request_ids: list[str],
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db=Depends(get_db),
):
    """AI批量审批建议 — 提交后台任务，立即返回 task_id 供轮询。"""
    if not request_ids:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "request_ids 不能为空")
    if len(request_ids) > 50:
        raise api_error(ErrorCode.VALIDATION_INVALID_INPUT, "批量审批最多支持50条")

    # P0 Security: 使用 scoped DB client（RLS 隔离）
    requests_result = (
        await db.table("approval_requests")
        .select("*")
        .in_("id", request_ids)
        .execute()
    )

    if not requests_result.data:
        return api_success(data={"approve_count": 0, "reject_count": 0, "reason": "未找到匹配的审批申请"})

    org_id = getattr(request.state, "org_id", None)
    if not org_id:
        raise api_error(ErrorCode.AUTH_ROLE_REQUIRED, "租户上下文缺失，请重新登录")

    # 生成 task_id，后台执行 LLM 分析
    task_id = str(uuid.uuid4())
    _store_task_result(task_id, {"status": "processing", "result": None})
    background_tasks.add_task(
        _run_batch_approval_analysis,
        task_id,
        requests_result.data,
        org_id,
    )

    return api_success(data={"task_id": task_id, "status": "processing"})


# ── 客户记忆摘要（异步后台任务版） ─────────────────────────────────

async def _run_customer_memory_analysis(
    task_id: str,
    customer_name: str,
    memories: list[dict],
    user_id: str,
    org_id: str,
) -> None:
    """后台执行客户记忆 LLM 分析。"""
    try:
        from app.services.llm_gateway import llm_gateway

        memory_texts = "\n".join(
            [f"- [{m.get('category', 'general')}] {m['content']}" for m in memories[:15]]
        )

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

        response = await llm_gateway.chat(
            scene_code="customer_memory",
            agent_code="analyzer",
            user_id=user_id,
            org_id=org_id,
            system_prompt="你是一个客户洞察分析助手，只返回 JSON 格式的分析结果。",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.3,
        )

        if response.finish_reason == "error":
            raise RuntimeError(f"LLM gateway error: {response.raw_response}")

        llm_text = response.content

        # 解析 JSON
        try:
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

        # 写入缓存
        cache_key = (customer_name.lower(), user_id)
        _memory_summary_cache[cache_key] = (summary, _time())
        _store_task_result(task_id, {"status": "completed", "result": summary})

    except Exception as e:
        logger.error(f"Customer memory background task failed: {e}")
        _store_task_result(task_id, {
            "status": "error",
            "result": {"has_insights": False, "summary": "获取洞察时出错", "key_points": []},
        })


@router.get("/customer-memory-summary/{customer_name}")
async def get_customer_memory_summary(
    customer_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
):
    """获取客户的 AI 记忆摘要 — 命中缓存则直接返回，否则提交后台任务。"""
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
        db = getattr(request.state, "db", None)
        if db is None:
            raise api_error(ErrorCode.AUTH_ROLE_REQUIRED, "租户上下文缺失，请重新登录")

        # 按内容关键字搜索（转义 LIKE 通配符防止模式注入）
        safe_name = customer_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        result = (
            await db.table("conversation_memories")
            .select("content, category, created_at")
            .eq("user_id", user_id)
            .ilike("content", f"%{safe_name}%")
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

        # 提交后台任务
        task_id = str(uuid.uuid4())
        _store_task_result(task_id, {"status": "processing", "result": None})
        background_tasks.add_task(
            _run_customer_memory_analysis,
            task_id,
            customer_name,
            memories,
            user_id,
            org_id,
        )

        return api_success(data={"task_id": task_id, "status": "processing"})

    except Exception as e:
        logger.error(f"Customer memory summary error: {e}")
        return api_success(
            data={"has_insights": False, "summary": "获取洞察时出错", "key_points": []},
            message="获取洞察失败",
        )


# ── 通用任务结果轮询接口 ────────────────────────────────────────────

@router.get("/task-result/{task_id}")
async def get_task_result(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """轮询后台 AI 分析任务的结果。

    返回:
      - status: "processing" | "completed" | "error"
      - result: 任务完成后的数据，processing 时为 null
    """
    if task_id not in _task_results:
        raise api_error(ErrorCode.NOT_FOUND, "任务不存在或已过期")

    entry = _task_results[task_id]
    data = entry["data"]

    # 完成或出错后标记已读，第二次轮询再清理（容忍一次网络重试）
    if data.get("status") in ("completed", "error"):
        if entry.get("_read_once"):
            _task_results.pop(task_id, None)
        else:
            entry["_read_once"] = True

    return api_success(data=data)
