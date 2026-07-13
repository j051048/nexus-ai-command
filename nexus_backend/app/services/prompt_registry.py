"""Versioned prompt registry for built-in Agents.

The registry keeps prompt metadata out of ad-hoc runtime strings. It gives
operators a stable prompt version, owner, risk tier, and required eval gates
that can be attached to every Agent run and prompt snapshot.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class PromptBlockManifest:
    name: str
    purpose: str
    risk: str = "medium"
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PromptManifest:
    agent_code: str
    prompt_version: str
    owner: str
    scenario: str
    risk_tier: str
    status: str = "active"
    eval_gates: tuple[str, ...] = (
        "tool_selection",
        "safety",
        "agent_replay",
    )
    blocks: tuple[PromptBlockManifest, ...] = field(default_factory=tuple)
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["eval_gates"] = list(self.eval_gates)
        data["blocks"] = [block.to_dict() for block in self.blocks]
        return data


DEFAULT_PROMPT_BLOCKS = (
    PromptBlockManifest("角色与工具", "声明用户角色和可用工具", "medium"),
    PromptBlockManifest("推理框架", "复杂任务内部规划与风险评估", "medium", False),
    PromptBlockManifest("历史失败教训", "注入工具失败模式以减少重复错误", "low", False),
    PromptBlockManifest("参考示例", "注入静态/动态 few-shot 样例", "low", False),
    PromptBlockManifest(
        "上下文引擎检索结果", "注入业务图谱、记忆、知识库和历史对话", "high"
    ),
    PromptBlockManifest(
        "检索到的参考知识", "注入 RAG 文档证据并标明来源", "high", False
    ),
)


BUILTIN_PROMPT_MANIFESTS: dict[str, PromptManifest] = {
    "director_agent": PromptManifest(
        agent_code="director_agent",
        prompt_version="director_agent@2026-05-25.1",
        owner="AI Platform",
        scenario="通用业务指挥与工具编排",
        risk_tier="high",
        blocks=DEFAULT_PROMPT_BLOCKS,
    ),
    "sales_agent": PromptManifest(
        agent_code="sales_agent",
        prompt_version="sales_agent@2026-05-25.1",
        owner="Sales AI Ops",
        scenario="科学仪器销售跟进、客户分析和商机推进",
        risk_tier="high",
        eval_gates=("tool_selection", "safety", "rag_quality", "agent_replay"),
        blocks=DEFAULT_PROMPT_BLOCKS,
    ),
    "vmd_agent": PromptManifest(
        agent_code="vmd_agent",
        prompt_version="vmd_agent@2026-05-25.1",
        owner="VMD Growth",
        scenario="虚拟营销部线索、竞品、投标和内容作战",
        risk_tier="high",
        eval_gates=("router_accuracy", "tool_selection", "safety", "agent_replay"),
        blocks=DEFAULT_PROMPT_BLOCKS,
    ),
}


class PromptRegistry:
    def __init__(self, manifests: dict[str, PromptManifest] | None = None) -> None:
        self._manifests = dict(manifests or BUILTIN_PROMPT_MANIFESTS)

    def get_manifest(self, agent_code: str | None) -> PromptManifest:
        key = agent_code or "director_agent"
        return self._manifests.get(key) or self._manifests["director_agent"]

    def resolve_prompt_version(self, agent_code: str | None) -> str:
        try:
            from app.services.prompt_artifact_service import prompt_artifact_resolver

            return prompt_artifact_resolver.builtin(agent_code).version
        except Exception:
            return self.get_manifest(agent_code).prompt_version

    def list_manifests(self) -> list[dict[str, Any]]:
        return [manifest.to_dict() for manifest in self._manifests.values()]

    def build_runtime_header(self, agent_code: str | None) -> str:
        try:
            from app.services.prompt_artifact_service import prompt_artifact_resolver

            return prompt_artifact_resolver.runtime_header(
                prompt_artifact_resolver.builtin(agent_code)
            )
        except Exception:
            pass
        manifest = self.get_manifest(agent_code)
        gates = ", ".join(manifest.eval_gates)
        required_blocks = ", ".join(
            block.name for block in manifest.blocks if block.required
        )
        return (
            "[Prompt Registry]\n"
            f"agent_code: {manifest.agent_code}\n"
            f"prompt_version: {manifest.prompt_version}\n"
            f"owner: {manifest.owner}\n"
            f"scenario: {manifest.scenario}\n"
            f"risk_tier: {manifest.risk_tier}\n"
            f"eval_gates: {gates}\n"
            f"required_blocks: {required_blocks}"
        )


prompt_registry = PromptRegistry()
