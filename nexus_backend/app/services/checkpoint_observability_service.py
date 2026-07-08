"""Observable projection helpers for LangGraph checkpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.graph_rag_models import EvidencePath


@dataclass(frozen=True)
class CheckpointProjection:
    thread_id: str
    checkpoint_id: str
    checkpoint_ns: str = ""
    parent_checkpoint_id: str | None = None
    channel_count: int = 0
    pending_write_count: int = 0
    tool_calls: list[str] = field(default_factory=list)
    hitl_status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    evidence: list[EvidencePath] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.to_dict() for item in self.evidence]
        return data


def _config_value(config: dict[str, Any] | None, key: str, default: str = "") -> str:
    if not config:
        return default
    configurable = config.get("configurable", {})
    return str(configurable.get(key) or default)


def project_checkpoint_tuple(
    *,
    config: dict[str, Any],
    checkpoint: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    parent_config: dict[str, Any] | None = None,
    pending_writes: list[tuple[str, str, Any]] | None = None,
) -> CheckpointProjection:
    """Project a LangGraph checkpoint tuple into an auditable record."""

    pending = pending_writes or []
    channel_values = checkpoint.get("channel_values") or {}
    messages = channel_values.get("messages") or checkpoint.get("messages") or []
    tool_calls: list[str] = []
    for message in messages:
        calls = getattr(message, "tool_calls", None)
        if calls is None and isinstance(message, dict):
            calls = message.get("tool_calls")
        for call in calls or []:
            if isinstance(call, dict):
                name = call.get("name") or call.get("tool_name") or call.get("id")
            else:
                name = getattr(call, "name", None) or getattr(call, "id", None)
            if name:
                tool_calls.append(str(name))

    hitl_status = (
        checkpoint.get("hitl_status")
        or channel_values.get("hitl_status")
        or (metadata or {}).get("hitl_status")
    )
    thread_id = _config_value(config, "thread_id")
    checkpoint_ns = _config_value(config, "checkpoint_ns")
    checkpoint_id = _config_value(
        config, "checkpoint_id", str(checkpoint.get("id", ""))
    )
    parent_id = _config_value(parent_config, "checkpoint_id", "") or None

    return CheckpointProjection(
        thread_id=thread_id,
        checkpoint_id=checkpoint_id,
        checkpoint_ns=checkpoint_ns,
        parent_checkpoint_id=parent_id,
        channel_count=len(checkpoint.get("channel_versions") or {}),
        pending_write_count=len(pending),
        tool_calls=tool_calls,
        hitl_status=str(hitl_status) if hitl_status else None,
        metadata=dict(metadata or {}),
        evidence=[
            EvidencePath(
                source="langgraph_checkpoint",
                record_id=checkpoint_id,
                trace_id=thread_id,
                metadata={"checkpoint_ns": checkpoint_ns},
            )
        ],
    )


def get_checkpoint_observability_contract() -> dict[str, Any]:
    """Return the projection contract used by Agent replay/debug UI."""

    return {
        "projection_name": "checkpoint_observability_projection",
        "source": "LangGraph checkpointer",
        "fields": [
            "thread_id",
            "checkpoint_id",
            "checkpoint_ns",
            "parent_checkpoint_id",
            "channel_count",
            "pending_write_count",
            "tool_calls",
            "hitl_status",
            "metadata",
            "evidence",
        ],
        "supports_pending_writes": True,
        "supports_human_review_debugging": True,
    }
