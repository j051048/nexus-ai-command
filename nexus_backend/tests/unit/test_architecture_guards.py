"""Static architecture guardrails for P0 platform regressions."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_celery_registers_isolated_tool_tasks():
    content = read("nexus_backend/app/core/celery_app.py")
    assert '"app.tasks.tool_tasks"' in content
    assert "agent_tools_high_risk" in content
    assert "worker_prefetch_multiplier=1" in content


def test_browser_ai_proxy_fallback_is_policy_gated():
    content = read("src/hooks/useAIStream.ts")
    assert "VITE_ENABLE_BROWSER_AI_PROXY_FALLBACK" in content
    assert "Browser-side AI proxy fallback is disabled by policy" in content


def test_pwa_precache_is_bounded():
    content = read("vite.config.ts")
    assert "maximumFileSizeToCacheInBytes" in content
    assert "vendor-syntax" in content


def test_static_rls_scanner_covers_common_tenant_columns():
    content = read("scripts/scan_rls_coverage.py")
    assert "organization_id" in content
    assert "org_id" in content
    assert "tenant_id" in content


def test_agent_run_observability_is_durable():
    graph = read("nexus_backend/app/agent/graph.py")
    stream = read("nexus_backend/app/agent/stream.py")
    execute = read("nexus_backend/app/agent/node_execute.py")
    migration = read("supabase/migrations/20260507_p1_agent_run_observability.sql")
    assert "agent_run_observer.start_run" in graph
    assert "agent_run_observer.finish_run" in stream
    assert "agent_run_observer.tool_call" in execute
    assert "agent_runs" in migration
    assert "agent_tool_calls" in migration
    assert "agent_events" in migration


def test_production_requires_durable_state_and_redis():
    content = read("nexus_backend/app/core/config.py")
    checkpointer = read("nexus_backend/app/agent/checkpointer.py")
    assert "LANGGRAPH_CHECKPOINTER must be 'postgres'" in content
    assert "REDIS_URL is required in production" in content
    assert "PostgreSQL LangGraph checkpointer failed in production" in checkpointer


def test_sse_client_has_backpressure_bounds():
    content = read("src/hooks/useAIStream.ts")
    assert "MAX_SSE_BUFFER_CHARS" in content
    assert "reader.cancel()" in content


def test_tool_rag_has_operator_controls():
    binding = read("nexus_backend/app/agent/plan/tool_binding.py")
    index = read("nexus_backend/app/agent/tool_embedding_index.py")
    router = read("nexus_backend/app/routers/chat.py")
    assert "tool_embedding_index.retrieve" in binding
    assert "def stats" in index
    assert "async def refresh" in index
    assert "/tools/governance" in router
    assert "/tools/rag/refresh" in router


def test_agent_run_management_api_is_org_scoped():
    router = read("nexus_backend/app/routers/agent_observability.py")
    database = read("nexus_backend/app/core/database.py")
    startup = read("nexus_backend/app/startup/route_groups.py")
    assert 'prefix="/api/agent-runs"' in router
    assert "get_current_org_id" in router
    assert "agent_runs" in router
    assert "agent_tool_calls" in router
    assert "agent_events" in router
    assert "require_agent_ops" in router
    assert "/{run_ref}/replay" in router
    assert '"agent_runs"' in database
    assert '"agent_tool_calls"' in database
    assert '"agent_events"' in database
    assert "agent_observability.router" in startup


def test_operator_frontend_pages_are_routed():
    lazy_imports = read("src/routes/lazyImports.ts")
    admin_routes = read("src/routes/adminRoutes.tsx")
    agent_page = read("src/pages/AgentRunsPage.tsx")
    tool_page = read("src/pages/ToolGovernancePage.tsx")
    assert "AgentRunsPage" in lazy_imports
    assert "ToolGovernancePage" in lazy_imports
    assert 'path="agent-runs"' in admin_routes
    assert 'path="tools/governance"' in admin_routes
    assert "/api/agent-runs" in agent_page
    assert "/api/usage/cost-alerts" in agent_page
    assert "replaySelected" in agent_page
    assert "TraceTopology" in agent_page
    assert "/api/tools/governance" in tool_page
    assert "/api/tools/rag/evaluate" in tool_page
    assert "fix_suggestions" in tool_page


def test_staging_migration_verifier_covers_critical_tables():
    script = read("scripts/verify_staging_migrations.py")
    ci = read(".github/workflows/ci.yml")
    assert "CRITICAL_TABLES" in script
    assert "agent_runs" in script
    assert "agent_tool_calls" in script
    assert "agent_events" in script
    assert "webhook_delivery_log" in script
    assert "vmd_reports" in script
    assert "row level security is not enabled" in script
    assert "Staging Migration Verification" in ci
    assert "--require-db" in ci


def test_cost_tool_plugin_and_deploy_governance_are_wired():
    usage = read("nexus_backend/app/routers/usage.py")
    chat = read("nexus_backend/app/routers/chat.py")
    plugins = read("nexus_backend/app/routers/plugins.py")
    deploy = read("nexus_backend/app/routers/deployment_health.py")
    startup = read("nexus_backend/app/startup/route_groups.py")
    doctor = read("scripts/private_deploy_doctor.py")
    assert "/cost-alerts" in usage
    assert "model_cost_concentration" in usage
    assert "/tools/governance/fix-plan" in chat
    assert "/tools/rag/evaluate" in chat
    assert "_plugin_governance" in plugins
    assert "/governance" in plugins
    assert 'prefix="/api/system/deployment-health"' in deploy
    assert "deployment_health.router" in startup
    assert "private deployment doctor" in doctor.lower()


def test_llm_gateway_has_ab_routing_policy():
    dispatch = read("nexus_backend/app/services/llm_gateway/chat_dispatch.py")
    policy = read("nexus_backend/app/services/llm_gateway/routing_policy.py")
    assert "choose_model_variant" in dispatch
    assert "LLM_ENABLE_AB_ROUTING" in policy
    assert "LLM_AB_ECONOMY_MODEL" in policy


def test_prompt_context_harness_is_wired_to_ops():
    prompt_registry = read("nexus_backend/app/core/prompts_registry.py")
    prompt_builder = read("nexus_backend/app/agent/plan/prompt_builder.py")
    stream = read("nexus_backend/app/agent/stream.py")
    agent_runs = read("nexus_backend/app/routers/agent_observability.py")
    replay = read("nexus_backend/app/routers/agent_replay.py")
    frontend = read("src/pages/AgentRunsPage.tsx")
    celery = read("nexus_backend/app/core/celery_app.py")
    assert "_install_clean_runtime_prompts" in prompt_registry
    assert "get_prompt_manifest" in prompt_registry
    assert "prompt_snapshot" in prompt_builder
    assert "context_ledger" in prompt_builder
    assert "cost_attribution" in stream
    assert "/prompt-lint" in agent_runs
    assert "/quality/trends" in agent_runs
    assert "/shadow-eval" in agent_runs
    assert "/context-ablation" in agent_runs
    assert "promote_failures_to_eval_cases" in replay
    assert "agent_eval_cases" in replay
    assert "promote-agent-failures-to-evals" in celery
    assert "Prompt Lint" in frontend
    assert "Eval 标注队列" in frontend


def test_first_launch_saas_guards_are_enforced():
    flags = read("src/config/featureFlags.ts")
    payment_service = read("nexus_backend/app/services/payment_service.py")
    payments_router = read("nexus_backend/app/routers/payments.py")
    payment_page = read("src/pages/PaymentPage.tsx")
    readiness = read("scripts/production_readiness_check.mjs")
    env_example = read(".env.production.example")

    small_profile = flags.split("SMALL_COMPANY_LAUNCH_MODULES", 1)[1].split("];", 1)[0]
    assert '"workflow_designer"' in small_profile
    assert '"oa"' in small_profile
    assert '"crm"' in small_profile
    assert '"dev_tools"' not in small_profile
    assert "EXTENDED_LAUNCH_MODULES" in flags
    assert "VITE_LAUNCH_PROFILE" in flags
    assert "CUSTOMER_LAUNCH_ENABLED_MODULES" in flags
    assert "CUSTOMER_LAUNCH_DISABLED_MODULES" in flags
    assert "PAYMENT_ENABLE_WECHAT_SANDBOX" in payment_service
    assert "PAYMENT_ENABLE_ALIPAY_SANDBOX" in payment_service
    assert "该支付渠道尚未在生产环境启用" in payment_service
    assert "/methods" in payments_router
    assert "首发生产环境仅开放对公转账" in payment_page
    assert "customer launch modules enabled" in readiness
    assert "small-company launch profile" in readiness
    assert "developer tools disabled" in readiness
    assert "VITE_LAUNCH_PROFILE=small_company" in env_example
    assert "workflow_designer" in env_example
    assert "oa" in env_example
    assert "VITE_DISABLED_MODULES=dev_tools" in env_example


def test_customer_launch_integrations_are_not_mocked():
    kingdee = read("nexus_backend/app/routers/kingdee.py")
    plugin_service = read("nexus_backend/app/services/plugin_marketplace_service.py")
    plugin_page = read("src/pages/PluginMarketplace.tsx")
    main = read("nexus_backend/app/main.py")
    api_docs = read("nexus_backend/app/core/api_docs.py")
    env_example = read(".env.production.example")

    assert 'tags=["Kingdee"]' in kingdee
    assert "Kingdee Mock" not in kingdee
    assert "httpx.AsyncClient" in kingdee
    assert "KINGDEE_BASE_URL" in kingdee
    assert "KINGDEE_API_KEY" in kingdee
    assert "INTEGRATION_CONNECT_FAILED" in kingdee
    assert "metadata_source" in plugin_service
    assert '"rating": None' in plugin_service
    assert '"downloads": 0' in plugin_service
    assert "伪造下载/评分指标" in plugin_page
    assert "renderStars" not in plugin_page
    assert "Kingdee Mock" not in main
    assert "Kingdee Mock" not in api_docs
    assert "KINGDEE_BASE_URL=" in env_example


def test_router_registration_is_domain_split():
    startup = read("nexus_backend/app/startup/routers.py")
    groups = read("nexus_backend/app/startup/route_groups.py")
    assert "register_crm_sales_routes" in startup
    assert "register_finance_routes" in startup
    assert "register_system_routes" in startup
    assert "def register_crm_sales_routes" in groups
    assert "def register_finance_routes" in groups
    assert "def register_optional_routes" in groups


def test_p0_production_container_is_build_time_installed():
    dockerfile = read("Dockerfile")
    compose = read("docker-compose.yml")
    assert "COPY nexus_backend/requirements.txt" in dockerfile
    assert "pip install --no-cache-dir" in dockerfile
    assert "USER appuser" in dockerfile
    assert "pip install -e ." not in compose
    assert "dockerfile: Dockerfile" in compose


def test_p0_vector_index_and_rls_policy_scanner_are_enforced():
    vector_migration = read(
        "supabase/migrations/20260514_p0_document_embeddings_vector_index.sql"
    )
    rls_migration = read(
        "supabase/migrations/20260514_p0_tenant_rls_policy_backfill.sql"
    )
    scanner = read("scripts/scan_rls_coverage.py")
    ci = read(".github/workflows/ci.yml")
    assert "USING hnsw (embedding vector_cosine_ops)" in vector_migration
    assert "USING ivfflat (embedding vector_cosine_ops)" in vector_migration
    assert "current_tenant_id_text" in rls_migration
    assert "SECURITY DEFINER" in rls_migration
    assert "CREATE POLICY p0_chat_messages_tenant_isolation" in rls_migration
    assert "MISSING_POLICY" in scanner
    assert "_collect_policy_tables" in scanner
    assert "Run static RLS coverage scanner" in ci


def test_p0_audit_logs_are_immutable():
    audit = read("supabase/migrations/20260419_p1_audit_logs_immutable.sql")
    assert "prevent_audit_log_mutation" in audit
    assert "BEFORE UPDATE OR DELETE ON public.audit_logs" in audit
    assert "audit_logs_immutable" in audit


def test_p0_celery_queue_backlog_alert_is_wired():
    monitor = read("nexus_backend/app/core/celery_queue_monitor.py")
    metrics = read("nexus_backend/app/core/metrics.py")
    deploy = read("nexus_backend/app/routers/deployment_health.py")
    env_example = read(".env.production.example")
    assert "CELERY_QUEUE_DEPTH_WARNING" in monitor
    assert "CELERY_QUEUE_DEPTH_CRITICAL" in monitor
    assert "observe_celery_queue_depth" in monitor
    assert "celery_queue_depth" in metrics
    assert "collect_celery_queue_health" in deploy
    assert "CELERY_MONITORED_QUEUES" in env_example


def test_p0_irreversible_tools_always_reach_critic():
    graph = read("nexus_backend/app/agent/graph.py")
    critic = read("nexus_backend/app/agent/node_reflect.py")
    assert "Irreversible tool succeeded + user confirmed" not in graph
    assert "return \"synthesize\"" not in graph.split("if _has_irreversible_tool(state):", 1)[1].split("logger.info(f\"[Graph] All tools succeeded", 1)[0]
    assert "Irreversible tool detected after reflect" in graph
    assert "and not has_irreversible_tool(state)" in critic


def test_p0_customer_launch_modules_have_owner_and_smoke_coverage():
    metadata = read("src/config/customerLaunchModules.ts")
    readiness = read("scripts/production_readiness_check.mjs")
    smoke = read("e2e/top10-critical-flows.spec.ts")
    flags = read("src/config/featureFlags.ts")

    enabled_section = flags.split("SMALL_COMPANY_LAUNCH_MODULES", 1)[1].split("];", 1)[0]
    modules = [
        line.split('"')[1]
        for line in enabled_section.splitlines()
        if '"' in line
    ]
    for module in modules:
        assert f'flag: "{module}"' in metadata
    assert "owner:" in metadata
    assert "smokePath:" in metadata
    for route in [
        "/login",
        "/crm",
        "/approval",
        "/documents",
        "/knowledge",
        "/vmd",
        "/plugins",
        "/reports",
        "/finance",
        "/workflows",
    ]:
        assert route in smoke
    assert "launch metadata:" in readiness
    assert "golden smoke route:" in readiness


def test_customer_acceptance_and_handoff_gates_are_wired():
    acceptance = read("scripts/customer_acceptance_gate.py")
    handoff = read("scripts/generate_customer_handoff.py")
    criteria = read("docs/CUSTOMER_ACCEPTANCE_CRITERIA.md")
    readiness = read("scripts/production_readiness_check.mjs")
    release_gate = read("scripts/release_quality_gate.py")
    evidence = read("scripts/collect_release_evidence.py")

    assert "SMALL_COMPANY_MODULES" in acceptance
    assert "Tool RBAC" in acceptance
    assert "Irreversible HITL" in acceptance
    assert "customer-handoff.md" in handoff
    assert "Required Acceptance Commands" in handoff
    assert "Default Launch Profile" in criteria
    assert "Acceptance Rules" in criteria
    assert "scripts/customer_acceptance_gate.py" in readiness
    assert "scripts/generate_customer_handoff.py" in readiness
    assert "customer acceptance gate" in release_gate
    assert "customer handoff generator" in release_gate
    assert "CUSTOMER_ACCEPTANCE_CRITERIA.md" in evidence


def test_p0_customer_visible_placeholder_language_is_removed():
    files = [
        "nexus_backend/app/tools/hr_tools.py",
        "nexus_backend/app/tools/finance_tools.py",
        "nexus_backend/app/tools/_shared.py",
        "nexus_backend/app/services/crawler_service.py",
        "nexus_backend/app/services/vector_service.py",
        "src/components/dashboard/EmployeeDashboard.tsx",
        "src/components/onboarding/OnboardingWizard.tsx",
        "src/components/admin/EmployeeDetail.tsx",
    ]
    forbidden = [
        "暂未开通",
        "暂未启用",
        "占位提示",
        "nexus-user-1",
        "已发送面试邀请",
        "已添加到您的日程",
        "暂未开放",
        "(Mock)",
        "模拟数据",
    ]
    for file in files:
        content = read(file)
        for token in forbidden:
            assert token not in content, f"{token} should not appear in {file}"
    assert "VITE_ENABLE_DEMO_DATA=false" in read(".env.production.example")


def test_p1_idempotency_has_bounded_memory_fallback():
    middleware = read("nexus_backend/app/core/idempotency_middleware.py")
    config = read("nexus_backend/app/core/config.py")
    env_example = read(".env.production.example")

    assert "IDEMPOTENCY_TTL_SECONDS" in middleware
    assert "IDEMPOTENCY_MEMORY_FALLBACK_MAX" in middleware
    assert "IDEMPOTENCY_MEMORY_FALLBACK_TTL_SECONDS" in middleware
    assert "def _prune_memory_cache" in middleware
    assert "X-Idempotency-Store" in middleware
    assert "process-local memory fallback" in middleware
    assert "IDEMPOTENCY_MEMORY_FALLBACK_MAX" in config
    assert "IDEMPOTENCY_MEMORY_FALLBACK_TTL_SECONDS" in env_example


def test_p1_streaming_usage_fallback_uses_token_counter():
    adapter = read("nexus_backend/app/services/llm_adapters/openai_compatible.py")
    gateway = read("nexus_backend/app/services/llm_gateway/chat_dispatch.py")

    assert "def _estimate_stream_usage" in adapter
    assert "token_counter.estimate_prompt_tokens" in adapter
    assert '"estimated": True' in adapter
    assert "usage = (" in adapter
    assert "tools=tools if config.supports_tools else None" in gateway
    assert "from app.services.token_service import token_counter" in gateway


def test_p1_route_level_suspense_and_error_boundaries_are_wired():
    boundary = read("src/components/common/ModuleRouteBoundary.tsx")
    core_routes = read("src/routes/coreRoutes.tsx")
    business_routes = read("src/routes/businessRoutes.tsx")
    admin_routes = read("src/routes/adminRoutes.tsx")
    vmd_routes = read("src/routes/vmdRoutes.tsx")

    assert "Suspense" in boundary
    assert "ModuleErrorBoundary" in boundary
    assert "ModuleRouteSkeleton" in boundary
    for route_file in [core_routes, business_routes, admin_routes, vmd_routes]:
        assert "ModuleRouteBoundary" in route_file


def test_p2_cost_report_rpc_and_daily_usage_migration_are_managed():
    migration = read("supabase/migrations/20260514_p2_cost_report_rpc.sql")
    early_table = read("supabase/migrations/20260405_p03_performance_indexes.sql")
    token_service = read("nexus_backend/app/services/token_service.py")

    assert "CREATE TABLE IF NOT EXISTS public.user_token_usage" in migration
    assert "CREATE TABLE IF NOT EXISTS public.user_token_usage" in early_table
    assert "CREATE OR REPLACE FUNCTION public.upsert_daily_token_usage" in migration
    assert "CREATE OR REPLACE FUNCTION public.get_cost_report" in migration
    assert "SECURITY DEFINER" in migration
    assert "SET search_path = public" in migration
    assert "upsert_daily_token_usage" in token_service
    assert "get_cost_report" in token_service


def test_p2_tool_development_guide_defines_required_governance_metadata():
    guide = read("docs/TOOL_DEVELOPMENT_GUIDE.md")
    registry = read("nexus_backend/app/tools/registry.py")

    for token in [
        "required_role",
        "risk",
        "owner",
        "timeout_s",
        "idempotent",
        "side_effect",
        "is_irreversible=True",
        "Tool RAG",
    ]:
        assert token in guide
        if token != "is_irreversible=True" and token != "Tool RAG":
            assert token in registry


def test_p2_wbs_validation_is_blocking_by_contract():
    wbs = read("nexus_backend/app/agent/nodes_wbs.py")

    assert "Blocking: any warning prevents orchestration" in wbs
    assert "WBS validation failed" in wbs
    assert "raise ValueError(\"WBS validation failed:" in wbs


def test_p2_chat_formbuilder_is_lazy_only():
    chat = read("src/components/ai/chat/ChatMessageList.tsx")
    genui = read("src/components/ai/GenUIContainer.tsx")

    assert "const FormBuilder = React.lazy" in chat
    assert "import FormBuilder from '../genui/FormBuilder'" not in chat
    assert "FormBuilder: lazyWithRetry" in genui


def test_p0_p2_release_quality_gate_is_wired():
    gate = read("scripts/release_quality_gate.py")
    readiness = read("scripts/production_readiness_check.mjs")
    ci = read(".github/workflows/ci.yml")
    soc2 = read("docs/SOC2_CONTROLS.md")

    for token in [
        "P0",
        "P1",
        "P2",
        "SOC2_CONTROLS.md",
        "enterprise_sso",
        "api_key_middleware",
        "tool_rbac",
        "test_fuzz_api.py",
    ]:
        assert token in gate
    assert "Run P0-P2 release quality gate" in ci
    assert "python scripts/release_quality_gate.py" in ci
    assert "scripts/release_quality_gate.py" in readiness
    assert "docs/SOC2_CONTROLS.md" in readiness
    assert "20260514_p2_cost_report_rpc.sql" in readiness
    assert "CC6" in soc2
    assert "CC7" in soc2


def test_p3_p6_sustained_quality_controls_are_wired():
    http_client = read("src/lib/httpClient.ts")
    bundle = read("scripts/check_bundle_budget.mjs")
    package = read("package.json")
    ci = read(".github/workflows/ci.yml")
    doctor = read("scripts/private_deploy_doctor.py")
    evidence = read("scripts/collect_release_evidence.py")
    gate = read("scripts/release_quality_gate.py")
    readiness = read("scripts/production_readiness_check.mjs")

    assert "import { supabase }" in http_client
    assert "await import('@/integrations/supabase/client')" not in http_client
    assert "maxJsChunkBytes" in bundle
    assert "vendor-jspdf-" in bundle
    assert "vendor-html2canvas-" in bundle
    assert '"check:bundle"' in package
    assert "Check bundle budget" in ci
    assert "npm run check:bundle" in ci
    assert "--env" in doctor
    assert "PRIVATE_DEPLOYMENT" in doctor
    assert "CORS_ORIGINS" in doctor
    assert "release-evidence.json" in evidence
    assert "sha256" in evidence
    assert "<redacted>" in evidence
    for level in ["P3", "P4", "P5", "P6"]:
        assert level in gate
    assert "scripts/check_bundle_budget.mjs" in readiness
    assert "scripts/collect_release_evidence.py" in readiness


def test_opus_p0_p2_recommendations_are_wired():
    stream = read("nexus_backend/app/agent/stream.py")
    lifecycle = read("nexus_backend/app/agent/stream_lifecycle.py")
    gateway = read("nexus_backend/app/services/llm_gateway/__init__.py")
    prompt_firewall = read("nexus_backend/app/core/prompt_firewall.py")
    main = read("nexus_backend/app/main.py")
    metrics_router = read("nexus_backend/app/routers/metrics.py")
    metrics_core = read("nexus_backend/app/core/metrics.py")
    web_vitals = read("src/lib/webVitals.ts")
    app = read("src/App.tsx")
    theme = read("src/contexts/ThemeContext.tsx")
    main_tsx = read("src/main.tsx")
    lazy_imports = read("src/routes/lazyImports.ts")
    admin_routes = read("src/routes/adminRoutes.tsx")
    pgbouncer = read("docs/PRIVATE_DEPLOYMENT_PGBOUNCER.md")

    assert "from app.agent.stream_lifecycle import" in stream
    assert "emit_error_and_cleanup" in stream
    assert "cleanup_on_disconnect" in stream
    assert "filter_think_content" in stream
    assert "agent_trace_service.end_trace" in lifecycle

    get_llm_body = gateway.split("def get_llm(", 1)[1]
    assert "requires resolved_config" in get_llm_body
    assert "settings.OPENAI_API_KEY" not in get_llm_body
    assert "settings.AI_BASE_URL" not in get_llm_body
    assert "resolve_model_config" in prompt_firewall

    assert '"/health/live"' in main
    assert '"/health/ready"' in main
    assert "Kubernetes readiness probe" in main
    assert "/api/metrics/web-vitals" in web_vitals
    assert "observe_web_vital" in metrics_router
    assert '"/slo"' in metrics_router
    assert "WEB_VITALS_VALUE" in metrics_core

    assert "React.StrictMode" in main_tsx
    assert "<ThemeProvider>" not in app
    assert "createContext" not in theme
    assert "useEnhancedTheme" in theme

    assert "SLODashboard" in lazy_imports
    assert 'path="slo"' in admin_routes
    assert "SUPABASE_DB_POOLER_URL" in pgbouncer
    assert "pool_mode" in pgbouncer


def test_customer_acceptance_e2e_has_stable_auth_and_chat_contracts():
    acceptance = read("e2e/customer-business-acceptance.spec.ts")
    sidebar = read("src/components/layout/Sidebar.tsx")
    chat_input = read("src/components/ai/chat/ChatInputArea.tsx")
    app = read("src/App.tsx")

    assert "mockLoggedInState(page, role)" in acceptance
    assert "setupAcceptanceMocks(page, 'employee')" in acceptance
    assert "toHaveURL(/\\/dashboard/" in acceptance
    assert 'data-testid="sidebar-main"' in sidebar
    assert "<textarea" in chat_input
    assert 'data-testid="chat-input"' in chat_input
    assert 'return <Navigate to="/dashboard" replace />' in app


def test_auth_and_prompt_firewall_regressions_have_direct_tests():
    auth = read("nexus_backend/app/core/auth.py")
    firewall = read("nexus_backend/app/core/prompt_firewall.py")
    auth_test = read("nexus_backend/tests/unit/test_auth_org_context.py")
    firewall_test = read("nexus_backend/tests/unit/test_prompt_firewall_fast_path.py")

    assert "Missing valid authentication for tenant context" in auth
    assert "auth_failed" in auth
    assert "len(text) > self._config.max_input_length" in firewall
    assert 'v.layer == "context_overflow"' in firewall
    assert "test_missing_org_without_auth_is_401" in auth_test
    assert "test_context_overflow_does_not_call_llm_judge" in firewall_test
