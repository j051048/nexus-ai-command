"""Domain-oriented router registration helpers."""

from __future__ import annotations

from fastapi import FastAPI

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def register_ai_routes(app: FastAPI) -> None:
    from app.routers import (
        agent_observability,
        ai_feedback,
        analysis,
        audio,
        batch,
        business_context,
        charts,
        chat,
        export,
        files,
        memories,
        metrics,
    )
    from app.routers import agent_proactive as agent_proactive_router
    from app.routers import chat_upload as chat_upload_router
    from app.routers import saved_prompts as saved_prompts_router
    from app.routers import scheduled_tasks as scheduled_tasks_router
    from app.routers import soul_document as soul_document_router
    from app.routers import ws as ws_router

    for router in [
        chat.router,
        chat_upload_router.router,
        audio.router,
        memories.router,
        metrics.router,
        saved_prompts_router.router,
        soul_document_router.router,
        scheduled_tasks_router.router,
        ws_router.router,
        agent_proactive_router.router,
        agent_observability.router,
        ai_feedback.router,
        ai_feedback.router_v1,
        export.router,
        charts.router,
        analysis.router,
        files.router,
        batch.router,
        business_context.router,
    ]:
        app.include_router(router)


def register_crm_sales_routes(app: FastAPI) -> None:
    from app.routers import (
        competitors,
        crm,
        dashboard,
        incentive,
        performance,
        sales,
        sales_leads,
    )

    for router in [
        crm.router,
        sales_leads.router,
        sales.router,
        competitors.router,
        performance.router,
        incentive.router,
        dashboard.router,
    ]:
        app.include_router(router)


def register_workflow_routes(app: FastAPI) -> None:
    from app.routers import (
        approval,
        form_schemas,
        oa,
        projects,
        workflow_templates,
        workflows,
    )
    from app.routers import approval_flows as approval_flows_router
    from app.routers import attendance as attendance_router
    from app.routers import expenses as expenses_router

    for router in [
        approval.router,
        approval_flows_router.router,
        projects.router,
        workflows.router,
        workflow_templates.router,
        form_schemas.router,
        attendance_router.router,
        expenses_router.router,
        oa.router,
    ]:
        app.include_router(router)


def register_document_routes(app: FastAPI) -> None:
    from app.routers import (
        documents,
        industry_knowledge,
        import_data,
        qa_pairs,
        report_engine,
        reports,
        training,
    )

    for router in [
        documents.router,
        industry_knowledge.router,
        training.router,
        reports.router,
        qa_pairs.router,
        import_data.router,
        report_engine.router,
    ]:
        app.include_router(router)


def register_organization_routes(app: FastAPI) -> None:
    from app.routers import (
        hr,
        inbox,
        notifications,
        onboarding,
        organization,
        permissions,
        profile,
        users,
    )
    from app.routers import notification_preferences as notification_preferences_router
    from app.routers import org_structure as org_structure_router

    for router in [
        organization.router,
        inbox.router,
        org_structure_router.router,
        profile.router,
        permissions.router,
        onboarding.router,
        notifications.router,
        notification_preferences_router.router,
        users.router,
        hr.router,
    ]:
        app.include_router(router)


def register_finance_routes(app: FastAPI) -> None:
    from app.routers import billing, finance, payments, usage
    from app.routers import stripe_webhooks as stripe_webhooks_router

    for router in [
        billing.router,
        payments.router,
        stripe_webhooks_router.router,
        usage.router,
        finance.router,
    ]:
        app.include_router(router)


def register_asset_routes(app: FastAPI) -> None:
    from app.routers import assets as assets_router
    from app.routers import certificates as certificates_router
    from app.routers import contracts
    from app.routers import inventory as inventory_router
    from app.routers import work_orders as work_orders_router

    for router in [
        contracts.router,
        assets_router.router,
        work_orders_router.router,
        inventory_router.router,
        certificates_router.router,
    ]:
        app.include_router(router)


def register_integration_routes(app: FastAPI) -> None:
    from app.routers import (
        ai_assistant,
        enterprise_sso,
        gdpr,
        im_callbacks,
        im_chat,
        im_oauth,
        im_settings,
        kingdee,
        oauth,
        plugins,
        push,
        webhooks,
        workflow_analytics,
    )
    from app.routers import mcp as mcp_router
    from app.routers import robot as robot_router

    for router in [
        ai_assistant.router,
        gdpr.router,
        workflow_analytics.router,
        im_chat.router,
        im_oauth.router,
        im_callbacks.router,
        im_settings.router,
        webhooks.router,
        oauth.router,
        enterprise_sso.router,
        push.router,
        plugins.router,
        kingdee.router,
        mcp_router.router,
        robot_router.router,
        robot_router.router_wecom,
    ]:
        app.include_router(router)


def register_system_routes(app: FastAPI) -> None:
    from app.routers import (
        api_docs,
        api_keys,
        backups,
        compliance,
        compliance_evidence,
        data_transfer,
        deployment_health,
        super_admin,
    )
    from app.routers import dsar as dsar_router
    from app.routers import intent_rules as intent_rules_router
    from app.routers import system as system_router
    from app.routers import system_configs as system_configs_router

    for router in [
        super_admin.router,
        intent_rules_router.router,
        api_docs.router,
        api_keys.router,
        backups.router,
        compliance.router,
        compliance_evidence.router,
        data_transfer.router,
        deployment_health.router,
        system_configs_router.router,
        dsar_router.router,
        system_router.router,
    ]:
        app.include_router(router)


def register_optional_routes(app: FastAPI) -> None:
    from app.routers import llm

    app.include_router(llm.router)

    for mod_name in [
        "vmd_tasks",
        "vmd_clues",
        "vmd_compliance",
        "vmd_dashboard",
        "agent_replay",
        "onboarding_agent",
        "admin_traces",
        "admin_rag",
    ]:
        try:
            module = __import__(f"app.routers.{mod_name}", fromlist=["router"])
            app.include_router(module.router)
        except (ImportError, AttributeError):
            logger.debug("Router %s could not be loaded", mod_name)
