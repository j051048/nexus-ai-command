import copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.agent.artifact_contract import ArtifactSpec
from app.agent.delivery_requirements import DeliveryRequirements
from app.services.artifact_evidence_compiler import _split_excerpt
from app.services.artifact_stage_cache import ArtifactStageCache, merge_delivery_usage
from app.services.artifact_workspace_service import require_current_evidence_access, revision_payload
from app.services.delivery_requirement_service import evaluate_delivery_requirements, resolve_delivery_quote


class Query:
    def __init__(self, rows, filters):
        self.rows = rows
        self.filters = filters

    def select(self, *_):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self

    def in_(self, key, values):
        self.rows = [row for row in self.rows if row.get(key) in values]
        return self

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    async def execute(self):
        return SimpleNamespace(data=self.rows)


class DB:
    def __init__(self, **tables):
        self.tables = tables
        self.filters = []

    def table(self, name):
        return Query(self.tables.get(name, []), self.filters)


@pytest.mark.parametrize("payload", [
    {"catalog_quantities": {"FD-F": 0}}, {"catalog_quantities": {"FD-F": True}},
    {"catalog_quantities": {"FD-F": 10001}}, {"budget": -1}, {"budget": "NaN"},
    {"forbidden_claims": [" "]}, {"unit_price": 1},
    {"required_facts": [{"topic": "  ", "expected_text": "合法证据"}]},
])
def test_invalid_requirements_rejected_at_boundary(payload):
    with pytest.raises(ValidationError):
        DeliveryRequirements.model_validate(payload)


def test_fact_needs_source_and_local_citation():
    spec = ArtifactSpec(delivery_requirements={"required_facts": [
        {"topic": "售后", "expected_text": "提供安装培训"},
    ], "forbidden_claims": ["永久免费保修"]})
    evidence = {"records": [{"document_id": "doc", "chunk_id": "c1", "excerpt": "提供安装培训"}]}
    check = lambda text, packet=evidence: evaluate_delivery_requirements(text, spec, packet)
    assert not check("提供安装培训 [EVID:doc:c1]")["findings"]
    assert check("提供安装培训\n\n其他事项 [EVID:doc:c1]")["findings"]
    assert check("提供安装培训 [EVID:doc:c1]", {})["findings"]
    assert check("提供安装培训 [EVID:doc:c1] 永久免费保修")["findings"][0]["code"] == "delivery_forbidden_claim"


@pytest.mark.asyncio
async def test_quote_uses_tenant_price_book_and_tax_not_model_prices():
    db = DB(
        instrument_product_catalog=[{"organization_id": "org", "id": "p1", "model_code": "FD-F",
                                     "is_active": True, "validation_status": "verified", "list_price": 100}],
        solution_price_books=[{"organization_id": "org", "id": "b1", "status": "active", "is_default": True, "tax_rate": .13}],
        solution_price_book_items=[{"organization_id": "org", "price_book_id": "b1", "product_id": "p1", "unit_price": 200}],
    )
    requirements = DeliveryRequirements(budget=450, catalog_quantities={"FD-F": 2})
    quote = await resolve_delivery_quote(db, "org", requirements)
    assert quote["total"] == 452
    assert db.filters.count(("organization_id", "org")) == 3
    assert evaluate_delivery_requirements("", ArtifactSpec(delivery_requirements=requirements, commercial_quote=quote), {})["findings"][0]["code"] == "delivery_budget_exceeded"
    db.tables["instrument_product_catalog"][0]["list_price"] = None
    db.tables["solution_price_book_items"] = []
    assert not (await resolve_delivery_quote(db, "org", requirements))["valid"]
    db.tables["solution_price_books"] = []
    assert (await resolve_delivery_quote(db, "org", requirements))["approval_required"]


def test_long_document_retrieval_keeps_late_terms_and_complete_passages():
    from app.services.agent_evidence_service import EvidenceRecord
    from app.services.evidence_selection import select_evidence

    chunks = _split_excerpt(("背景材料" * 380 + "\n") * 30 + "售后条款：提供安装培训")
    assert len(chunks) > 20 and "提供安装培训" in chunks[-1]
    excerpt = "|项目|条款|\n" + "材料" * 710 + "\n适用条件：另行签订服务协议"
    record = EvidenceRecord(document_id="d", chunk_id="c", title="服务", excerpt=excerpt, purposes=["售后"])
    assert select_evidence([record], ["售后"])[0].excerpt.endswith("另行签订服务协议")


class CheckpointDB:
    def __init__(self):
        self.saved = {}
        self.denied = False

    def rpc(self, name, args):
        assert name == "artifact_stage_checkpoint"
        async def execute():
            if self.denied:
                raise PermissionError("lease lost")
            key = tuple(args[key] for key in ("p_organization_id", "p_user_id", "p_job_id", "p_stage", "p_input_hash"))
            if "p_payload" in args:
                self.saved[key] = copy.deepcopy(args["p_payload"])
            return SimpleNamespace(data=copy.deepcopy(self.saved.get(key)))
        return SimpleNamespace(execute=execute)


@pytest.mark.asyncio
async def test_stage_resume_invalidation_scope_and_errors():
    db = CheckpointDB()
    scope = dict(db=db, organization_id="org", user_id="user", job_id="job", lease_token="lease")
    cache = ArtifactStageCache(**scope, context={"evidence": "v1"})
    operation = AsyncMock(return_value=({"sections": ["原稿"]}, SimpleNamespace(
        usage={"call_cost": .001}, finish_reason="stop", model_code="fixed", raw_response={"secret": "never-store"},
    )))
    await cache.pair("analysis", operation, request="方案")
    value, response = await cache.pair("analysis", operation, request="方案")
    assert operation.await_count == 1 and cache.hits == 1
    assert response.usage["call_cost"] == .001 and value["sections"] == ["原稿"]
    assert "secret" not in str(db.saved)
    await ArtifactStageCache(**scope, context={"evidence": "v2"}).pair("analysis", operation, request="方案")
    await ArtifactStageCache(**{**scope, "user_id": "other"}).pair("analysis", operation, request="方案")
    assert operation.await_count == 3
    db.denied = True
    with pytest.raises(PermissionError):
        await cache.pair("analysis", operation, request="方案")
    assert operation.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", ["error", "length"])
async def test_incomplete_stage_is_not_cached(finish):
    db = CheckpointDB()
    cache = ArtifactStageCache(db=db, organization_id="o", user_id="u", job_id="j", lease_token="l")
    await cache.pair("section", AsyncMock(return_value=(["partial"], SimpleNamespace(finish_reason=finish))))
    assert not db.saved


def test_checkpoint_migration_has_actor_lease_and_service_guards():
    sql = (Path(__file__).parents[3] / "supabase/migrations/20260909_001_artifact_stage_checkpoints.sql").read_text()
    for token in ("SECURITY INVOKER", "ENABLE ROW LEVEL SECURITY", "created_by = p_user_id", "FOR UPDATE",
                  "lease_expires_at <= now()", "organization_id = p_organization_id", "FROM PUBLIC, anon, authenticated"):
        assert token in sql


@pytest.mark.asyncio
async def test_preview_and_revision_recheck_source_acl_and_version():
    doc_id = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
    version = {"evidence_snapshot": {"records": [{"document_id": doc_id, "source_version": "v1"}]}}
    row = {"id": doc_id, "organization_id": "org", "owner_id": "user", "visibility": "private", "source_version": "v1", "status": "ready"}
    db = DB(documents=[row])
    await require_current_evidence_access(db, "org", "user", version)
    for org, user in (("other", "user"), ("org", "other")):
        with pytest.raises(Exception) as exc:
            await require_current_evidence_access(db, org, user, version)
        assert exc.value.status_code == 409
    row["source_version"] = "v2"
    with pytest.raises(Exception):
        await require_current_evidence_access(db, "org", "user", version)


def test_revision_keeps_requirements_and_resets_approval():
    payload = revision_payload({"id": "a", "title": "方案", "artifact_type": "customer_solution",
        "source_request": "原始要求", "metadata": {"content_contract": {"target_character_count": 3000,
        "delivery_requirements": {"budget": 200}}}}, {}, "完善售后", "revision-key")
    assert payload["delivery_requirements"]["budget"] == 200
    assert payload["revision_of"] == "a" and payload["review_confirmed"] is False
    assert payload["source_content"] == ""  # Worker reads authoritative, permission-checked source.


def test_cost_decimals_and_unknown_cost_are_preserved():
    assert merge_delivery_usage({"call_cost": .0003}, {"call_cost": .0004})["call_cost"] == pytest.approx(.0007)
    assert "call_cost" not in merge_delivery_usage({"total_tokens": 15})
