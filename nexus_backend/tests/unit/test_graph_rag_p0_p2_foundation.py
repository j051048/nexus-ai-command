from app.services.business_entity_embedding_service import (
    build_entity_embedding_candidates,
    build_relationship_embedding_candidates,
    get_entity_embedding_plan,
)
from app.services.checkpoint_observability_service import (
    get_checkpoint_observability_contract,
    project_checkpoint_tuple,
)
from app.services.generated_query_safety import evaluate_generated_query
from app.services.graph_rag_models import BusinessGraphDocument
from app.services.graph_rag_retrieval_service import (
    GRAPH_RAG_RETRIEVAL_STEPS,
    build_context_packet_from_graph,
)
from app.services.retrieval_security import (
    construct_metadata_filter,
    next_fetch_k,
    require_org_scope,
)


def _sample_graph_document() -> BusinessGraphDocument:
    graph = {
        "nodes": [
            {
                "id": "customer:c1",
                "type": "customer",
                "label": "Acme Lab",
                "status": "stale",
                "metadata": {"industry": "scientific instruments"},
            },
            {
                "id": "project:p1",
                "type": "project",
                "label": "Microscope upgrade",
                "status": "quote",
            },
            {
                "id": "contract:k1",
                "type": "contract",
                "label": "Renewal contract",
                "status": "risk",
            },
        ],
        "edges": [
            {
                "source": "customer:c1",
                "target": "project:p1",
                "type": "owns_project",
                "label": "customer project",
                "strength": 0.9,
            },
            {
                "source": "project:p1",
                "target": "contract:k1",
                "type": "has_contract",
                "label": "project contract",
                "strength": 0.8,
            },
        ],
        "prompt_context": "Acme Lab has a quote-stage project.",
    }
    return BusinessGraphDocument.from_business_context_graph(
        graph,
        org_id="org-1",
        source="unit_test",
        trace_id="trace-1",
    )


def test_business_graph_document_preserves_evidence_and_embedding_text():
    document = _sample_graph_document()

    assert document.org_id == "org-1"
    assert document.nodes[0].evidence[0].source == "unit_test"
    assert "Acme Lab" in document.nodes[0].embedding_text()
    assert "Acme Lab" in document.relationships[0].embedding_text(document.node_labels)
    assert document.to_dict()["relationships"][0]["evidence"]


def test_entity_and_relationship_embedding_candidates_are_separate():
    document = _sample_graph_document()
    plan = get_entity_embedding_plan()
    entity_rows = build_entity_embedding_candidates(document)
    relationship_rows = build_relationship_embedding_candidates(document)

    assert plan["index_contract"]["supports_from_existing_graph"] is True
    assert plan["index_contract"]["supports_relationship_embeddings"] is True
    assert {row["entity_type"] for row in entity_rows} >= {"customer", "project"}
    assert relationship_rows[0]["entity_type"] == "relationship"
    assert "customer project" in relationship_rows[0]["content"]


def test_retrieval_security_parameterizes_metadata_and_requires_org_scope():
    scoped = require_org_scope({"stage": "quote"}, "org-1")
    metadata_filter = construct_metadata_filter(scoped, alias="n")

    assert scoped["organization_id"] == "org-1"
    assert "n.`stage` = $filter_param_0" in metadata_filter.snippet
    assert "quote" in metadata_filter.params.values()


def test_fetch_k_escalation_stops_when_counts_stop_growing():
    assert (
        next_fetch_k(
            current_fetch_k=4,
            requested_k=8,
            observed_count=3,
            previous_count=2,
        )
        == 16
    )
    assert (
        next_fetch_k(
            current_fetch_k=16,
            requested_k=8,
            observed_count=3,
            previous_count=3,
        )
        is None
    )


def test_generated_query_safety_blocks_mutations_and_missing_tenant_guard():
    denied = evaluate_generated_query(
        "MATCH (n) DETACH DELETE n",
        dialect="cypher",
        require_tenant_guard=False,
    )
    missing_tenant = evaluate_generated_query(
        "SELECT * FROM customers",
        dialect="sql",
    )
    allowed = evaluate_generated_query(
        "SELECT * FROM customers WHERE organization_id = :org_id",
        dialect="sql",
    )

    assert denied.allowed is False
    assert denied.requires_human_review is True
    assert missing_tenant.reason == "missing_tenant_guard"
    assert allowed.allowed is True
    assert allowed.read_only is True


def test_graph_rag_context_packet_has_ordered_p0_p2_steps_and_mmr_context():
    document = _sample_graph_document()
    packet = build_context_packet_from_graph(
        "Acme Lab renewal risk",
        document,
        org_id="org-1",
        user_id="user-1",
        role="boss",
        filters={"stage": "quote"},
        limit=4,
    )

    assert packet.plan.steps == GRAPH_RAG_RETRIEVAL_STEPS
    assert packet.plan.metadata_filter["organization_id"] == "org-1"
    assert "customer:c1" in packet.plan.candidate_entities
    assert "contract:k1" in packet.plan.expanded_entities
    assert packet.context_items
    assert packet.prompt_context


def test_checkpoint_projection_exposes_pending_writes_tool_calls_and_hitl():
    projection = project_checkpoint_tuple(
        config={
            "configurable": {
                "thread_id": "thread-1",
                "checkpoint_ns": "",
                "checkpoint_id": "ckpt-2",
            }
        },
        parent_config={"configurable": {"checkpoint_id": "ckpt-1"}},
        checkpoint={
            "id": "ckpt-2",
            "channel_versions": {"messages": "2"},
            "channel_values": {
                "messages": [
                    {"type": "ai", "tool_calls": [{"name": "crm_followup"}]},
                ],
                "hitl_status": "approved",
            },
        },
        metadata={"source": "unit"},
        pending_writes=[("task-1", "messages", {"value": 1})],
    )
    contract = get_checkpoint_observability_contract()

    assert projection.pending_write_count == 1
    assert projection.parent_checkpoint_id == "ckpt-1"
    assert projection.tool_calls == ["crm_followup"]
    assert projection.hitl_status == "approved"
    assert contract["supports_pending_writes"] is True
