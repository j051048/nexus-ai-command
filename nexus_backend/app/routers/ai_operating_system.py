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


class AgentDefinitionRequest(BaseModel):
    sop_text: str = Field(..., min_length=20, max_length=8000)
    scenario: str = Field(default="科学仪器销售运营", max_length=120)
    autonomy_level: str = Field(default="guarded_auto", max_length=80)


class AgentCIRequest(BaseModel):
    cases: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    candidate_metadata: dict[str, Any] = Field(default_factory=dict)


class AgentProposalDecisionRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|gray_release|rollback)$")
    gray_percentage: int = Field(default=0, ge=0, le=100)
    reviewer_note: str = Field(default="", max_length=1000)


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


async def _safe_count(db: Any, table: str) -> int:
    try:
        result = await db.table(table).select("id", count="exact").limit(1).execute()
        return int(getattr(result, "count", 0) or 0)
    except Exception:
        return 0


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


def _value_summary(
    agent: dict[str, Any], actions: dict[str, Any], events: list[dict[str, Any]]
) -> dict[str, Any]:
    completed_actions = actions["completed"]
    accepted_actions = actions["accepted"]
    saved_minutes = (
        completed_actions * 18 + max(accepted_actions - completed_actions, 0) * 8
    )
    automated_followups = sum(
        1
        for item in events
        if item.get("source") == "crm"
        and item.get("event_type") in {"accepted", "completed", "command_executed"}
    )
    risk_reviews = agent["failed"] + agent["tool_failure_signals"]
    saved_hours = round(saved_minutes / 60, 1)
    estimated_value_cny = round(
        saved_hours * 180 + automated_followups * 120 + risk_reviews * 300
    )
    return {
        "saved_minutes": saved_minutes,
        "saved_hours": saved_hours,
        "automated_followups": automated_followups,
        "risk_reviews": risk_reviews,
        "estimated_value_cny": estimated_value_cny,
        "roi_story": (
            f"近 30 天 AI 约节省 {saved_hours} 小时，自动推进 {automated_followups} 个跟进动作，"
            f"识别/复核 {risk_reviews} 个风险信号，折算业务价值约 ¥{estimated_value_cny}。"
        ),
    }


def _trust_summary(agent: dict[str, Any], actions: dict[str, Any]) -> dict[str, Any]:
    tool_failure_rate = (
        round(agent["tool_failure_signals"] / agent["total_runs"], 4)
        if agent["total_runs"]
        else 0
    )
    human_review_rate = (
        round(1 - actions["acceptance_rate"], 4) if actions["total_events"] else 0
    )
    confidence_score = max(
        0,
        min(
            100,
            round(
                agent["success_rate"] * 70
                + actions["completion_rate"] * 20
                + (1 - tool_failure_rate) * 10
            ),
        ),
    )
    if confidence_score >= 80:
        level = "高"
    elif confidence_score >= 55:
        level = "中"
    else:
        level = "低"
    return {
        "confidence_score": confidence_score,
        "confidence_level": level,
        "human_review_rate": human_review_rate,
        "tool_failure_rate": tool_failure_rate,
        "audit_summary": (
            f"Agent 成功率 {round(agent['success_rate'] * 100)}%，"
            f"行动完成率 {round(actions['completion_rate'] * 100)}%，"
            f"工具失败信号 {agent['tool_failure_signals']} 次。"
        ),
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


def _normalize_lines(text: str) -> list[str]:
    lines = []
    for raw in text.replace("\r", "\n").split("\n"):
        line = raw.strip(" -\t")
        if line:
            lines.append(line[:180])
    return lines


def _extract_trigger_phrases(lines: list[str]) -> list[str]:
    triggers = []
    keywords = [
        "当",
        "如果",
        "若",
        "客户",
        "招标",
        "投标",
        "合同",
        "审批",
        "跟进",
        "报价",
        "竞品",
    ]
    for line in lines:
        if any(keyword in line for keyword in keywords):
            triggers.append(line)
        if len(triggers) >= 5:
            break
    return triggers or lines[:3]


def _tools_for_sop(text: str) -> list[str]:
    tools = []
    mapping = [
        ("客户", "search_customers"),
        ("线索", "score_sales_lead"),
        ("跟进", "draft_followup"),
        ("拜访", "create_visit_note"),
        ("招标", "parse_tender_document"),
        ("投标", "score_tender_response"),
        ("竞品", "generate_battlecard"),
        ("合同", "query_contracts"),
        ("审批", "query_pending_approvals"),
        ("邮件", "draft_email"),
        ("周报", "generate_weekly_report"),
    ]
    for keyword, tool in mapping:
        if keyword in text and tool not in tools:
            tools.append(tool)
    return tools or ["answer_with_context", "create_followup_task"]


def _generate_agent_definition(payload: AgentDefinitionRequest) -> dict[str, Any]:
    lines = _normalize_lines(payload.sop_text)
    triggers = _extract_trigger_phrases(lines)
    tools = _tools_for_sop(payload.sop_text)
    high_risk_terms = [
        "付款",
        "打款",
        "删除",
        "外发",
        "批量",
        "批准",
        "驳回",
        "合同金额",
    ]
    guardrails = [
        "所有付款、删除、批量外发、审批结论和合同金额变更必须进入人工确认。",
        "回答必须引用客户、项目、合同、审批或文档证据；证据不足时只生成待确认草稿。",
        "不得伪造客户关系、采购预算、竞品参数或招投标评分。",
    ]
    if any(term in payload.sop_text for term in high_risk_terms):
        guardrails.insert(0, "该 SOP 含高风险动作，默认启用 HITL 确认门。")

    procedure = []
    for index, line in enumerate(lines[:6], start=1):
        procedure.append(
            {
                "step": index,
                "name": f"步骤 {index}",
                "instruction": line,
                "expected_evidence": "客户/项目/合同/文档/行动事件",
            }
        )

    intent_rules = [
        {
            "name": f"{payload.scenario} 规则 {index}",
            "trigger": trigger,
            "tools": tools[:4],
            "autonomy": payload.autonomy_level,
        }
        for index, trigger in enumerate(triggers[:4], start=1)
    ]
    test_cases = [
        f"用户说：{trigger}。验证 Agent 是否按 SOP 调用 {tools[0]} 并输出证据链。"
        for trigger in triggers[:3]
    ]
    confidence = min(0.92, max(0.55, 0.58 + len(lines) * 0.03 + len(tools) * 0.02))
    definition_markdown = "\n".join(
        [
            f"# {payload.scenario} Agent Operating Procedure",
            "## 触发规则",
            *[f"- {rule['trigger']}" for rule in intent_rules],
            "## 工具链",
            f"- {' -> '.join(tools)}",
            "## 护栏",
            *[f"- {item}" for item in guardrails],
        ]
    )
    return {
        "scenario": payload.scenario,
        "autonomy_level": payload.autonomy_level,
        "intent_rules": intent_rules,
        "operating_procedure": procedure,
        "tools": tools,
        "guardrails": guardrails,
        "test_cases": test_cases,
        "confidence": round(confidence, 2),
        "next_steps": [
            "放入 Agent 仿真沙盒跑历史消息回放。",
            "把高风险动作绑定 HITL 确认门。",
            "灰度给 1 个销售小组并观察采纳率、失败率和人工否决原因。",
        ],
        "definition_markdown": definition_markdown,
    }


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
    agent = _agent_summary(runs)
    actions = _action_summary(events)

    return api_success(
        data={
            "window_days": days,
            "agent": agent,
            "actions": actions,
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
                "agent_success_rate": agent["success_rate"],
                "action_completion_rate": actions["completion_rate"],
                "context_graph_nodes": graph["summary"]["node_count"],
                "context_graph_edges": graph["summary"]["edge_count"],
            },
            "value": _value_summary(agent, actions, events),
            "trust": _trust_summary(agent, actions),
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


@router.post("/define-agent")
async def define_agent_from_sop(
    payload: AgentDefinitionRequest,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    definition = _generate_agent_definition(payload)
    definition["created_by"] = user_id
    definition["organization_id"] = org_id
    return api_success(data=definition)


@router.get("/prompt-registry")
async def list_prompt_registry(
    _user_id: str = Depends(get_current_user_id),
    _org_id: str = Depends(get_current_org_id),
):
    from app.services.prompt_registry import prompt_registry

    return api_success(data={"manifests": prompt_registry.list_manifests()})


@router.post("/agent-ci")
async def run_agent_ci(
    payload: AgentCIRequest,
    _user_id: str = Depends(get_current_user_id),
    _org_id: str = Depends(get_current_org_id),
):
    from app.services.agent_ci_service import agent_ci_service

    return api_success(
        data=agent_ci_service.run_static_ci(
            cases=payload.cases or None,
            candidate_metadata=payload.candidate_metadata,
        )
    )


@router.get("/improvement-proposals")
async def get_agent_improvement_proposals(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    db = _db(request)
    runs = await _safe_select(
        db,
        "agent_runs",
        "id, run_id, status, input_summary, error, error_message, metadata, updated_at",
        order_by="updated_at",
        limit=80,
    )
    graph = await build_business_context_graph(db, org_id=org_id, user_id=user_id)
    from app.services.agent_improvement_service import agent_improvement_service
    from app.services.context_quality import context_quality_service
    from app.services.prompt_registry import prompt_registry

    context_pack = context_quality_service.build_evidence_pack(
        {
            "entries": [
                {
                    "included": True,
                    "quality_score": 0.9 if graph["summary"]["node_count"] else 0.45,
                    "evidence_ids": [node["id"] for node in graph["nodes"][:8]],
                    "permission_scope": "tenant_scoped",
                    "conflict_flag": False,
                }
            ]
        }
    )
    manifest = prompt_registry.get_manifest("director_agent").to_dict()
    return api_success(
        data=agent_improvement_service.generate_proposals(
            runs=runs,
            prompt_manifest=manifest,
            context_pack=context_pack,
        )
    )


@router.get("/memory-hygiene")
async def get_memory_hygiene(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    from app.services.memory_hygiene_service import memory_hygiene_service

    return api_success(
        data=await memory_hygiene_service.audit_memory_hygiene(
            db=_db(request),
            user_id=user_id,
            org_id=org_id,
        )
    )


@router.get("/evolution-ops")
async def get_agent_evolution_ops(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    db = _db(request)
    runs = await _safe_select(
        db,
        "agent_runs",
        "id, run_id, status, input_summary, error, error_message, metadata, updated_at",
        order_by="updated_at",
        limit=120,
    )
    events = await _safe_select(
        db,
        "action_events",
        "id, action_id, source, source_id, event_type, status, user_id, metadata, created_at",
        order_by="created_at",
        limit=200,
    )
    persisted_proposals = await _safe_select(
        db,
        "agent_improvement_proposals",
        "id, proposal_key, category, title, rationale, proposed_patch, risk_level, "
        "status, gray_percentage, ci_result, created_at, updated_at",
        order_by="updated_at",
        limit=40,
    )
    redteam_findings = await _safe_select(
        db,
        "agent_redteam_findings",
        "id, scenario_key, attack_type, severity, status, finding, created_at",
        order_by="created_at",
        limit=40,
    )
    graph = await build_business_context_graph(db, org_id=org_id, user_id=user_id)

    from app.services.agent_ci_service import agent_ci_service
    from app.services.agent_evolution_ops_service import (
        AGENT_EVOLUTION_TABLES,
        agent_evolution_ops_service,
    )
    from app.services.agent_improvement_service import agent_improvement_service
    from app.services.context_quality import context_quality_service
    from app.services.prompt_registry import prompt_registry

    context_pack = context_quality_service.build_evidence_pack(
        {
            "entries": [
                {
                    "included": True,
                    "quality_score": 0.9 if graph["summary"]["node_count"] else 0.45,
                    "evidence_ids": [node["id"] for node in graph["nodes"][:8]],
                    "permission_scope": "tenant_scoped",
                    "conflict_flag": False,
                }
            ]
        }
    )
    manifest = prompt_registry.get_manifest("director_agent").to_dict()
    generated = agent_improvement_service.generate_proposals(
        runs=runs,
        prompt_manifest=manifest,
        context_pack=context_pack,
    )
    proposals = persisted_proposals or generated["proposals"]
    agent_ci = agent_ci_service.run_static_ci(
        candidate_metadata={"source": "evolution_ops_dashboard"}
    )
    persisted_counts = {
        table: await _safe_count(db, table) for table in AGENT_EVOLUTION_TABLES
    }
    return api_success(
        data=agent_evolution_ops_service.build_dashboard(
            runs=runs,
            events=events,
            proposals=proposals,
            prompt_manifest=manifest,
            context_pack=context_pack,
            agent_ci=agent_ci,
            redteam_findings=redteam_findings,
            persisted_counts=persisted_counts,
        )
    )


@router.get("/aeon-inspired-ops")
async def get_aeon_inspired_agent_ops(
    request: Request,
    focus_var: str = Query("scientific instrument sales", max_length=160),
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    db = _db(request)
    runs = await _safe_select(
        db,
        "agent_runs",
        "id, run_id, agent, agent_role, tool_name, status, input_summary, error, "
        "error_message, metadata, updated_at",
        order_by="updated_at",
        limit=160,
    )
    events = await _safe_select(
        db,
        "action_events",
        "id, action_id, source, source_id, event_type, status, user_id, metadata, created_at",
        order_by="created_at",
        limit=240,
    )
    proposals = await _safe_select(
        db,
        "agent_improvement_proposals",
        "id, proposal_key, category, title, status, risk_level, updated_at",
        order_by="updated_at",
        limit=40,
    )
    from app.services.agent_ops_runtime_service import agent_ops_runtime_service

    payload = agent_ops_runtime_service.build_dashboard(
        runs=runs,
        events=events,
        proposals=proposals,
        focus_var=focus_var,
    )
    payload["requested_by"] = user_id
    payload["organization_id"] = org_id
    return api_success(data=payload)


@router.post("/aeon-inspired-ops/run-heartbeat")
async def run_aeon_inspired_heartbeat(
    request: Request,
    focus_var: str = Query("scientific instrument sales", max_length=160),
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """Run and persist one governed Agent Ops heartbeat snapshot."""
    db = _db(request)
    runs = await _safe_select(
        db,
        "agent_runs",
        "id, run_id, agent, agent_role, tool_name, status, input_summary, error, "
        "error_message, metadata, updated_at",
        order_by="updated_at",
        limit=160,
    )
    events = await _safe_select(
        db,
        "action_events",
        "id, action_id, source, source_id, event_type, status, user_id, metadata, created_at",
        order_by="created_at",
        limit=240,
    )
    proposals = await _safe_select(
        db,
        "agent_improvement_proposals",
        "id, proposal_key, category, title, status, risk_level, updated_at",
        order_by="updated_at",
        limit=40,
    )
    from app.services.agent_ops_runtime_service import agent_ops_runtime_service

    payload = agent_ops_runtime_service.build_dashboard(
        runs=runs,
        events=events,
        proposals=proposals,
        focus_var=focus_var,
    )
    payload["requested_by"] = user_id
    payload["organization_id"] = org_id
    try:
        payload["persistence"] = await agent_ops_runtime_service.persist_dashboard(
            db=db,
            organization_id=org_id,
            payload=payload,
        )
    except Exception as exc:
        payload["persistence"] = {
            "mode": "safe_fallback_not_saved",
            "reason": str(exc)[:240],
        }
    return api_success(data=payload)


@router.post("/aeon-inspired-ops/register-heartbeat-schedule")
async def register_aeon_heartbeat_schedule(
    request: Request,
    focus_var: str = Query("scientific instrument sales", max_length=160),
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    """Register a daily governed Agent Ops heartbeat with the scheduler."""
    db = _db(request)
    from app.services.agent_ops_runtime_service import agent_ops_runtime_service

    try:
        schedule = await agent_ops_runtime_service.register_heartbeat_schedule(
            db=db,
            organization_id=org_id,
            user_id=user_id,
            focus_var=focus_var,
        )
    except Exception as exc:
        schedule = {
            "mode": "safe_fallback_not_registered",
            "reason": str(exc)[:240],
        }
    return api_success(data=schedule)


@router.post("/proposals/{proposal_key}/decision")
async def decide_agent_improvement_proposal(
    proposal_key: str,
    payload: AgentProposalDecisionRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
    org_id: str = Depends(get_current_org_id),
):
    from app.services.agent_evolution_ops_service import agent_evolution_ops_service

    result = agent_evolution_ops_service.build_decision_result(
        proposal_key=proposal_key,
        action=payload.action,
        reviewer_id=user_id,
        gray_percentage=payload.gray_percentage,
    )
    db = _db(request)
    try:
        await (
            db.table("agent_improvement_proposals")
            .upsert(
                {
                    "organization_id": org_id,
                    "proposal_key": proposal_key,
                    "category": "operator_decision",
                    "title": f"Decision for {proposal_key}",
                    "rationale": payload.reviewer_note,
                    "proposed_patch": {},
                    "risk_level": "medium",
                    "status": result["status"],
                    "gray_percentage": result["gray_percentage"],
                    "decided_by": user_id,
                    "decided_at": result["decided_at"],
                    "updated_at": result["decided_at"],
                },
                on_conflict="organization_id,proposal_key",
            )
            .execute()
        )
        result["persistence"] = "saved"
    except Exception:
        result["persistence"] = "safe_fallback_not_saved"
    return api_success(data=result)
