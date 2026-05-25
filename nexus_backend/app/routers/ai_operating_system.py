"""AI operating system APIs.

These endpoints turn the P0-P6 product blueprint into a live operator surface:
real Agent run data, action telemetry, simulation, and business graph context.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.services.business_context_graph import build_business_context_graph

router = APIRouter(prefix="/api/ai-operating-system", tags=["AI Operating System"])


class SimulationRequest(BaseModel):
    messages: list[str] = Field(default_factory=list, max_length=20)
    candidate_policy: str = Field(
        default="低风险自动执行，高风险进入人工确认", max_length=500
    )
    baseline_policy: str = Field(default="全部建议人工点击执行", max_length=500)


def _db(request: Request):
    client = getattr(request.state, "db", None)
    if client is None:
        raise api_error(
            ErrorCode.DB_CONNECTION_ERROR, "Database client is not available"
        )
    return client


async def _safe_select(
    db: Any,
    table: str,
    select: str,
    *,
    since: str | None = None,
    order_by: str = "updated_at",
    limit: int = 100,
) -> list[dict[str, Any]]:
    try:
        query = db.table(table).select(select)
        if since:
            query = query.gte(order_by, since)
        result = await query.order(order_by, desc=True).limit(limit).execute()
        return result.data or []
    except Exception:
        return []


def _agent_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(runs)
    failed = sum(
        1 for item in runs if item.get("status") in {"failed", "error", "cancelled"}
    )
    completed = sum(
        1 for item in runs if item.get("status") in {"completed", "success", "done"}
    )
    tool_failures = sum(
        1
        for item in runs
        if str(item.get("error") or item.get("error_message") or "").strip()
    )
    total_cost = sum(
        float(item.get("cost_usd") or item.get("total_cost") or 0) for item in runs
    )
    total_tokens = sum(
        int(item.get("input_tokens") or item.get("total_input_tokens") or 0)
        + int(item.get("output_tokens") or item.get("total_output_tokens") or 0)
        for item in runs
    )
    return {
        "total_runs": total,
        "completed": completed,
        "failed": failed,
        "failure_rate": round(failed / total, 4) if total else 0,
        "success_rate": round(completed / total, 4) if total else 0,
        "tool_failure_signals": tool_failures,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
    }


def _action_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(events)
    completed = sum(1 for item in events if item.get("event_type") == "completed")
    accepted = sum(1 for item in events if item.get("event_type") == "accepted")
    ignored = sum(1 for item in events if item.get("event_type") == "ignored")
    return {
        "total_events": total,
        "accepted": accepted,
        "completed": completed,
        "ignored": ignored,
        "completion_rate": round(completed / total, 4) if total else 0,
        "acceptance_rate": round(accepted / total, 4) if total else 0,
    }


def _intent_for(message: str) -> tuple[str, list[str]]:
    text = message.lower()
    if any(token in text for token in ["审批", "报销", "批准", "驳回", "approval"]):
        return "approval_decision", ["query_pending_approvals", "approval_risk_check"]
    if any(token in text for token in ["投标", "标书", "招标", "评分", "tender"]):
        return "tender_support", ["parse_tender_document", "score_tender_response"]
    if any(
        token in text for token in ["竞品", "thermo", "agilent", "shimadzu", "战卡"]
    ):
        return "battlecard", ["load_knowledge", "generate_battlecard"]
    if any(token in text for token in ["合同", "续约", "复购", "到期", "renewal"]):
        return "renewal_or_contract", ["query_contracts", "create_followup_task"]
    if any(token in text for token in ["客户", "线索", "crm", "跟进", "拜访"]):
        return "crm_followup", ["search_customers", "draft_followup"]
    return "general_assistant", ["answer_with_context"]


def _risk_for(message: str, intent: str) -> tuple[int, list[str], str]:
    text = message.lower()
    flags: list[str] = []
    score = 20
    gate = "auto"
    if intent in {"approval_decision", "renewal_or_contract"}:
        score += 35
        flags.append("涉及审批、合同或财务结果，默认需要人工确认")
        gate = "hitl"
    if any(
        token in text
        for token in ["删除", "打款", "付款", "发送给客户", "外发", "批量"]
    ):
        score += 30
        flags.append("包含外发、付款、删除或批量动作")
        gate = "hitl"
    if any(token in text for token in ["10000", "十万", "百万", "高风险"]):
        score += 20
        flags.append("存在金额或高风险信号")
        gate = "hitl"
    if not flags:
        flags.append("低风险信息处理或草稿生成，可自动执行")
    return min(score, 100), flags, gate


def _simulate_messages(messages: list[str], candidate_policy: str) -> dict[str, Any]:
    cases = []
    auto_count = 0
    hitl_count = 0
    total_risk = 0
    for index, message in enumerate(messages, start=1):
        intent, tools = _intent_for(message)
        risk_score, flags, gate = _risk_for(message, intent)
        if gate == "auto":
            auto_count += 1
        else:
            hitl_count += 1
        total_risk += risk_score
        cases.append(
            {
                "id": f"case-{index}",
                "message": message,
                "detected_intent": intent,
                "suggested_tools": tools,
                "baseline": {
                    "mode": "recommend_only",
                    "expected_outcome": "生成建议，等待人工点击执行",
                },
                "candidate": {
                    "mode": gate,
                    "policy": candidate_policy,
                    "expected_outcome": (
                        "自动执行低风险步骤" if gate == "auto" else "进入人工确认门"
                    ),
                },
                "risk_score": risk_score,
                "risk_flags": flags,
            }
        )
    total = len(messages)
    return {
        "cases": cases,
        "summary": {
            "case_count": total,
            "automation_rate": round(auto_count / total, 4) if total else 0,
            "hitl_rate": round(hitl_count / total, 4) if total else 0,
            "avg_risk_score": round(total_risk / total, 1) if total else 0,
            "recommendation": (
                "可上线灰度"
                if total and hitl_count <= max(1, total // 2)
                else "需要补充护栏"
            ),
        },
    }


@router.get("/overview")
async def get_ai_operating_overview(
    request: Request,
    days: int = Query(30, ge=1, le=90),
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    db = _db(request)
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    runs = await _safe_select(
        db,
        "agent_runs",
        "id, run_id, status, input_summary, output_summary, error, error_message, "
        "metadata, input_tokens, output_tokens, cost_usd, total_input_tokens, "
        "total_output_tokens, total_cost, duration_ms, updated_at, started_at",
        since=since,
        order_by="updated_at",
        limit=200,
    )
    events = await _safe_select(
        db,
        "action_events",
        "id, action_id, source, source_id, event_type, status, user_id, metadata, created_at",
        since=since,
        order_by="created_at",
        limit=300,
    )
    graph = await build_business_context_graph(db, org_id=org_id, user_id=user_id)

    return api_success(
        data={
            "window_days": days,
            "agent": _agent_summary(runs),
            "actions": _action_summary(events),
            "graph": graph,
            "recent_runs": [
                {
                    "id": item.get("id"),
                    "run_id": item.get("run_id"),
                    "status": item.get("status"),
                    "input_summary": item.get("input_summary"),
                    "updated_at": item.get("updated_at") or item.get("started_at"),
                }
                for item in runs[:8]
            ],
            "operating_metrics": {
                "agent_success_rate": _agent_summary(runs)["success_rate"],
                "action_completion_rate": _action_summary(events)["completion_rate"],
                "context_graph_nodes": graph["summary"]["node_count"],
                "context_graph_edges": graph["summary"]["edge_count"],
            },
        }
    )


@router.get("/context-graph")
async def get_ai_context_graph(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    graph = await build_business_context_graph(
        _db(request), org_id=org_id, user_id=user_id
    )
    return api_success(data=graph)


@router.post("/simulate")
async def simulate_agent_policy(
    payload: SimulationRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    messages = [item.strip() for item in payload.messages if item.strip()]
    if not messages:
        recent = await _safe_select(
            _db(request),
            "agent_runs",
            "input_summary, updated_at",
            order_by="updated_at",
            limit=8,
        )
        messages = [
            item.get("input_summary")
            for item in recent
            if isinstance(item.get("input_summary"), str) and item.get("input_summary")
        ]
    if not messages:
        messages = [
            "30天未跟进客户自动生成拜访提醒和邮件草稿",
            "审批一笔12000元差旅报销并检查风险",
            "根据招标文件生成评分矩阵和技术响应草稿",
        ]

    graph = await build_business_context_graph(
        _db(request), org_id=org_id, user_id=user_id
    )
    simulation = _simulate_messages(messages[:20], payload.candidate_policy)
    simulation["context_graph_summary"] = graph["summary"]
    simulation["baseline_policy"] = payload.baseline_policy
    simulation["candidate_policy"] = payload.candidate_policy
    return api_success(data=simulation)
