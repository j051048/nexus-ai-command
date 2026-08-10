"""Tenant knowledge readiness API for solution and tender delivery."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db
from app.core.errors import api_success
from app.services.knowledge_readiness_service import build_knowledge_readiness

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Readiness"])


@router.get("/readiness")
async def get_knowledge_readiness(
    artifact_type: Literal[
        "customer_solution",
        "tender",
        "competitor_analysis",
        "service_proposal",
        "technical_report",
    ] = Query(default="customer_solution"),
    db=Depends(get_request_db),
    organization_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
):
    documents = (
        await db.table("documents")
        .select(
            "id,name,doc_type,status,review_status,source_version,valid_until,"
            "quality_score,indexed_at,readiness_snapshot"
        )
        .eq("organization_id", organization_id)
        .limit(500)
        .execute()
    )
    products = (
        await db.table("instrument_product_catalog")
        .select("id", count="exact")
        .eq("organization_id", organization_id)
        .eq("is_active", True)
        .execute()
    )
    product_count = int(getattr(products, "count", None) or len(products.data or []))
    readiness = build_knowledge_readiness(
        documents.data or [], artifact_type=artifact_type, product_count=product_count
    )
    return api_success(data=readiness)
