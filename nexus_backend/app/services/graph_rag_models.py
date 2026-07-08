"""Shared GraphRAG data models for business Agent context.

The models in this file intentionally mirror the small ``GraphDocument``
shape used by graph-native LangChain integrations: nodes, relationships and
source evidence.  They keep our current Supabase-backed graph layer portable
without requiring a dedicated graph database.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from typing import Any


@dataclass(frozen=True)
class EvidencePath:
    """Where a graph fact came from and how confident we are in it."""

    source: str
    table: str | None = None
    record_id: str | None = None
    field: str | None = None
    trace_id: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence"] = max(0.0, min(float(self.confidence), 1.0))
        return data


@dataclass(frozen=True)
class BusinessGraphNode:
    """A business entity that can be injected into Agent context."""

    id: str
    type: str
    label: str
    text: str = ""
    status: str | None = None
    value: Any = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    evidence: list[EvidencePath] = dataclass_field(default_factory=list)

    def embedding_text(self) -> str:
        parts = [
            f"type: {self.type}",
            f"label: {self.label}",
            f"status: {self.status or ''}",
            f"value: {self.value or ''}",
            self.text,
        ]
        for key, value in sorted(self.metadata.items()):
            if value is not None:
                parts.append(f"{key}: {value}")
        return "\n".join(part for part in parts if str(part).strip())

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.to_dict() for item in self.evidence]
        data["embedding_text"] = self.embedding_text()
        return data


@dataclass(frozen=True)
class BusinessGraphRelationship:
    """A directed relationship between two business entities."""

    source: str
    target: str
    type: str
    label: str = ""
    strength: float = 1.0
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    evidence: list[EvidencePath] = dataclass_field(default_factory=list)

    def embedding_text(self, node_labels: dict[str, str] | None = None) -> str:
        labels = node_labels or {}
        source_label = labels.get(self.source, self.source)
        target_label = labels.get(self.target, self.target)
        parts = [
            f"source: {source_label}",
            f"relationship: {self.type}",
            f"label: {self.label}",
            f"target: {target_label}",
            f"strength: {self.strength:.2f}",
        ]
        for key, value in sorted(self.metadata.items()):
            if value is not None:
                parts.append(f"{key}: {value}")
        return "\n".join(part for part in parts if str(part).strip())

    def to_dict(self, node_labels: dict[str, str] | None = None) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.to_dict() for item in self.evidence]
        data["embedding_text"] = self.embedding_text(node_labels)
        return data


@dataclass(frozen=True)
class BusinessGraphDocument:
    """Portable graph document for GraphRAG ingestion and Agent context."""

    org_id: str
    nodes: list[BusinessGraphNode]
    relationships: list[BusinessGraphRelationship]
    source: EvidencePath
    prompt_context: str = ""

    @property
    def node_labels(self) -> dict[str, str]:
        return {node.id: node.label for node in self.nodes}

    def to_dict(self) -> dict[str, Any]:
        labels = self.node_labels
        return {
            "org_id": self.org_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "relationships": [
                relationship.to_dict(labels) for relationship in self.relationships
            ],
            "source": self.source.to_dict(),
            "prompt_context": self.prompt_context,
        }

    @classmethod
    def from_business_context_graph(
        cls,
        graph: dict[str, Any],
        *,
        org_id: str,
        source: str = "business_context_graph",
        trace_id: str | None = None,
    ) -> BusinessGraphDocument:
        source_evidence = EvidencePath(source=source, trace_id=trace_id)
        nodes = [
            BusinessGraphNode(
                id=str(item.get("id", "")),
                type=str(item.get("type", "entity")),
                label=str(item.get("label") or item.get("id") or "entity"),
                status=item.get("status"),
                value=item.get("value"),
                metadata=dict(item.get("metadata") or {}),
                evidence=[
                    EvidencePath(
                        source=source,
                        record_id=str(item.get("id", "")),
                        trace_id=trace_id,
                    )
                ],
            )
            for item in graph.get("nodes", [])
            if item.get("id")
        ]
        relationships = [
            BusinessGraphRelationship(
                source=str(item.get("source", "")),
                target=str(item.get("target", "")),
                type=str(item.get("type") or item.get("label") or "related_to"),
                label=str(item.get("label") or item.get("type") or "related_to"),
                strength=float(item.get("strength") or 1.0),
                metadata=dict(item.get("metadata") or {}),
                evidence=[
                    EvidencePath(
                        source=source,
                        record_id=f"{item.get('source', '')}->{item.get('target', '')}",
                        trace_id=trace_id,
                    )
                ],
            )
            for item in graph.get("edges", [])
            if item.get("source") and item.get("target")
        ]
        return cls(
            org_id=org_id,
            nodes=nodes,
            relationships=relationships,
            source=source_evidence,
            prompt_context=str(graph.get("prompt_context") or ""),
        )
