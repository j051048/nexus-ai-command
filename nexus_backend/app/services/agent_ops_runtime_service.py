"""Aeon-inspired Agent operations runtime.

The goal is not to copy Aeon, but to bring its strongest operating-system ideas
into Nexus: quiet heartbeats, skill health, reactive triggers, governed repair,
chainable skills, a universal focus variable, durable operating memory, agent
fleets, persona/soul packs, and externally exposed capabilities.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

AEON_AGENT_OPS_TABLES = [
    "agent_heartbeat_runs",
    "agent_skill_health",
    "agent_reactive_triggers",
    "agent_chain_runs",
    "agent_persona_profiles",
    "agent_external_capabilities",
]


DEFAULT_REACTIVE_TRIGGERS = [
    {
        "id": "repair-after-3-failures",
        "when": "skill.consecutive_failures >= 3",
        "run": "agent_repair_proposal",
        "autonomy": "proposal_only",
        "risk": "medium",
    },
    {
        "id": "crm-30-day-followup",
        "when": "customer.days_since_last_contact >= 30",
        "run": "crm_next_best_action_chain",
        "autonomy": "low_risk_auto",
        "risk": "low",
    },
    {
        "id": "contract-renewal-60-days",
        "when": "contract.days_to_expiry <= 60",
        "run": "renewal_risk_agent",
        "autonomy": "hitl_required",
        "risk": "high",
    },
    {
        "id": "approval-anomaly",
        "when": "approval.amount > historical_avg * 1.5",
        "run": "approval_risk_review_agent",
        "autonomy": "hitl_required",
        "risk": "high",
    },
]


DEFAULT_PERSONAS = [
    {
        "id": "boss_copilot",
        "role": "Boss Copilot",
        "style": "numbers_first, concise, risk_prioritized",
        "must_do": [
            "lead with business impact",
            "show confidence",
            "list unresolved risks",
        ],
    },
    {
        "id": "sales_copilot",
        "role": "Scientific Instrument Sales Copilot",
        "style": "action_oriented, relationship_aware, evidence_backed",
        "must_do": [
            "name next action",
            "cite customer context",
            "avoid invented budget",
        ],
    },
    {
        "id": "tender_copilot",
        "role": "Tender Copilot",
        "style": "precise, compliance_first, evidence_chain_required",
        "must_do": [
            "extract score criteria",
            "flag missing evidence",
            "separate facts from assumptions",
        ],
    },
]


EXTERNAL_CAPABILITIES = [
    {
        "name": "crm.followup",
        "description": "Create next-best-action suggestions for stale or high-value customers.",
        "protocols": ["mcp", "a2a", "rest"],
        "risk": "low",
    },
    {
        "name": "approval.risk_review",
        "description": "Review approval requests for anomaly and policy risk.",
        "protocols": ["mcp", "a2a", "rest"],
        "risk": "high",
    },
    {
        "name": "tender.score",
        "description": "Parse tender files and generate a score/risk matrix.",
        "protocols": ["mcp", "a2a", "rest"],
        "risk": "medium",
    },
    {
        "name": "dashboard.ai_weekly_report",
        "description": "Expose the customer-visible AI behavior weekly report.",
        "protocols": ["mcp", "rest"],
        "risk": "low",
    },
]


class AgentOpsRuntimeService:
    """Builds an Aeon-inspired operating payload from existing telemetry."""

    def _skill_key(self, run: dict[str, Any]) -> str:
        metadata = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
        return str(
            metadata.get("skill")
            or metadata.get("agent")
            or run.get("agent")
            or run.get("agent_role")
            or run.get("tool_name")
            or "general_agent"
        )

    def build_skill_health(self, runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for run in runs:
            grouped[self._skill_key(run)].append(run)
        if not grouped:
            grouped["general_agent"] = []

        health: list[dict[str, Any]] = []
        for skill, items in sorted(grouped.items()):
            recent = items[:30]
            failures = [
                item
                for item in recent
                if str(item.get("status") or "").lower()
                in {"failed", "error", "cancelled"}
                or item.get("error")
                or item.get("error_message")
            ]
            total = max(1, len(recent))
            success_rate = round((total - len(failures)) / total, 4)
            score = round(
                max(1.0, min(5.0, 1 + success_rate * 4 - min(len(failures), 3) * 0.25)),
                2,
            )
            flags = []
            if len(failures) >= 3:
                flags.append("consecutive_failures")
            if success_rate < 0.8:
                flags.append("low_success_rate")
            if any(
                "rate"
                in str(item.get("error") or item.get("error_message") or "").lower()
                for item in failures
            ):
                flags.append("rate_limited")
            if not flags:
                flags.append("healthy")
            health.append(
                {
                    "skill": skill,
                    "window": min(30, len(recent)),
                    "score": score,
                    "success_rate": success_rate,
                    "failure_count": len(failures),
                    "flags": flags,
                    "last_status": recent[0].get("status") if recent else "idle",
                    "recommended_action": (
                        "repair_proposal" if "low_success_rate" in flags else "monitor"
                    ),
                }
            )
        return health

    def build_heartbeat(self, health: list[dict[str, Any]]) -> dict[str, Any]:
        critical = [
            item for item in health if item["score"] < 3 or item["failure_count"] >= 3
        ]
        return {
            "status": "attention_required" if critical else "ok",
            "checked_at": datetime.now(UTC).isoformat(),
            "summary": (
                f"{len(critical)} skill(s) need attention."
                if critical
                else "HEARTBEAT_OK: no urgent Agent Ops issue found."
            ),
            "notify_operator": bool(critical),
            "attention_items": critical[:8],
        }

    def build_reactive_triggers(self, health: list[dict[str, Any]]) -> dict[str, Any]:
        fired = []
        for item in health:
            if item["failure_count"] >= 3 or item["score"] < 3:
                fired.append(
                    {
                        "trigger": "repair-after-3-failures",
                        "skill": item["skill"],
                        "reason": f"score={item['score']} failures={item['failure_count']}",
                        "next_action": "create_self_repair_proposal",
                    }
                )
        return {
            "trigger_count": len(DEFAULT_REACTIVE_TRIGGERS),
            "definitions": DEFAULT_REACTIVE_TRIGGERS,
            "fired": fired,
            "dsl": "when <business_or_skill_condition> run <agent_or_chain> autonomy <mode>",
        }

    def build_self_repair(self, health: list[dict[str, Any]]) -> dict[str, Any]:
        proposals = []
        for item in health:
            if item["recommended_action"] == "repair_proposal":
                proposals.append(
                    {
                        "id": f"repair-{item['skill']}",
                        "skill": item["skill"],
                        "diagnosis": item["flags"],
                        "proposed_patch": {
                            "prompt": "add stricter argument validation and evidence requirements",
                            "tool_policy": "retry only safe read tools; route high-risk failures to HITL",
                            "evals": ["add regression case from failed run"],
                        },
                        "release_mode": "human_approved_gray_release",
                        "auto_apply": False,
                    }
                )
        return {
            "mode": "diagnose_and_propose_only",
            "auto_apply": False,
            "proposal_count": len(proposals),
            "proposals": proposals,
        }

    def build_skill_chains(self, focus_var: str) -> dict[str, Any]:
        chains = [
            {
                "id": "crm_risk_daily_chain",
                "var": focus_var,
                "steps": [
                    "scan_stale_customers",
                    "score_customer_health",
                    "draft_next_best_action",
                    "write_inbox_item",
                ],
                "output_contract": "action_items + evidence_ids + owner + due_date",
            },
            {
                "id": "tender_response_chain",
                "var": focus_var,
                "steps": [
                    "parse_tender",
                    "build_score_matrix",
                    "generate_battlecard",
                    "compliance_review",
                    "boss_summary",
                ],
                "output_contract": "score_matrix + risk_flags + response_outline",
            },
            {
                "id": "ai_weekly_report_chain",
                "var": focus_var,
                "steps": [
                    "collect_agent_health",
                    "collect_roi",
                    "collect_redteam",
                    "summarize_business_value",
                ],
                "output_contract": "weekly_report + trust_summary + next_actions",
            },
        ]
        return {"chain_count": len(chains), "chains": chains}

    def build_universal_var(self, focus_var: str) -> dict[str, Any]:
        return {
            "name": "var",
            "value": focus_var,
            "description": "A universal business focus parameter interpreted by each skill.",
            "examples": [
                "华东区高校客户",
                "Thermo Fisher 竞品线索",
                "预算 500 万以上招标",
                "科学仪器展会线索",
            ],
            "routing_hint": f"Bias retrieval, scoring, and chain outputs toward: {focus_var}",
        }

    def build_operating_memory(
        self, runs: list[dict[str, Any]], events: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return {
            "stores": [
                "agent_run_state",
                "agent_skill_health",
                "agent_chain_outputs",
                "agent_repair_issues",
                "agent_cost_ledger",
                "agent_daily_logs",
            ],
            "run_count": len(runs),
            "event_count": len(events),
            "retention_policy": "last_30_runs_for_health, full_audit_for_trust_reports",
            "memory_promotion_rule": "promote only high-quality, cited, tenant-scoped outcomes",
        }

    def build_instance_fleet(self, health: list[dict[str, Any]]) -> dict[str, Any]:
        fleet = [
            {
                "id": "vmd_scientific_sales",
                "mission": "industry marketing and lead nurturing",
                "budget": "medium",
                "risk": "low",
            },
            {
                "id": "tender_support",
                "mission": "tender scoring and compliance",
                "budget": "high",
                "risk": "medium",
            },
            {
                "id": "renewal_risk",
                "mission": "contract renewal and churn prevention",
                "budget": "medium",
                "risk": "high",
            },
            {
                "id": "boss_weekly_report",
                "mission": "AI behavior and value reporting",
                "budget": "low",
                "risk": "low",
            },
        ]
        health_by_skill = {item["skill"]: item for item in health}
        return {
            "instances": [
                {
                    **item,
                    "health": health_by_skill.get(
                        item["id"], {"score": 4.2, "flags": ["synthetic_baseline"]}
                    ),
                    "permissions": "tenant_scoped, HITL for high-risk side effects",
                }
                for item in fleet
            ],
            "fleet_control": "pause, resume, budget_cap, gray_release, rollback",
        }

    def build_persona_soul(self) -> dict[str, Any]:
        return {
            "profiles": DEFAULT_PERSONAS,
            "style_contract": "SOUL.md + STYLE.md + golden_examples per role",
            "guardrail": "persona changes affect tone only, never permission or factual policy",
        }

    def build_external_capabilities(self) -> dict[str, Any]:
        return {
            "gateway": "mcp_and_a2a_ready",
            "capabilities": EXTERNAL_CAPABILITIES,
            "auth_boundary": "JWT + org scope + tool RBAC + HITL for high-risk operations",
        }

    def build_dashboard(
        self,
        *,
        runs: list[dict[str, Any]],
        events: list[dict[str, Any]],
        proposals: list[dict[str, Any]],
        focus_var: str,
    ) -> dict[str, Any]:
        health = self.build_skill_health(runs)
        heartbeat = self.build_heartbeat(health)
        reactive_triggers = self.build_reactive_triggers(health)
        self_repair = self.build_self_repair(health)
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "inspiration": "aeon-style unattended Agent Ops adapted for enterprise SaaS governance",
            "tables": AEON_AGENT_OPS_TABLES,
            "heartbeat": heartbeat,
            "skill_health": health,
            "reactive_triggers": reactive_triggers,
            "self_repair": self_repair,
            "skill_chains": self.build_skill_chains(focus_var),
            "universal_var": self.build_universal_var(focus_var),
            "operating_memory": self.build_operating_memory(runs, events),
            "instance_fleet": self.build_instance_fleet(health),
            "persona_soul": self.build_persona_soul(),
            "external_capabilities": self.build_external_capabilities(),
            "governance": {
                "proposal_count": len(proposals),
                "self_mutation_allowed": False,
                "required_release_flow": [
                    "simulate",
                    "agent_ci",
                    "redteam",
                    "human_approval",
                    "gray_release",
                    "rollback_ready",
                ],
            },
        }

    async def persist_dashboard(
        self,
        *,
        db: Any,
        organization_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist one Agent Ops heartbeat snapshot.

        This intentionally writes only operating facts and proposed actions.
        It never applies self-repair patches or runs high-risk side effects.
        """
        persisted = {
            "heartbeat": False,
            "skill_health": 0,
            "reactive_triggers": 0,
            "repair_proposals": 0,
            "trigger_actions": 0,
            "chain_templates": 0,
            "persona_profiles": 0,
            "external_capabilities": 0,
        }

        heartbeat = payload.get("heartbeat") or {}
        await (
            db.table("agent_heartbeat_runs")
            .insert(
                {
                    "organization_id": organization_id,
                    "status": heartbeat.get("status", "unknown"),
                    "summary": heartbeat.get("summary"),
                    "attention_items": heartbeat.get("attention_items", []),
                }
            )
            .execute()
        )
        persisted["heartbeat"] = True

        for item in payload.get("skill_health") or []:
            await (
                db.table("agent_skill_health")
                .upsert(
                    {
                        "organization_id": organization_id,
                        "skill_key": item["skill"],
                        "score": item["score"],
                        "success_rate": item["success_rate"],
                        "failure_count": item["failure_count"],
                        "flags": item["flags"],
                        "last_status": item.get("last_status"),
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    on_conflict="organization_id,skill_key",
                )
                .execute()
            )
            persisted["skill_health"] += 1

        for item in (payload.get("reactive_triggers") or {}).get("definitions", []):
            await (
                db.table("agent_reactive_triggers")
                .upsert(
                    {
                        "organization_id": organization_id,
                        "trigger_key": item["id"],
                        "condition_expr": item["when"],
                        "run_target": item["run"],
                        "autonomy": item["autonomy"],
                        "risk": item["risk"],
                        "enabled": True,
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    on_conflict="organization_id,trigger_key",
                )
                .execute()
            )
            persisted["reactive_triggers"] += 1

        for item in (payload.get("reactive_triggers") or {}).get("fired", []):
            trigger_key = str(item.get("trigger") or "agent-ops-trigger")
            skill_key = str(item.get("skill") or "general_agent")
            action_id = f"agent-ops:{trigger_key}:{skill_key}"
            await (
                db.table("action_events")
                .insert(
                    {
                        "organization_id": organization_id,
                        "action_id": action_id,
                        "source": "system",
                        "source_id": trigger_key,
                        "event_type": "accepted",
                        "status": "open",
                        "comment": "Reactive Agent Ops trigger created an operator action.",
                        "metadata": {
                            "type": "agent_ops_reactive_trigger",
                            "trigger": trigger_key,
                            "skill": skill_key,
                            "reason": item.get("reason"),
                            "next_action": item.get("next_action"),
                            "priority": "high",
                            "action_url": "/agent-improvement",
                            "requires_human_review": True,
                        },
                    }
                )
                .execute()
            )
            persisted["trigger_actions"] += 1

        for proposal in (payload.get("self_repair") or {}).get("proposals", []):
            await (
                db.table("agent_improvement_proposals")
                .upsert(
                    {
                        "organization_id": organization_id,
                        "proposal_key": proposal["id"],
                        "category": "self_repair",
                        "title": f"Repair proposal for {proposal['skill']}",
                        "rationale": ", ".join(proposal.get("diagnosis") or []),
                        "proposed_patch": proposal.get("proposed_patch") or {},
                        "risk_level": "medium",
                        "approval_required": True,
                        "status": "proposed",
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    on_conflict="organization_id,proposal_key",
                )
                .execute()
            )
            persisted["repair_proposals"] += 1

        for chain in (payload.get("skill_chains") or {}).get("chains", []):
            await (
                db.table("agent_chain_runs")
                .insert(
                    {
                        "organization_id": organization_id,
                        "chain_key": chain["id"],
                        "focus_var": chain.get("var"),
                        "status": "template_registered",
                        "steps": chain.get("steps") or [],
                        "output_contract": chain.get("output_contract"),
                        "outputs": {},
                    }
                )
                .execute()
            )
            persisted["chain_templates"] += 1

        for persona in (payload.get("persona_soul") or {}).get("profiles", []):
            await (
                db.table("agent_persona_profiles")
                .upsert(
                    {
                        "organization_id": organization_id,
                        "persona_key": persona["id"],
                        "role_name": persona["role"],
                        "style_contract": persona["style"],
                        "must_do": persona.get("must_do") or [],
                        "enabled": True,
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    on_conflict="organization_id,persona_key",
                )
                .execute()
            )
            persisted["persona_profiles"] += 1

        for capability in (payload.get("external_capabilities") or {}).get(
            "capabilities", []
        ):
            await (
                db.table("agent_external_capabilities")
                .upsert(
                    {
                        "organization_id": organization_id,
                        "capability_key": capability["name"],
                        "description": capability["description"],
                        "protocols": capability.get("protocols") or [],
                        "risk": capability.get("risk") or "low",
                        "enabled": True,
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    on_conflict="organization_id,capability_key",
                )
                .execute()
            )
            persisted["external_capabilities"] += 1

        return persisted

    def _next_daily_utc(self, utc_hour: int = 1, minute: int = 0) -> str:
        now = datetime.now(UTC)
        target = now.replace(hour=utc_hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return target.isoformat()

    async def register_heartbeat_schedule(
        self,
        *,
        db: Any,
        organization_id: str,
        user_id: str,
        focus_var: str,
    ) -> dict[str, Any]:
        """Register the daily Agent Ops heartbeat in the existing scheduler.

        The scheduler executes user_scheduled_tasks through the proactive agent.
        This prompt is intentionally low-risk: it asks the agent to inspect,
        summarize, and create proposals/actions, never to apply repairs.
        """
        task_name = "Agent Ops Daily Heartbeat"
        prompt = (
            "Run the governed Agent Ops heartbeat for "
            f"{focus_var}. Inspect recent agent runs, skill health, reactive "
            "trigger conditions, self-repair proposals, and trust signals. "
            "Persist only safe heartbeat facts, proposed repair items, and "
            "operator action records. Do not execute high-risk operations or "
            "apply self-repair without HITL approval."
        )
        task_data = {
            "user_id": user_id,
            "organization_id": organization_id,
            "name": task_name,
            "prompt": prompt,
            "schedule_type": "daily",
            "hour": 9,
            "minute": 0,
            "is_active": True,
            "notify_method": "notification",
            "next_execution_at": self._next_daily_utc(),
        }
        existing = await (
            db.table("user_scheduled_tasks")
            .select("id")
            .eq("user_id", user_id)
            .eq("organization_id", organization_id)
            .eq("name", task_name)
            .limit(1)
            .execute()
        )
        if existing.data:
            task_id = existing.data[0]["id"]
            result = await (
                db.table("user_scheduled_tasks")
                .update(task_data)
                .eq("id", task_id)
                .execute()
            )
            return {
                "mode": "updated",
                "task_id": task_id,
                "next_execution_at": task_data["next_execution_at"],
                "record": (result.data or [{}])[0],
            }

        result = await db.table("user_scheduled_tasks").insert(task_data).execute()
        record = (result.data or [{}])[0]
        return {
            "mode": "created",
            "task_id": record.get("id"),
            "next_execution_at": task_data["next_execution_at"],
            "record": record,
        }


agent_ops_runtime_service = AgentOpsRuntimeService()
