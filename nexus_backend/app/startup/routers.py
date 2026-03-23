"""Router imports and registration."""

from fastapi import FastAPI

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def register_routers(app: FastAPI) -> None:
    """Import and register all routers with the application."""

    # --- Standard routers (direct imports) ---
    from app.routers import (
        api_docs,
        api_keys,
        approval,
        audio,
        backups,
        billing,
        chat,
        compliance,
        competitors,
        contracts,
        crm,
        dashboard,
        data_transfer,
        documents,
        form_schemas,
        im_callbacks,
        im_chat,
        im_oauth,
        im_settings,
        import_data,
        incentive,
        kingdee,
        memories,
        notifications,
        oauth,
        onboarding,
        organization,
        payments,
        performance,
        permissions,
        plugins,
        profile,
        projects,
        push,
        qa_pairs,
        reports,
        super_admin,
        training,
        usage,
        webhooks,
        workflow_templates,
        workflows,
    )
    from app.routers import notification_preferences as notification_preferences_router
    from app.routers import approval_flows as approval_flows_router
    from app.routers import assets as assets_router
    from app.routers import attendance as attendance_router
    from app.routers import certificates as certificates_router
    from app.routers import dsar as dsar_router
    from app.routers import expenses as expenses_router
    from app.routers import inventory as inventory_router
    from app.routers import mcp as mcp_router
    from app.routers import org_structure as org_structure_router
    from app.routers import robot as robot_router
    from app.routers import scheduled_tasks as scheduled_tasks_router
    from app.routers import stripe_webhooks as stripe_webhooks_router
    from app.routers import system_configs as system_configs_router
    from app.routers import work_orders as work_orders_router
    from app.routers import ws as ws_router
    from app.routers import saved_prompts as saved_prompts_router
    from app.routers import chat_upload as chat_upload_router
    from app.routers import soul_document as soul_document_router

    app.include_router(performance.router)
    app.include_router(incentive.router)
    app.include_router(approval.router)
    app.include_router(kingdee.router)
    app.include_router(chat.router)
    app.include_router(chat_upload_router.router)
    app.include_router(audio.router)
    app.include_router(documents.router)
    app.include_router(projects.router)
    app.include_router(usage.router)
    app.include_router(organization.router)
    app.include_router(import_data.router)
    app.include_router(qa_pairs.router)
    app.include_router(webhooks.router)
    app.include_router(oauth.router)
    app.include_router(compliance.router)
    app.include_router(billing.router)
    app.include_router(profile.router)
    app.include_router(mcp_router.router)
    app.include_router(robot_router.router)
    app.include_router(workflows.router)
    app.include_router(form_schemas.router)
    app.include_router(push.router)
    app.include_router(im_oauth.router)
    app.include_router(im_callbacks.router)
    app.include_router(im_chat.router)
    app.include_router(im_settings.router)
    app.include_router(permissions.router)
    app.include_router(workflow_templates.router)
    app.include_router(memories.router)
    app.include_router(reports.router)
    app.include_router(notifications.router)
    app.include_router(notification_preferences_router.router)
    app.include_router(payments.router)
    app.include_router(data_transfer.router)
    app.include_router(plugins.router)
    app.include_router(training.router)
    app.include_router(contracts.router)
    app.include_router(competitors.router)
    app.include_router(super_admin.router)
    app.include_router(crm.router)
    app.include_router(api_docs.router)
    app.include_router(backups.router)
    app.include_router(api_keys.router)
    app.include_router(onboarding.router)
    app.include_router(ws_router.router)
    app.include_router(scheduled_tasks_router.router)
    app.include_router(dashboard.router)
    app.include_router(system_configs_router.router)
    app.include_router(org_structure_router.router)
    app.include_router(assets_router.router)
    app.include_router(work_orders_router.router)
    app.include_router(attendance_router.router)
    app.include_router(expenses_router.router)
    app.include_router(inventory_router.router)
    app.include_router(certificates_router.router)
    app.include_router(approval_flows_router.router)
    app.include_router(stripe_webhooks_router.router)
    app.include_router(dsar_router.router)
    app.include_router(saved_prompts_router.router)
    app.include_router(soul_document_router.router)

    # --- Optional routers (try/except to avoid all-or-nothing failure) ---

    # Item 45: Agent Replay Engine
    try:
        from app.routers import agent_replay as agent_replay_router

        app.include_router(agent_replay_router.router)
    except ImportError:
        logger.debug("agent_replay router not available, skipping")

    # Item 54: Onboarding Agent
    try:
        from app.routers import onboarding_agent as onboarding_agent_router

        app.include_router(onboarding_agent_router.router)
    except ImportError:
        logger.debug("onboarding_agent router not available, skipping")

    # VMD (Virtual Marketing Department) routers
    _optional_vmd_routers = [
        ("llm_models", "llm_models"),
        ("vmd_tasks", "vmd_tasks"),
        ("vmd_compliance", "vmd_compliance"),
        ("vmd_clues", "vmd_clues"),
        ("vmd_dashboard", "vmd_dashboard"),
        ("admin_traces", "admin_traces"),
        ("admin_rag", "admin_rag"),
        ("ai_feedback", "ai_feedback"),
    ]
    for module_name, label in _optional_vmd_routers:
        try:
            module = __import__(f"app.routers.{module_name}", fromlist=["router"])
            app.include_router(module.router)
        except ImportError:
            logger.debug(f"{label} router not available, skipping")
