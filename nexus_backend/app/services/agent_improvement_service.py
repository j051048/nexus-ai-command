"""Hermes-style improvement proposals for built-in Agents.

The service never mutates prompts or policies directly. It produces structured
change proposals, runs Agent CI, and requires human approval/gray rollout before
anything can become active.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.services.agent_ci_service import agent_ci_service


@dataclass
class ImprovementProposal:
    id: str
    category: str
    title: str
    rationale: str
    proposed_patch: dict[str, Any]
    risk_level: str
    approval_required: bool = True
    status: str = "proposed"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentImprovementService:
    def generate_proposals(
        self,
        *,
        runs: list[dict[str, Any]] | None = None,
        prompt_manifest: dict[str, Any] | None = None,
        context_pack: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        runs = runs or []
        prompt_manifest = prompt_manifest or {}
        context_pack = context_pack or {}
        proposals: list[ImprovementProposal] = []

        failed_runs = [
            run
            for run in runs
            if run.get("status") in {"failed", "error", "cancelled"}
            or run.get("error")
            or run.get("error_message")
        ]
        tool_errors = [
            run
            for run in runs
            if "tool" in str(run.get("error") or run.get("error_message") or "").lower()
        ]

        if failed_runs:
            proposals.append(
                ImprovementProposal(
                    id="proposal-prompt-failure-guard",
                    category="prompt_patch",
                    title="补充失败恢复与证据不足降级规则",
                    rationale=f"最近样本中发现 {len(failed_runs)} 个失败/取消 Agent run。",
                    proposed_patch={
                        "prompt_block": "历史失败教训",
                        "change": "要求工具失败时生成降级方案、保留证据链并提示人工接管。",
                    },
                    risk_level="medium",
                )
            )

        if tool_errors:
            proposals.append(
                ImprovementProposal(
                    id="proposal-tool-contract-guard",
                    category="tool_rule",
                    title="为高失败工具补参数校验和重试上限",
                    rationale=f"发现 {len(tool_errors)} 个工具相关失败信号。",
                    proposed_patch={
                        "rule": "tool_preflight_validation",
                        "change": "工具调用前检查必填参数，失败后最多重试一次并转人工确认。",
                    },
                    risk_level="medium",
                )
            )

        if context_pack.get("context_quality_score", 1) < 0.65:
            proposals.append(
                ImprovementProposal(
                    id="proposal-context-quality-threshold",
                    category="context_rule",
                    title="低质量上下文触发补证据或追问",
                    rationale="Context Quality Score 低于 0.65，直接执行容易误判。",
                    proposed_patch={
                        "rule": "context_quality_gate",
                        "threshold": 0.65,
                        "fallback": "追问用户或只生成草稿，不执行外部动作。",
                    },
                    risk_level="high",
                )
            )

        if not proposals:
            proposals.append(
                ImprovementProposal(
                    id="proposal-golden-example-refresh",
                    category="golden_example",
                    title="沉淀本周高质量对话为 Golden Examples",
                    rationale="当前没有明显失败信号，适合把高采纳对话蒸馏为 few-shot 样例。",
                    proposed_patch={
                        "memory_category": "golden_example",
                        "change": "挑选高采纳、低风险、证据完整的对话进入 prompt few-shot 候选池。",
                    },
                    risk_level="low",
                )
            )

        ci = agent_ci_service.run_static_ci(
            candidate_metadata={
                "prompt_version": prompt_manifest.get("prompt_version"),
                "source": "improvement_proposal",
            }
        )
        return {
            "proposals": [proposal.to_dict() for proposal in proposals],
            "agent_ci": ci,
            "governance": {
                "self_mutation_allowed": False,
                "required_flow": [
                    "生成提案",
                    "Agent CI / Replay / Shadow Eval",
                    "人工批准",
                    "小流量灰度",
                    "指标达标后发布",
                ],
            },
        }


agent_improvement_service = AgentImprovementService()
