"""Lightweight business graph for Agent context and AI operating dashboards.

The graph deliberately uses existing operational tables instead of introducing a
new graph store. It gives the product a Glean-style "who/what is connected"
context layer that can be queried by dashboards, simulations, and runtime Agent
prompt injection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.graph_rag_models import BusinessGraphDocument


@dataclass(frozen=True)
class GraphQuerySpec:
    table: str
    select: str
    entity_type: str
    label_fields: tuple[str, ...]
    limit: int = 8
    order_by: str = "updated_at"


GRAPH_QUERY_SPECS: tuple[GraphQuerySpec, ...] = (
    GraphQuerySpec(
        table="customers",
        select="id, name, company, stage, industry, estimated_value, assigned_to, updated_at, created_at",
        entity_type="customer",
        label_fields=("name", "company"),
    ),
    GraphQuerySpec(
        table="sales_leads",
        select="id, name, company, stage, status, estimated_value, assigned_to, updated_at, created_at",
        entity_type="lead",
        label_fields=("name", "company"),
    ),
    GraphQuerySpec(
        table="projects",
        select="id, name, customer_id, client_id, customer_name, stage, status, progress, owner_id, updated_at, created_at",
        entity_type="project",
        label_fields=("name",),
    ),
    GraphQuerySpec(
        table="contracts",
        select="id, title, customer_id, project_id, status, amount, end_date, updated_at, created_at",
        entity_type="contract",
        label_fields=("title",),
    ),
    GraphQuerySpec(
        table="approval_requests",
        select="id, type, title, description, status, amount, submitted_by, requester_id, metadata, updated_at, created_at",
        entity_type="approval",
        label_fields=("title", "description", "type"),
        order_by="created_at",
    ),
    GraphQuerySpec(
        table="documents",
        select="id, title, filename, doc_type, status, metadata, created_at, updated_at",
        entity_type="document",
        label_fields=("title", "filename"),
        order_by="created_at",
    ),
    GraphQuerySpec(
        table="action_events",
        select="id, action_id, source, source_id, event_type, status, user_id, metadata, created_at",
        entity_type="action_event",
        label_fields=("action_id", "event_type"),
        order_by="created_at",
    ),
)


def _as_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    return str(value)


def _label(row: dict[str, Any], fields: tuple[str, ...], fallback: str) -> str:
    for field in fields:
        value = _as_text(row.get(field)).strip()
        if value:
            return value[:80]
    return fallback


def _entity_id(entity_type: str, row: dict[str, Any]) -> str:
    return f"{entity_type}:{_as_text(row.get('id') or row.get('action_id'), 'unknown')}"


async def _safe_query(
    db: Any, org_id: str, spec: GraphQuerySpec
) -> list[dict[str, Any]]:
    try:
        query = db.table(spec.table).select(spec.select).eq("organization_id", org_id)
        query = query.order(spec.order_by, desc=True).limit(spec.limit)
        result = await query.execute()
        return result.data or []
    except Exception:
        return []


def _build_nodes(rows_by_type: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for spec in GRAPH_QUERY_SPECS:
        for row in rows_by_type.get(spec.entity_type, []):
            nodes.append(
                {
                    "id": _entity_id(spec.entity_type, row),
                    "type": spec.entity_type,
                    "label": _label(row, spec.label_fields, spec.entity_type),
                    "status": row.get("status")
                    or row.get("stage")
                    or row.get("event_type"),
                    "value": row.get("estimated_value") or row.get("amount"),
                    "updated_at": row.get("updated_at") or row.get("created_at"),
                    "metadata": {
                        key: row.get(key)
                        for key in (
                            "industry",
                            "stage",
                            "status",
                            "progress",
                            "source",
                            "event_type",
                            "doc_type",
                        )
                        if row.get(key) is not None
                    },
                }
            )
    return nodes


def _build_edges(rows_by_type: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    customers = {
        _as_text(row.get("id")): _entity_id("customer", row)
        for row in rows_by_type.get("customer", [])
    }
    projects = {
        _as_text(row.get("id")): _entity_id("project", row)
        for row in rows_by_type.get("project", [])
    }

    for project in rows_by_type.get("project", []):
        project_id = _entity_id("project", project)
        customer_id = _as_text(project.get("customer_id") or project.get("client_id"))
        if customer_id and customer_id in customers:
            edges.append(
                {
                    "source": customers[customer_id],
                    "target": project_id,
                    "label": "客户项目",
                    "strength": 0.86,
                }
            )

    for contract in rows_by_type.get("contract", []):
        contract_id = _entity_id("contract", contract)
        customer_id = _as_text(contract.get("customer_id"))
        project_id = _as_text(contract.get("project_id"))
        if customer_id and customer_id in customers:
            edges.append(
                {
                    "source": customers[customer_id],
                    "target": contract_id,
                    "label": "客户合同",
                    "strength": 0.82,
                }
            )
        if project_id and project_id in projects:
            edges.append(
                {
                    "source": projects[project_id],
                    "target": contract_id,
                    "label": "项目合同",
                    "strength": 0.78,
                }
            )

    for event in rows_by_type.get("action_event", []):
        source = _as_text(event.get("source"))
        source_id = _as_text(event.get("source_id"))
        event_id = _entity_id("action_event", event)
        if source == "crm" and source_id in customers:
            edges.append(
                {
                    "source": customers[source_id],
                    "target": event_id,
                    "label": "客户行动",
                    "strength": 0.68,
                }
            )
        elif source == "approval":
            approval_ref = f"approval:{source_id}"
            edges.append(
                {
                    "source": approval_ref,
                    "target": event_id,
                    "label": "审批行动",
                    "strength": 0.62,
                }
            )

    return edges[:40]


def _prompt_context(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    if not nodes:
        return ""
    by_type: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        by_type.setdefault(node["type"], []).append(node)

    lines = [
        "[业务知识图谱]",
        "以下是当前组织内与本次请求相关的业务实体关系，请在回答和工具调用前优先参考：",
    ]
    for entity_type, items in sorted(by_type.items()):
        labels = "、".join(item["label"] for item in items[:5])
        lines.append(f"- {entity_type}: {labels}")
    for edge in edges[:8]:
        lines.append(f"- 关系: {edge['source']} -> {edge['target']} ({edge['label']})")
    lines.append(
        "使用要求：区分客户、项目、合同、审批、文档和行动事件；不要把缺失关系编造成事实。"
    )
    return "\n".join(lines)


async def build_business_context_graph(
    db: Any,
    *,
    org_id: str,
    user_id: str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    rows_by_type: dict[str, list[dict[str, Any]]] = {}
    for spec in GRAPH_QUERY_SPECS:
        rows_by_type[spec.entity_type] = await _safe_query(db, org_id, spec)

    nodes = _build_nodes(rows_by_type)
    edges = _build_edges(rows_by_type)
    prompt_context = _prompt_context(nodes, edges)
    density = round(len(edges) / max(len(nodes), 1), 2) if nodes else 0
    graph_document = BusinessGraphDocument.from_business_context_graph(
        {"nodes": nodes, "edges": edges, "prompt_context": prompt_context},
        org_id=org_id,
        source="business_context_graph",
    )

    return {
        "nodes": nodes,
        "edges": edges,
        "graph_document": graph_document.to_dict(),
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "density": density,
            "entity_counts": {
                entity_type: len(rows)
                for entity_type, rows in sorted(rows_by_type.items())
                if rows
            },
            "user_id": user_id,
            "role": role,
        },
        "prompt_context": prompt_context,
    }
