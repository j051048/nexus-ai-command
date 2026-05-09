"""Router registration entrypoint organized by business domain."""

from __future__ import annotations

from fastapi import FastAPI

from app.startup.route_groups import (
    register_ai_routes,
    register_asset_routes,
    register_crm_sales_routes,
    register_document_routes,
    register_finance_routes,
    register_integration_routes,
    register_optional_routes,
    register_organization_routes,
    register_system_routes,
    register_workflow_routes,
)


def register_routers(app: FastAPI) -> None:
    """Import and register all routers with explicit domain boundaries."""
    register_ai_routes(app)
    register_crm_sales_routes(app)
    register_workflow_routes(app)
    register_document_routes(app)
    register_organization_routes(app)
    register_finance_routes(app)
    register_asset_routes(app)
    register_integration_routes(app)
    register_system_routes(app)
    register_optional_routes(app)
