from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

from app.core.route_introspection import iter_effective_routes
from app.routers import knowledge
from app.startup.route_groups import register_document_routes

GRAPH_ROWS = [
    {
        "id": "rel-1",
        "source_entity": "成都某高校",
        "source_type": "organization",
        "relationship": "interested_in",
        "destination_entity": "高分辨质谱",
        "destination_type": "product",
        "confidence": 0.92,
        "source_context": "采购线索",
        "created_at": "2026-07-18T00:00:00Z",
    }
]


def test_entity_identifier_round_trip():
    entity_id = knowledge._entity_id("成都某高校", "organization")

    assert knowledge._decode_entity_id(entity_id) == ("成都某高校", "organization")


@pytest.mark.asyncio
async def test_search_entities_returns_frontend_contract(monkeypatch):
    monkeypatch.setattr(knowledge, "_load_rows", AsyncMock(return_value=GRAPH_ROWS))

    response = await knowledge.search_entities(
        q="成都", db=object(), _organization_id="org-1"
    )

    assert response["success"] is True
    assert response["data"][0]["name"] == "成都某高校"
    assert response["data"][0]["relation_count"] == 1


@pytest.mark.asyncio
async def test_entity_relations_return_stable_ids(monkeypatch):
    monkeypatch.setattr(knowledge, "_load_rows", AsyncMock(return_value=GRAPH_ROWS))
    entity_id = knowledge._entity_id("成都某高校", "organization")

    response = await knowledge.get_entity_relations(
        entity_id=entity_id, db=object(), _organization_id="org-1"
    )

    relation = response["data"][0]
    assert relation["source_id"] == entity_id
    assert relation["target_name"] == "高分辨质谱"
    assert relation["weight"] == 0.92


@pytest.mark.asyncio
async def test_patterns_return_empty_graph_without_error(monkeypatch):
    monkeypatch.setattr(knowledge, "_load_rows", AsyncMock(return_value=[]))

    response = await knowledge.get_graph_patterns(db=object(), _organization_id="org-1")

    assert response["data"]["total_entities"] == 0
    assert response["data"]["total_relations"] == 0


def test_knowledge_router_is_registered_with_document_routes():
    app = FastAPI()
    register_document_routes(app)
    paths = {
        route.path
        for route in iter_effective_routes(app.routes)
        if hasattr(route, "path")
    }

    assert "/api/knowledge/search" in paths
    assert "/api/knowledge/entity/{entity_id}/relations" in paths
    assert "/api/knowledge/patterns" in paths
