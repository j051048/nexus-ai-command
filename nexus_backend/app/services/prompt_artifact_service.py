"""Canonical prompt artifacts, resolution, rendering, and release gates.

This module is the compatibility boundary between built-in prompts, tenant
overrides, and the Agent prompt release workflow. Runtime callers should use
``prompt_artifact_resolver`` instead of reading prompt tables directly.
"""

from __future__ import annotations

import hashlib
import logging
import string
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class PromptReleaseState(StrEnum):
    DRAFT = "draft"
    LINTED = "linted"
    OFFLINE_EVAL = "offline_eval"
    SHADOW = "shadow"
    CANARY = "canary"
    ACTIVE = "active"
    RETIRED = "retired"
    REJECTED = "rejected"


RELEASE_TRANSITIONS: dict[PromptReleaseState, frozenset[PromptReleaseState]] = {
    PromptReleaseState.DRAFT: frozenset(
        {PromptReleaseState.LINTED, PromptReleaseState.REJECTED}
    ),
    PromptReleaseState.LINTED: frozenset(
        {PromptReleaseState.OFFLINE_EVAL, PromptReleaseState.REJECTED}
    ),
    PromptReleaseState.OFFLINE_EVAL: frozenset(
        {PromptReleaseState.SHADOW, PromptReleaseState.REJECTED}
    ),
    PromptReleaseState.SHADOW: frozenset(
        {PromptReleaseState.CANARY, PromptReleaseState.REJECTED}
    ),
    PromptReleaseState.CANARY: frozenset(
        {PromptReleaseState.ACTIVE, PromptReleaseState.REJECTED}
    ),
    PromptReleaseState.ACTIVE: frozenset({PromptReleaseState.RETIRED}),
    PromptReleaseState.RETIRED: frozenset(),
    PromptReleaseState.REJECTED: frozenset({PromptReleaseState.DRAFT}),
}

REQUIRED_EVIDENCE: dict[PromptReleaseState, tuple[str, ...]] = {
    PromptReleaseState.LINTED: ("lint",),
    PromptReleaseState.OFFLINE_EVAL: ("lint", "offline_eval"),
    PromptReleaseState.SHADOW: ("lint", "offline_eval", "shadow"),
    PromptReleaseState.CANARY: ("lint", "offline_eval", "shadow", "canary"),
    PromptReleaseState.ACTIVE: ("lint", "offline_eval", "shadow", "canary"),
}


@dataclass(frozen=True)
class PromptModelProfile:
    model: str = "deepseek-v4-flash"
    max_input_tokens: int = 32_000
    reserved_output_tokens: int = 2_000
    temperature: float = 0.2


@dataclass(frozen=True)
class PromptArtifact:
    prompt_key: str
    agent_code: str
    version: str
    content: str
    state: PromptReleaseState = PromptReleaseState.ACTIVE
    organization_id: str | None = None
    owner: str = "AI Platform"
    risk_tier: str = "medium"
    variables: tuple[str, ...] = ("current_time",)
    required_evals: tuple[str, ...] = (
        "tool_selection",
        "safety",
        "agent_replay",
    )
    model_profile: PromptModelProfile = field(default_factory=PromptModelProfile)
    evidence: Mapping[str, Any] = field(default_factory=dict)
    source: str = "builtin"

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        data["content_hash"] = self.content_hash
        return data

    def render(self, values: Mapping[str, Any]) -> str:
        return StrictPromptRenderer.render(
            self.content,
            values=values,
            declared_variables=self.variables,
        )


class StrictPromptRenderer:
    """Render only declared variables and fail closed on missing values."""

    @staticmethod
    def fields(template: str) -> set[str]:
        fields: set[str] = set()
        for _, field_name, _, _ in string.Formatter().parse(template):
            if field_name:
                fields.add(field_name.split(".", 1)[0].split("[", 1)[0])
        return fields

    @classmethod
    def render(
        cls,
        template: str,
        *,
        values: Mapping[str, Any],
        declared_variables: tuple[str, ...] | list[str] | set[str],
    ) -> str:
        declared = set(declared_variables)
        referenced = cls.fields(template)
        undeclared = referenced - declared
        if undeclared:
            raise ValueError(
                f"Prompt references undeclared variables: {sorted(undeclared)}"
            )
        missing = referenced - set(values)
        if missing:
            raise ValueError(f"Prompt variables are missing: {sorted(missing)}")
        return template.format_map(dict(values))


class PromptReleaseGate:
    """Validate release transitions using machine-readable evidence."""

    def validate_transition(
        self,
        current: PromptReleaseState | str,
        target: PromptReleaseState | str,
        evidence: Mapping[str, Any] | None,
    ) -> None:
        current_state = PromptReleaseState(current)
        target_state = PromptReleaseState(target)
        if target_state not in RELEASE_TRANSITIONS[current_state]:
            raise ValueError(
                f"Invalid prompt transition: {current_state.value} -> {target_state.value}"
            )
        evidence = evidence or {}
        missing = [
            key
            for key in REQUIRED_EVIDENCE.get(target_state, ())
            if not self._evidence_passed(evidence.get(key))
        ]
        if missing:
            raise ValueError(
                f"Prompt transition lacks passing evidence: {', '.join(missing)}"
            )

    @staticmethod
    def _evidence_passed(value: Any) -> bool:
        if value is True:
            return True
        if isinstance(value, Mapping):
            return value.get("passed") is True
        return False


AGENT_TO_PROMPT_KEY = {
    "sales_agent": "sales_commander",
    "sales_commander": "sales_commander",
    "approval_agent": "approval_manager",
    "approval_manager": "approval_manager",
    "performance_agent": "performance_coach",
    "performance_coach": "performance_coach",
    "boss_agent": "boss_assistant",
    "boss_assistant": "boss_assistant",
    "director_agent": "default_fallback",
    "default": "default_fallback",
}


class PromptArtifactResolver:
    """Resolve one authoritative active artifact with safe built-in fallback."""

    def prompt_key_for(self, agent_code: str | None) -> str:
        return AGENT_TO_PROMPT_KEY.get(agent_code or "default", "default_fallback")

    def builtin(
        self, agent_code: str | None, prompt_key: str | None = None
    ) -> PromptArtifact:
        from app.core.prompts_registry import SYSTEM_PROMPTS

        key = prompt_key or self.prompt_key_for(agent_code)
        content = SYSTEM_PROMPTS.get(key) or SYSTEM_PROMPTS["default_fallback"]
        code = agent_code or "director_agent"
        version = (
            f"{code}@builtin-{hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]}"
        )
        return PromptArtifact(
            prompt_key=key,
            agent_code=code,
            version=version,
            content=content,
            source="builtin",
        )

    async def resolve(
        self,
        *,
        agent_code: str | None,
        organization_id: str | None = None,
        db_client: Any | None = None,
    ) -> PromptArtifact:
        fallback = self.builtin(agent_code)
        try:
            client = db_client
            if client is None:
                from app.core.database import supabase

                client = supabase
            if client is None:
                return fallback

            scopes = [organization_id, None] if organization_id else [None]
            for scope in scopes:
                query = (
                    client.table("agent_prompt_versions")
                    .select(
                        "organization_id,agent_code,prompt_version,owner,risk_tier,status,manifest"
                    )
                    .eq("agent_code", agent_code or "director_agent")
                    .eq("status", PromptReleaseState.ACTIVE.value)
                )
                query = (
                    query.eq("organization_id", scope)
                    if scope
                    else query.is_("organization_id", "null")
                )
                response = await query.order("updated_at", desc=True).limit(1).execute()
                row = (response.data or [None])[0]
                if row:
                    return self._from_row(row, fallback)
            return fallback
        except Exception as exc:
            logger.debug("Prompt artifact DB resolution fell back to builtin: %s", exc)
            return fallback

    def _from_row(
        self, row: Mapping[str, Any], fallback: PromptArtifact
    ) -> PromptArtifact:
        manifest = row.get("manifest") or {}
        content = manifest.get("content") or fallback.content
        variables = tuple(manifest.get("variables") or fallback.variables)
        required_evals = tuple(
            manifest.get("required_evals") or fallback.required_evals
        )
        model_data = manifest.get("model_profile") or {}
        profile = PromptModelProfile(
            model=model_data.get("model", fallback.model_profile.model),
            max_input_tokens=int(
                model_data.get(
                    "max_input_tokens", fallback.model_profile.max_input_tokens
                )
            ),
            reserved_output_tokens=int(
                model_data.get(
                    "reserved_output_tokens",
                    fallback.model_profile.reserved_output_tokens,
                )
            ),
            temperature=float(
                model_data.get("temperature", fallback.model_profile.temperature)
            ),
        )
        return PromptArtifact(
            prompt_key=manifest.get("prompt_key") or fallback.prompt_key,
            agent_code=str(row.get("agent_code") or fallback.agent_code),
            version=str(row.get("prompt_version") or fallback.version),
            content=str(content),
            state=PromptReleaseState(str(row.get("status") or "active")),
            organization_id=(
                str(row["organization_id"]) if row.get("organization_id") else None
            ),
            owner=str(row.get("owner") or fallback.owner),
            risk_tier=str(row.get("risk_tier") or fallback.risk_tier),
            variables=variables,
            required_evals=required_evals,
            model_profile=profile,
            evidence=manifest.get("evidence") or {},
            source="database",
        )

    def runtime_header(self, artifact: PromptArtifact) -> str:
        return "\n".join(
            [
                "[Prompt Artifact]",
                f"agent_code: {artifact.agent_code}",
                f"prompt_version: {artifact.version}",
                f"content_hash: {artifact.content_hash}",
                f"risk_tier: {artifact.risk_tier}",
                f"required_evals: {', '.join(artifact.required_evals)}",
            ]
        )


prompt_release_gate = PromptReleaseGate()
prompt_artifact_resolver = PromptArtifactResolver()


def default_prompt_values() -> dict[str, str]:
    return {
        "current_time": datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    }
