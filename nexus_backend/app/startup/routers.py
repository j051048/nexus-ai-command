"""Router imports and registration — organized by business domain."""

from fastapi import FastAPI

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def register_routers(app: FastAPI) -> None:
    """Import and register all routers with the application.

    Domain groups:
      1. AI / Chat          — core AI chat, audio, memories, prompts
      2. CRM / Sales        — customers, competitors, performance, incentive
      3. OA / Workflow       — approval, projects, tasks, attendance, expenses
      4. Documents / KB     — documents, training, knowledge, reports
      5. Organization       — org structure, users, profile, permissions
      6. Finance / Billing  — billing, payments, usage
      7. Assets / Inventory — assets, work orders, inventory, certificates, contracts
      8. IM / Integration   — IM chat, OAuth, callbacks, webhooks, MCP, Kingdee
      9. System / Admin     — super admin, backups, configs, compliance, DSAR
      10. VMD / Optional    — optional routers loaded with try/except
    """

    # ── 1. AI / Chat ──────────────────────────────────────────────────────
    from app.routers import agent_proactive as agent_proactive_router
    from app.routers import (
        analysis,
        audio,
        batch,
        charts,
        chat,
        export,
        files,
        memories,
        metrics,
    )
    from app.routers import chat_upload as chat_upload_router
    from app.routers import saved_prompts as saved_prompts_router
    from app.routers import scheduled_tasks as scheduled_tasks_router
    from app.routers import soul_document as soul_document_router
    from app.routers import ws as ws_router

    app.include_router(chat.router)
    app.include_router(chat_upload_router.router)
    app.include_router(audio.router)
    app.include_router(memories.router)
    app.include_router(metrics.router)
    app.include_router(saved_prompts_router.router)
    app.include_router(soul_document_router.router)
    app.include_router(scheduled_tasks_router.router)
    app.include_router(ws_router.router)
    app.include_router(agent_proactive_router.router)
    app.include_router(export.router)
    app.include_router(charts.router)
    app.include_router(analysis.router)
    app.include_router(files.router)
    app.include_router(batch.router)

    from app.routers import business_context

    app.include_router(business_context.router)

    # ── 2. CRM / Sales ───────────────────────────────────────────────────
    from app.routers import (
        competitors,
        crm,
        dashboard,
        incentive,
        performance,
        sales,
        sales_leads,
    )

    app.include_router(crm.router)
    app.include_router(sales_leads.router)
    app.include_router(sales.router)
    app.include_router(competitors.router)
    app.include_router(performance.router)
    app.include_router(incentive.router)
    app.include_router(dashboard.router)

    # ── 3. OA / Workflow ──────────────────────────────────────────────────
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

    app.include_router(approval.router)
    app.include_router(approval_flows_router.router)
    app.include_router(projects.router)
    app.include_router(workflows.router)
    app.include_router(workflow_templates.router)
    app.include_router(form_schemas.router)
    app.include_router(attendance_router.router)
    app.include_router(expenses_router.router)
    app.include_router(oa.router)

    # ── 4. Documents / Knowledge ──────────────────────────────────────────
    from app.routers import documents, import_data, qa_pairs, reports, training

    app.include_router(documents.router)
    app.include_router(training.router)
    app.include_router(reports.router)
    app.include_router(qa_pairs.router)
    app.include_router(import_data.router)

    # ── 5. Organization / Users ───────────────────────────────────────────
    from app.routers import (
        hr,
        notifications,
        onboarding,
        organization,
        permissions,
        profile,
        users,
    )
    from app.routers import notification_preferences as notification_preferences_router
    from app.routers import org_structure as org_structure_router

    app.include_router(organization.router)
    app.include_router(org_structure_router.router)
    app.include_router(profile.router)
    app.include_router(permissions.router)
    app.include_router(onboarding.router)
    app.include_router(notifications.router)
    app.include_router(notification_preferences_router.router)
    app.include_router(users.router)
    app.include_router(hr.router)

    # ── 6. Finance / Billing ──────────────────────────────────────────────
    from app.routers import billing, finance, payments, usage
    from app.routers import stripe_webhooks as stripe_webhooks_router

    app.include_router(billing.router)
    app.include_router(payments.router)
    app.include_router(stripe_webhooks_router.router)
    app.include_router(usage.router)
    app.include_router(finance.router)

    # ── 7. Assets / Inventory / Contracts ─────────────────────────────────
    from app.routers import assets as assets_router
    from app.routers import certificates as certificates_router
    from app.routers import contracts
    from app.routers import inventory as inventory_router
    from app.routers import work_orders as work_orders_router

    app.include_router(contracts.router)
    app.include_router(assets_router.router)
    app.include_router(work_orders_router.router)
    app.include_router(inventory_router.router)
    app.include_router(certificates_router.router)

    # ── 8. IM / Integration ───────────────────────────────────────────────
    from app.routers import (
        im_callbacks,
        im_chat,
        im_oauth,
        im_settings,
        kingdee,
        oauth,
        plugins,
        push,
        webhooks,
    )
    from app.routers import mcp as mcp_router
    from app.routers import robot as robot_router

    app.include_router(im_chat.router)
    app.include_router(im_oauth.router)
    app.include_router(im_callbacks.router)
    app.include_router(im_settings.router)
    app.include_router(webhooks.router)
    app.include_router(oauth.router)
    app.include_router(push.router)
    app.include_router(plugins.router)
    app.include_router(kingdee.router)
    app.include_router(mcp_router.router)
    app.include_router(robot_router.router)

    # ── 9. System / Admin ─────────────────────────────────────────────────
    from app.routers import (
        api_docs,
        api_keys,
        backups,
        compliance,
        data_transfer,
        super_admin,
    )
    from app.routers import dsar as dsar_router
    from app.routers import system as system_router
    from app.routers import system_configs as system_configs_router

    app.include_router(super_admin.router)
    app.include_router(api_docs.router)
    app.include_router(api_keys.router)
    app.include_router(backups.router)
    app.include_router(compliance.router)
    app.include_router(data_transfer.router)
    app.include_router(system_configs_router.router)
    app.include_router(dsar_router.router)
    app.include_router(system_router.router)

    # ── 10. VMD / LLM Optional Routers ─────────────────────────────
    from app.routers import llm

    app.include_router(llm.router)

    _vmd_modules = [
        "vmd_tasks",
        "vmd_clues",
        "vmd_compliance",
        "vmd_dashboard",
    ]
    for mod_name in _vmd_modules:
        try:
            module = __import__(f"app.routers.{mod_name}", fromlist=["router"])
            app.include_router(module.router)
        except (ImportError, AttributeError):
            logger.debug(f"Router {mod_name} could not be loaded")

    # Extra legacy ones
    for mod_name in ["agent_replay", "onboarding_agent", "admin_traces", "admin_rag"]:
        try:
            module = __import__(f"app.routers.{mod_name}", fromlist=["router"])
            app.include_router(module.router)
        except (ImportError, AttributeError):
            pass
