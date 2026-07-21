"""Operator APIs for durable Agent run observability."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_success

router = APIRouter(prefix="/api/agent-runs", tags=["Agent Observability"])
require_agent_ops = require_role(["admin", "founder", "boss"])

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _db(request: Request):
    client = getattr(request.state, "db", None)
    if client is None:
        raise api_error(
            ErrorCode.DB_CONNECTION_ERROR,
            message="Database client is not available",
        )
    return client


def _redact_run(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata") or {}
    return {
        "id": row.get("id"),
        "run_id": row.get("run_id"),
        "thread_id": row.get("thread_id"),
        "trace_id": row.get("trace_id"),
        "session_id": row.get("session_id"),
        "scene_code": row.get("scene_code"),
        "agent_code": row.get("agent_code"),
        "status": row.get("status"),
        "input_summary": row.get("input_summary"),
        "output_summary": row.get("output_summary"),
        "final_response": row.get("final_response"),
        "error": row.get("error"),
        "error_message": row.get("error_message"),
        "metadata": metadata,
        "input_tokens": row.get("input_tokens") or row.get("total_input_tokens") or 0,
        "output_tokens": row.get("output_tokens")
        or row.get("total_output_tokens")
        or 0,
        "cost_usd": float(row.get("cost_usd") or row.get("total_cost") or 0),
        "duration_ms": row.get("duration_ms"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
        "updated_at": row.get("updated_at"),
    }


def _summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    total_cost = 0.0
    total_tokens = 0
    completed_durations: list[int] = []
    for run in runs:
        status = run.get("status") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        total_cost += float(run.get("cost_usd") or 0)
        total_tokens += int(run.get("input_tokens") or 0) + int(
            run.get("output_tokens") or 0
        )
        if isinstance(run.get("duration_ms"), int):
            completed_durations.append(run["duration_ms"])

    avg_duration_ms = (
        round(sum(completed_durations) / len(completed_durations))
        if completed_durations
        else None
    )
    return {
        "total_runs": len(runs),
        "by_status": by_status,
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "avg_duration_ms": avg_duration_ms,
    }


def _summarize_artifact_quality(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, dict[str, Any]] = {}
    failure_codes: dict[str, int] = {}
    for event in events:
        artifact_type = str(event.get("artifact_type") or "unknown")
        bucket = by_type.setdefault(
            artifact_type,
            {"count": 0, "ready": 0, "score_total": 0.0},
        )
        bucket["count"] += 1
        bucket["ready"] += int(bool(event.get("ready")))
        bucket["score_total"] += float(event.get("score") or 0)
        for finding in event.get("findings") or []:
            code = str(finding.get("code") or "unknown")
            failure_codes[code] = failure_codes.get(code, 0) + 1

    type_summary = {
        key: {
            "count": value["count"],
            "ready_rate": round(value["ready"] / value["count"], 4),
            "avg_score": round(value["score_total"] / value["count"], 2),
        }
        for key, value in by_type.items()
    }
    total = len(events)
    return {
        "available": True,
        "sample_size": total,
        "ready_rate": (
            round(sum(int(bool(item.get("ready"))) for item in events) / total, 4)
            if total
            else 0
        ),
        "avg_score": (
            round(sum(float(item.get("score") or 0) for item in events) / total, 2)
            if total
            else 0
        ),
        "avg_evidence_count": (
            round(
                sum(int(item.get("evidence_count") or 0) for item in events) / total, 2
            )
            if total
            else 0
        ),
        "avg_repair_count": (
            round(sum(int(item.get("repair_count") or 0) for item in events) / total, 2)
            if total
            else 0
        ),
        "by_artifact_type": type_summary,
        "top_failure_codes": dict(
            sorted(failure_codes.items(), key=lambda item: item[1], reverse=True)[:10]
        ),
    }


@router.get("")
@router.get("/")
async def list_agent_runs(
    request: Request,
    _role: str = Depends(require_agent_ops),
    _org_id: str = Depends(get_current_org_id),
    status: str | None = Query(None, max_length=40),
    session_id: str | None = Query(None, max_length=128),
    limit: int = Query(50, ge=1, le=200),
):
    """List recent Agent runs for the current tenant."""
    query = (
        _db(request)
        .table("agent_runs")
        .select(
            "id, run_id, thread_id, trace_id, session_id, scene_code, agent_code, "
            "status, input_summary, output_summary, error, error_message, metadata, "
            "input_tokens, output_tokens, cost_usd, total_input_tokens, "
            "total_output_tokens, total_cost, duration_ms, started_at, finished_at, updated_at"
        )
    )
    if status:
        query = query.eq("status", status)
    if session_id:
        query = query.eq("session_id", session_id)

    result = await query.order("updated_at", desc=True).limit(limit).execute()
    runs = [_redact_run(row) for row in (result.data or [])]
    return api_success(
        data={"runs": runs, "summary": _summarize(runs)},
        meta={"limit": limit, "count": len(runs)},
    )


@router.get("/summary")
async def get_agent_runs_summary(
    request: Request,
    _role: str = Depends(require_agent_ops),
    _org_id: str = Depends(get_current_org_id),
    limit: int = Query(200, ge=20, le=500),
):
    """Return a low-cost aggregate over recent Agent runs."""
    result = (
        await _db(request)
        .table("agent_runs")
        .select(
            "status, input_tokens, output_tokens, cost_usd, total_input_tokens, "
            "total_output_tokens, total_cost, duration_ms"
        )
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    runs = [_redact_run(row) for row in (result.data or [])]
    return api_success(data=_summarize(runs), meta={"sample_size": len(runs)})


@router.get("/quality/trends")
async def get_agent_quality_trends(
    request: Request,
    _role: str = Depends(require_agent_ops),
    _org_id: str = Depends(get_current_org_id),
    days: int = Query(30, ge=1, le=90),
):
    """Return eval/quality trend data for operator dashboards."""
    from datetime import UTC, datetime, timedelta

    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    client = _db(request)
    runs_result = (
        await client.table("agent_runs")
        .select(
            "status, input_tokens, output_tokens, cost_usd, duration_ms, started_at"
        )
        .gte("started_at", since)
        .execute()
    )
    eval_result = (
        await client.table("agent_eval_cases")
        .select("status, dimension, created_at")
        .gte("created_at", since)
        .execute()
    )
    runs = runs_result.data or []
    eval_cases = eval_result.data or []
    failures = [r for r in runs if r.get("status") in {"failed", "error"}]
    total_tokens = sum(
        int(r.get("input_tokens") or 0) + int(r.get("output_tokens") or 0) for r in runs
    )
    return api_success(
        data={
            "days": days,
            "run_count": len(runs),
            "failure_rate": round(len(failures) / len(runs), 4) if runs else 0,
            "total_tokens": total_tokens,
            "total_cost_usd": round(
                sum(float(r.get("cost_usd") or 0) for r in runs), 6
            ),
            "avg_duration_ms": (
                round(sum(int(r.get("duration_ms") or 0) for r in runs) / len(runs))
                if runs
                else 0
            ),
            "eval_cases": {
                "total": len(eval_cases),
                "pending_label": sum(
                    1 for c in eval_cases if c.get("status") == "pending_label"
                ),
                "by_dimension": {
                    dim: sum(1 for c in eval_cases if c.get("dimension") == dim)
                    for dim in sorted({c.get("dimension") for c in eval_cases})
                    if dim
                },
            },
        }
    )


@router.get("/quality/artifacts")
async def get_artifact_quality_summary(
    request: Request,
    _role: str = Depends(require_agent_ops),
    org_id: str = Depends(get_current_org_id),
    days: int = Query(30, ge=1, le=90),
    limit: int = Query(500, ge=20, le=2000),
):
    """Expose artifact readiness, evidence coverage, and repair health."""
    from datetime import UTC, datetime, timedelta

    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    try:
        result = (
            await _db(request)
            .table("agent_artifact_quality_events")
            .select(
                "artifact_type,score,ready,dimensions,findings,skill_id,skill_version,"
                "evidence_count,repair_count,created_at"
            )
            .eq("organization_id", org_id)
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception:
        return api_success(
            data={"available": False, "sample_size": 0},
            message="成果质量数据尚未就绪",
        )
    events = result.data or []
    return api_success(
        data={"days": days, **_summarize_artifact_quality(events)},
        meta={"limit": limit},
    )


@router.get("/prompt-lint")
async def lint_runtime_prompts(
    _role: str = Depends(require_agent_ops),
    _org_id: str = Depends(get_current_org_id),
):
    """Run static prompt lint checks on the backend prompt registry."""
    from app.services.prompt_linter import prompt_linter

    return api_success(data=prompt_linter.lint_registry())


@router.post("/{run_ref}/shadow-eval")
async def shadow_eval_agent_run(
    run_ref: str,
    request: Request,
    _role: str = Depends(require_agent_ops),
    _org_id: str = Depends(get_current_org_id),
):
    """Run a safe offline shadow assertion against a recorded run."""
    client = _db(request)
    query = client.table("agent_runs").select("*")
    query = (
        query.eq("id", run_ref)
        if _UUID_RE.match(run_ref)
        else query.eq("run_id", run_ref)
    )
    run_result = await query.maybe_single().execute()
    if not run_result.data:
        raise HTTPException(status_code=404, detail="Agent run not found")
    run = run_result.data
    events = (
        await client.table("agent_events")
        .select("event_type, node_name, payload, created_at")
        .eq("agent_run_id", run.get("id"))
        .order("id", desc=False)
        .limit(500)
        .execute()
    )
    steps = [
        {
            "node_type": e.get("node_name") or e.get("event_type"),
            "output_data": e.get("payload") or {},
        }
        for e in (events.data or [])
    ]
    trace_data = {
        "trace_id": run.get("trace_id"),
        "total_tokens": int(run.get("input_tokens") or 0)
        + int(run.get("output_tokens") or 0),
        "total_duration_ms": run.get("duration_ms") or 0,
        "final_response": run.get("final_response") or "",
        "steps": steps,
    }
    from app.services.shadow_eval_service import shadow_eval_service

    result = await shadow_eval_service.compare_trace_to_expectations(
        trace_data=trace_data,
        candidate_metadata={"source": "recorded_run"},
    )
    return api_success(data=result)


@router.get("/{run_ref}/context-ablation")
async def get_context_ablation(
    run_ref: str,
    request: Request,
    _role: str = Depends(require_agent_ops),
    _org_id: str = Depends(get_current_org_id),
):
    """Analyze context-provider token savings/risk for a recorded run."""
    client = _db(request)
    query = client.table("agent_runs").select("metadata")
    query = (
        query.eq("id", run_ref)
        if _UUID_RE.match(run_ref)
        else query.eq("run_id", run_ref)
    )
    run_result = await query.maybe_single().execute()
    if not run_result.data:
        raise HTTPException(status_code=404, detail="Agent run not found")
    ledger = (run_result.data.get("metadata") or {}).get("context_ledger") or {}
    from app.services.context_ablation_service import context_ablation_service

    return api_success(data=context_ablation_service.analyze_ledger(ledger))


@router.get("/{run_ref}")
async def get_agent_run_detail(
    run_ref: str,
    request: Request,
    _role: str = Depends(require_agent_ops),
    _org_id: str = Depends(get_current_org_id),
):
    """Fetch a single Agent run by UUID id or stable run_id."""
    client = _db(request)
    query = client.table("agent_runs").select("*")
    query = (
        query.eq("id", run_ref)
        if _UUID_RE.match(run_ref)
        else query.eq("run_id", run_ref)
    )
    run_result = await query.maybe_single().execute()
    if not run_result.data:
        raise HTTPException(status_code=404, detail="Agent run not found")

    run = _redact_run(run_result.data)
    agent_run_id = run.get("id")
    stable_run_id = run.get("run_id")

    tool_query = client.table("agent_tool_calls").select(
        "id, tool_call_id, tool_name, status, risk, tool_args, result_preview, "
        "error_type, error_message, started_at, finished_at, duration_ms"
    )
    event_query = client.table("agent_events").select(
        "id, event_type, node_name, payload, created_at"
    )

    if agent_run_id:
        tool_query = tool_query.eq("agent_run_id", agent_run_id)
        event_query = event_query.eq("agent_run_id", agent_run_id)
    elif stable_run_id:
        tool_query = tool_query.eq("run_id", stable_run_id)
        event_query = event_query.eq("run_id", stable_run_id)

    tool_result = await tool_query.order("started_at", desc=False).limit(200).execute()
    event_result = await event_query.order("id", desc=False).limit(500).execute()
    return api_success(
        data={
            "run": run,
            "tool_calls": tool_result.data or [],
            "events": event_result.data or [],
        }
    )


@router.post("/{run_ref}/replay")
async def replay_failed_agent_run(
    run_ref: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    _role: str = Depends(require_agent_ops),
    org_id: str = Depends(get_current_org_id),
    execute: bool = Query(False, description="Execute a live rerun when true"),
):
    """Prepare or execute a controlled replay for a failed Agent run."""
    client = _db(request)
    query = client.table("agent_runs").select("*")
    query = (
        query.eq("id", run_ref)
        if _UUID_RE.match(run_ref)
        else query.eq("run_id", run_ref)
    )
    run_result = await query.maybe_single().execute()
    if not run_result.data:
        raise HTTPException(status_code=404, detail="Agent run not found")

    run = _redact_run(run_result.data)
    prompt = (
        run.get("input_summary")
        or (run.get("metadata") or {}).get("last_user_message")
        or (run.get("metadata") or {}).get("query")
        or ""
    )
    if not prompt:
        raise api_error(
            ErrorCode.VALIDATION_MISSING_FIELD,
            message="Cannot replay: original input summary is missing",
        )

    replay_plan = {
        "source_run_id": run.get("run_id") or run.get("id"),
        "source_status": run.get("status"),
        "thread_id": f"replay::{run.get('run_id') or run.get('id')}",
        "prompt_preview": prompt[:500],
        "execute": execute,
        "safety": "dry_run_plan" if not execute else "live_rerun_requested",
    }

    if not execute:
        return api_success(data={"replay": replay_plan})

    if run.get("status") not in {"failed", "error", "cancelled"}:
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT,
            message="Only failed/error/cancelled runs can be replayed live",
        )

    from langchain_core.messages import HumanMessage

    from app.agent.graph import get_agent_graph
    from app.agent.state import AgentConfig

    token = ""
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]

    result = await get_agent_graph().run(
        {
            "messages": [HumanMessage(content=prompt)],
            "config": AgentConfig(
                user_id=user_id,
                org_id=org_id,
                session_id=f"replay:{run.get('session_id') or 'default'}",
                token=token,
                user_role=_role,
            ),
            "metadata": {
                "replay_of": run.get("run_id") or run.get("id"),
                "replay_reason": "operator_requested_failed_run_replay",
            },
        },
        thread_id=replay_plan["thread_id"],
    )
    return api_success(
        data={
            "replay": replay_plan,
            "result": {
                "final_response": result.get("final_response"),
                "error": result.get("error"),
                "agent_run_id": result.get("agent_run_id"),
            },
        }
    )
