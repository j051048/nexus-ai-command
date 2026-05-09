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
    startup = read("nexus_backend/app/startup/routers.py")
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
    startup = read("nexus_backend/app/startup/routers.py")
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
