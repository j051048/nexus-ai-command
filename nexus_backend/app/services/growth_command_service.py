"""Growth command center aggregation and extension contracts.

The growth command API is deliberately read-model oriented. It composes the
existing CRM, VMD, tender, and action-event stores into one stable contract
without moving ownership away from those domains. New signal sources and
playbooks can be registered without changing the workspace response shape.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

logger = logging.getLogger(__name__)

GROWTH_COMMAND_SCHEMA_VERSION = "growth-command.v1"

Priority = Literal["urgent", "high", "medium", "low"]


@dataclass(frozen=True)
class GrowthCapability:
    key: str
    name: str
    category: Literal["signal", "action", "knowledge", "connector"]
    status: Literal["ready", "configurable", "planned"]
    risk_level: Literal["low", "medium", "high"] = "low"
    requires_confirmation: bool = False
    contract_version: str = "v1"


class GrowthCapabilityProvider(Protocol):
    """Extension point for future industry feeds and action executors."""

    def capabilities(self) -> list[GrowthCapability]: ...


class GrowthCapabilityRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, GrowthCapabilityProvider] = {}

    def register(self, key: str, provider: GrowthCapabilityProvider) -> None:
        if key in self._providers:
            raise ValueError(f"growth capability provider already registered: {key}")
        self._providers[key] = provider

    def manifest(self) -> list[dict[str, Any]]:
        capabilities: list[GrowthCapability] = []
        for provider in self._providers.values():
            capabilities.extend(provider.capabilities())
        return [asdict(item) for item in capabilities]


class CoreGrowthProvider:
    def capabilities(self) -> list[GrowthCapability]:
        return [
            GrowthCapability("crm.accounts", "客户与项目", "signal", "ready"),
            GrowthCapability("vmd.clues", "行业线索", "signal", "ready"),
            GrowthCapability("tender.projects", "投标机会", "signal", "ready"),
            GrowthCapability(
                "vmd.playbooks", "增长任务编排", "action", "ready", "medium", True
            ),
            GrowthCapability(
                "industry.knowledge", "科学仪器知识", "knowledge", "ready"
            ),
            GrowthCapability(
                "connector.public-tender",
                "公开招投标数据源",
                "connector",
                "configurable",
            ),
            GrowthCapability(
                "connector.research-grants",
                "科研基金与论文数据源",
                "connector",
                "planned",
            ),
        ]


growth_capability_registry = GrowthCapabilityRegistry()
growth_capability_registry.register("core", CoreGrowthProvider())


INDUSTRY_PLAYBOOKS: list[dict[str, Any]] = [
    {
        "key": "instrument-new-opportunity",
        "name": "科研商机发现与核验",
        "category": "lead_generation",
        "outcome": "形成可分配、可追溯的有效商机",
        "agents": ["clue", "sales", "compliance"],
        "acceptance": ["来源可追溯", "客户与预算线索明确", "下一步责任人已指定"],
        "risk_policy": "recommend",
    },
    {
        "key": "instrument-account-plan",
        "name": "重点客户推进计划",
        "category": "account_growth",
        "outcome": "明确决策链、应用场景与下一次有效触达",
        "agents": ["sales", "content", "director"],
        "acceptance": ["决策角色完整", "关键异议有证据", "跟进动作可执行"],
        "risk_policy": "confirm_before_external_action",
    },
    {
        "key": "instrument-tender-readiness",
        "name": "投标胜率提升",
        "category": "tender",
        "outcome": "在截止日前暴露资格、技术和商务缺口",
        "agents": ["tender", "compliance", "content", "director"],
        "acceptance": ["评分项逐条映射", "缺口有负责人", "最终提交由人工确认"],
        "risk_policy": "human_approval_required",
    },
    {
        "key": "instrument-launch",
        "name": "新品上市作战",
        "category": "launch",
        "outcome": "从应用场景到首批目标客户形成上市闭环",
        "agents": ["clue", "content", "sales", "operation", "director"],
        "acceptance": ["目标细分明确", "证据素材齐备", "渠道动作有量化目标"],
        "risk_policy": "confirm_before_external_action",
    },
]


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def _days_since(value: Any, now: datetime) -> int | None:
    parsed = _parse_datetime(value)
    return max(0, (now - parsed).days) if parsed else None


def _money(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _priority_rank(value: str) -> int:
    return {"urgent": 0, "high": 1, "medium": 2, "low": 3}.get(value, 2)


def _clue_signal(row: dict[str, Any]) -> dict[str, Any]:
    priority = str(row.get("priority") or "medium")
    return {
        "id": f"clue:{row.get('id')}",
        "kind": "market_signal",
        "priority": (
            priority if priority in {"urgent", "high", "medium", "low"} else "medium"
        ),
        "title": row.get("title") or row.get("clue_code") or "待核验行业线索",
        "summary": (row.get("content") or "需要补充需求、预算与采购时间证据")[:180],
        "source": row.get("source") or "manual",
        "source_label": "行业线索",
        "evidence": [
            value
            for value in [row.get("industry"), row.get("region"), row.get("source_url")]
            if value
        ],
        "occurred_at": row.get("update_time") or row.get("create_time"),
        "target_url": f"/vmd/clues?detail={row.get('id')}",
        "estimated_value": _money(row.get("estimated_value")),
    }


def _customer_item(row: dict[str, Any], now: datetime) -> dict[str, Any]:
    inactive_days = _days_since(row.get("updated_at") or row.get("created_at"), now)
    stage = str(row.get("stage") or "lead")
    risk = (
        "high"
        if inactive_days is not None and inactive_days >= 30
        else "medium" if inactive_days is not None and inactive_days >= 14 else "low"
    )
    next_action = {
        "lead": "确认应用场景与联系人",
        "prospect": "补齐预算和采购周期",
        "opportunity": "推进技术验证或方案评审",
        "customer": "复盘交付并识别扩购机会",
        "churned": "记录流失原因并进入培育",
    }.get(stage, "更新客户下一步")
    return {
        "id": str(row.get("id") or ""),
        "name": row.get("company") or row.get("name") or "未命名客户",
        "contact_name": row.get("name"),
        "industry": row.get("industry"),
        "stage": stage,
        "estimated_value": _money(row.get("estimated_value")),
        "inactive_days": inactive_days,
        "risk": risk,
        "next_action": next_action,
        "updated_at": row.get("updated_at") or row.get("created_at"),
        "target_url": f"/crm?customer={row.get('id')}",
    }


def _tender_item(row: dict[str, Any], now: datetime) -> dict[str, Any]:
    deadline = row.get("deadline") or row.get("bid_deadline")
    parsed_deadline = _parse_datetime(deadline)
    days_left = (parsed_deadline - now).days if parsed_deadline else None
    compliance = row.get("compliance_status") or "unchecked"
    risk = (
        "high"
        if (days_left is not None and days_left <= 3) or compliance == "has_issues"
        else "medium" if days_left is not None and days_left <= 10 else "low"
    )
    return {
        "id": str(row.get("id") or ""),
        "name": row.get("title") or row.get("project_name") or "未命名投标项目",
        "client_name": row.get("buyer_name") or row.get("client_name"),
        "deadline": deadline,
        "days_left": days_left,
        "estimated_value": _money(row.get("estimated_value")),
        "status": row.get("status") or "preparation",
        "compliance_status": compliance,
        "win_probability": int(row.get("win_probability") or 0),
        "risk": risk,
        "target_url": "/tender-analysis",
    }


def compose_growth_workspace(
    *,
    clues: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    tenders: list[dict[str, Any]],
    action_events: list[dict[str, Any]],
    growth_outcomes: list[dict[str, Any]] | None = None,
    source_health: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Pure projection used by the API and regression tests."""

    current = now or datetime.now(UTC)
    outcome_rows = growth_outcomes or []
    open_clues = [
        row for row in clues if row.get("status") not in {"converted", "lost"}
    ]
    account_items = [_customer_item(row, current) for row in customers]
    tender_items = [_tender_item(row, current) for row in tenders]
    signals = [_clue_signal(row) for row in open_clues]

    for account in account_items:
        if account["risk"] == "high":
            signals.append(
                {
                    "id": f"account:{account['id']}",
                    "kind": "account_risk",
                    "priority": "high",
                    "title": f"{account['name']} 已 {account['inactive_days']} 天未更新",
                    "summary": account["next_action"],
                    "source": "crm",
                    "source_label": "客户风险",
                    "evidence": [
                        f"阶段：{account['stage']}",
                        f"停滞：{account['inactive_days']} 天",
                    ],
                    "occurred_at": account["updated_at"],
                    "target_url": account["target_url"],
                    "estimated_value": account["estimated_value"],
                }
            )

    for tender in tender_items:
        if tender["risk"] in {"high", "medium"}:
            signals.append(
                {
                    "id": f"tender:{tender['id']}",
                    "kind": "tender_risk",
                    "priority": "urgent" if tender["risk"] == "high" else "high",
                    "title": tender["name"],
                    "summary": "优先核对资格、技术响应和商务缺口",
                    "source": "tender",
                    "source_label": "投标节点",
                    "evidence": [
                        (
                            f"剩余：{tender['days_left']} 天"
                            if tender["days_left"] is not None
                            else "截止时间待确认"
                        ),
                        f"合规：{tender['compliance_status']}",
                    ],
                    "occurred_at": tender["deadline"],
                    "target_url": tender["target_url"],
                    "estimated_value": tender["estimated_value"],
                }
            )

    signals.sort(
        key=lambda item: (
            _priority_rank(item["priority"]),
            -_money(item.get("estimated_value")),
        )
    )
    actions = [
        {
            "id": f"next:{signal['id']}",
            "priority": signal["priority"],
            "title": signal["title"],
            "recommendation": signal["summary"],
            "reason": f"{signal['source_label']} · {len(signal['evidence'])} 条可核验证据",
            "confidence": "high" if len(signal["evidence"]) >= 2 else "medium",
            "execution_mode": (
                "confirm" if signal["kind"] == "tender_risk" else "recommend"
            ),
            "target_url": signal["target_url"],
            "source_signal_id": signal["id"],
        }
        for signal in signals[:8]
    ]

    open_tasks = [
        row
        for row in tasks
        if row.get("status") not in {"completed", "done", "cancelled"}
    ]
    completed_tasks = [
        row for row in tasks if row.get("status") in {"completed", "done"}
    ]
    completed_events = [
        row for row in action_events if row.get("event_type") == "completed"
    ]
    accepted_events = [
        row
        for row in action_events
        if row.get("event_type") in {"accepted", "completed"}
    ]
    acted_events = [
        row
        for row in action_events
        if row.get("event_type") in {"accepted", "completed", "ignored"}
    ]
    conversion_count = len([row for row in clues if row.get("status") == "converted"])
    active_tenders = [
        row for row in tender_items if row["status"] not in {"won", "lost", "cancelled"}
    ]

    metrics = {
        "open_opportunities": len(open_clues),
        "pipeline_value": round(
            sum(_money(row.get("estimated_value")) for row in open_clues)
            + sum(
                item["estimated_value"]
                for item in account_items
                if item["stage"] == "opportunity"
            ),
            2,
        ),
        "high_priority_signals": len(
            [item for item in signals if item["priority"] in {"urgent", "high"}]
        ),
        "active_tasks": len(open_tasks),
        "active_tenders": len(active_tenders),
        "conversion_rate": (
            round(conversion_count / len(clues) * 100, 1) if clues else 0.0
        ),
    }
    review = {
        "completed_growth_tasks": len(completed_tasks),
        "accepted_actions": len(accepted_events),
        "completed_actions": len(completed_events),
        "action_adoption_rate": (
            round(len(accepted_events) / len(acted_events) * 100, 1)
            if acted_events
            else 0.0
        ),
        "estimated_hours_saved": round(
            len(completed_tasks) * 3.5 + len(completed_events) * 0.25, 1
        ),
        "qualified_leads": len(
            [row for row in outcome_rows if row.get("outcome_type") == "qualified_lead"]
        ),
        "wins": len([row for row in outcome_rows if row.get("outcome_type") == "won"]),
        "attributed_revenue": round(
            sum(
                _money(row.get("amount"))
                for row in outcome_rows
                if row.get("outcome_type") == "revenue"
            ),
            2,
        ),
        "outcome_evidence_count": len(
            [row for row in outcome_rows if row.get("evidence_ref")]
        ),
        "evidence_note": "节省时间为运营基线估算；成交与收入数据仅使用业务系统真实记录。",
    }
    context_graph = {
        "nodes": len(clues) + len(customers) + len(tenders) + len(tasks),
        "links": len([row for row in clues if row.get("customer_id")])
        + len(
            [row for row in tenders if row.get("client_name") or row.get("buyer_name")]
        ),
        "entity_types": ["clue", "account", "project", "tender", "action"],
    }
    return {
        "schema_version": GROWTH_COMMAND_SCHEMA_VERSION,
        "generated_at": current.isoformat(),
        "metrics": metrics,
        "actions": actions,
        "signals": signals[:50],
        "accounts": sorted(
            account_items,
            key=lambda item: (_priority_rank(item["risk"]), -item["estimated_value"]),
        )[:50],
        "tenders": sorted(
            tender_items,
            key=lambda item: (item["days_left"] is None, item["days_left"] or 9999),
        )[:50],
        "review": review,
        "context_graph": context_graph,
        "playbooks": INDUSTRY_PLAYBOOKS,
        "capabilities": growth_capability_registry.manifest(),
        "source_health": source_health or {},
        "sandbox": {
            "enabled": False,
            "data_isolation": "workspace",
            "production_data_mixed": False,
        },
    }


class GrowthCommandService:
    _SOURCES = {
        "clues": ("business_clue", "*", "create_time"),
        "tasks": ("vmd_main_task", "*", "create_time"),
        "customers": ("customers", "*", "updated_at"),
        "tenders": ("bid_project", "*", "create_time"),
        "action_events": ("action_events", "*", "created_at"),
        "growth_outcomes": ("growth_outcome_events", "*", "occurred_at"),
    }

    async def _load_source(
        self, db: Any, table: str, columns: str, order_by: str
    ) -> tuple[list[dict[str, Any]], str]:
        try:
            query = (
                db.table(table).select(columns).order(order_by, desc=True).limit(200)
            )
            result = await query.execute()
            return list(result.data or []), "ready"
        except Exception as exc:
            logger.warning(
                "Growth command source unavailable: table=%s error=%s", table, exc
            )
            return [], "degraded"

    async def get_workspace(self, db: Any) -> dict[str, Any]:
        source_names = list(self._SOURCES)
        results = await asyncio.gather(
            *(self._load_source(db, *self._SOURCES[name]) for name in source_names)
        )
        rows = {
            name: result[0] for name, result in zip(source_names, results, strict=True)
        }
        health = {
            name: result[1] for name, result in zip(source_names, results, strict=True)
        }
        return compose_growth_workspace(
            clues=rows["clues"],
            tasks=rows["tasks"],
            customers=rows["customers"],
            tenders=rows["tenders"],
            action_events=rows["action_events"],
            growth_outcomes=rows["growth_outcomes"],
            source_health=health,
        )


growth_command_service = GrowthCommandService()
