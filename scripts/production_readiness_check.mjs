#!/usr/bin/env node
import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const args = process.argv.slice(2);
const envArgIndex = args.indexOf("--env");
const envFile =
  envArgIndex >= 0 && args[envArgIndex + 1]
    ? args[envArgIndex + 1]
    : existsSync(path.join(root, ".env.production"))
      ? ".env.production"
      : ".env.production.example";

function parseEnv(file) {
  const full = path.join(root, file);
  if (!existsSync(full)) return {};
  const raw = readFileSync(full, "utf8");
  const result = {};
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const equal = trimmed.indexOf("=");
    if (equal === -1) continue;
    const key = trimmed.slice(0, equal).trim();
    const value = trimmed.slice(equal + 1).trim().replace(/^["']|["']$/g, "");
    result[key] = value;
  }
  return result;
}

const env = { ...parseEnv(envFile), ...process.env };
const checks = [];
const customerLaunchEnabled = [
  "approval",
  "crm",
  "documents",
  "finance",
  "hr",
  "knowledge",
  "oa",
  "plugins",
  "projects",
  "reports",
  "vmd",
  "workflow_designer",
];
const customerLaunchDisabled = [
  "dev_tools",
];

function addCheck(name, ok, severity, hint) {
  checks.push({ name, ok: Boolean(ok), severity, hint });
}

function hasRealValue(key) {
  const value = env[key] || "";
  return Boolean(
    value &&
      !value.includes("your-") &&
      !value.includes("replace-with") &&
      !value.includes("change-me"),
  );
}

function hasAnyRealValue(keys) {
  return keys.some((key) => hasRealValue(key));
}

function csvSet(key) {
  return new Set(
    String(env[key] || "")
      .split(",")
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean),
  );
}

function containsAll(set, values) {
  return values.every((value) => set.has(value));
}

addCheck("env file exists", existsSync(path.join(root, envFile)), "critical", `${envFile} must exist`);
addCheck("ENV=production", env.ENV === "production" || env.ENV === "prod", "critical", "Set ENV=production");
addCheck("DEBUG=false", String(env.DEBUG).toLowerCase() !== "true", "critical", "Disable DEBUG in production");
addCheck("SUPABASE_URL", hasRealValue("SUPABASE_URL"), "critical", "Configure Supabase URL");
addCheck("SUPABASE_SERVICE_KEY", hasRealValue("SUPABASE_SERVICE_KEY"), "critical", "Configure Supabase service role key");
addCheck(
  "JWT secret",
  hasAnyRealValue(["SUPABASE_JWT_SECRET", "JWT_SECRET"]),
  "critical",
  "Configure SUPABASE_JWT_SECRET or JWT_SECRET",
);
addCheck("REDIS_URL", hasRealValue("REDIS_URL"), "critical", "Redis is required for rate limits, Celery, token budgets");
addCheck(
  "distributed rate limiting",
  String(env.ALLOW_MEMORY_RATE_LIMIT || "").toLowerCase() !== "1",
  "warning",
  "Only set ALLOW_MEMORY_RATE_LIMIT=1 for explicitly approved private single-node deployments",
);
addCheck("OPENAI_API_KEY", hasRealValue("OPENAI_API_KEY"), "critical", "Configure a primary model provider key");
addCheck("AI_BASE_URL", hasRealValue("AI_BASE_URL"), "critical", "Configure an OpenAI-compatible base URL");
addCheck("LANGGRAPH_CHECKPOINTER=postgres", env.LANGGRAPH_CHECKPOINTER === "postgres", "critical", "Use durable Agent state");
addCheck("ENCRYPTION_KEY", hasRealValue("ENCRYPTION_KEY") && env.ENCRYPTION_KEY.length >= 32, "critical", "Use a 32+ character random key");
addCheck("HEALTH_CHECK_TOKEN", hasRealValue("HEALTH_CHECK_TOKEN") && env.HEALTH_CHECK_TOKEN.length >= 24, "critical", "Use a 24+ character random health token");
addCheck("VITE_API_BASE_URL", hasRealValue("VITE_API_BASE_URL"), "critical", "Frontend must point to backend API");
addCheck("VITE_SUPABASE_URL", hasRealValue("VITE_SUPABASE_URL"), "critical", "Frontend Supabase URL is required");
addCheck("VITE_SUPABASE_PUBLISHABLE_KEY", hasRealValue("VITE_SUPABASE_PUBLISHABLE_KEY"), "critical", "Frontend Supabase anon key is required");

addCheck("CORS_ORIGINS locked down", hasRealValue("CORS_ORIGINS") && !env.CORS_ORIGINS.includes("*"), "warning", "Use explicit app domains");
addCheck(
  "platform super admin allowlist",
  hasRealValue("PLATFORM_SUPER_ADMIN_EMAILS") && !env.PLATFORM_SUPER_ADMIN_EMAILS.includes("*"),
  "critical",
  "Set PLATFORM_SUPER_ADMIN_EMAILS to the explicit platform owner email(s)",
);
addCheck("AI fallback configured", hasAnyRealValue(["AI_FALLBACK_API_KEY", "AI_FALLBACK_BASE_URL"]), "warning", "Fallback provider improves resilience");
addCheck("Sentry configured", hasRealValue("SENTRY_DSN"), "warning", "Needed for production exception triage");
addCheck("Langfuse configured", env.LANGFUSE_ENABLED !== "true" || hasAnyRealValue(["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]), "warning", "If enabled, configure Langfuse keys");
addCheck("module flags configured", hasRealValue("VITE_ENABLED_MODULES") || hasRealValue("VITE_DISABLED_MODULES"), "warning", "Declare launch modules explicitly");
addCheck("small-company launch profile", env.VITE_LAUNCH_PROFILE === "small_company", "critical", "First production rollout must use VITE_LAUNCH_PROFILE=small_company");
addCheck(
  "customer launch modules enabled",
  containsAll(csvSet("VITE_ENABLED_MODULES"), customerLaunchEnabled),
  "critical",
  `VITE_ENABLED_MODULES must include customer-facing modules: ${customerLaunchEnabled.join(",")}`,
);
addCheck(
  "developer tools disabled",
  containsAll(csvSet("VITE_DISABLED_MODULES"), customerLaunchDisabled),
  "critical",
  `Disable non-customer developer modules: ${customerLaunchDisabled.join(",")}`,
);
addCheck("demo data disabled", env.VITE_ENABLE_DEMO_DATA !== "true", "critical", "Disable demo-data entrypoints for production launch");
addCheck("monthly cost cap <= 1500", Number(env.TOKEN_BUDGET_MAX_COST_PER_MONTH_PER_TENANT || 999999) <= 1500, "warning", "Keep first launch blast radius small");
addCheck("tenant LLM concurrency <= 5", Number(env.MAX_CONCURRENT_LLM_PER_TENANT || 999999) <= 5, "warning", "Avoid one tenant exhausting workers");

const requiredFiles = [
  "Dockerfile",
  "supabase/migrations/20260508_launch_readiness_feature_flags.sql",
  "supabase/migrations/20260514_p0_document_embeddings_vector_index.sql",
  "supabase/migrations/20260514_p0_tenant_rls_policy_backfill.sql",
  "supabase/migrations/20260514_p2_cost_report_rpc.sql",
  "docs/PRODUCTION_LAUNCH_CHECKLIST.md",
  "docs/RUNBOOK_SMALL_COMPANY.md",
  "docs/CUSTOMER_ACCEPTANCE_CRITERIA.md",
  "docs/PRIVATE_DEPLOYMENT_PGBOUNCER.md",
  "docs/SOC2_CONTROLS.md",
  "docs/TOOL_DEVELOPMENT_GUIDE.md",
  "scripts/backup_supabase.sh",
  "scripts/backup_supabase.ps1",
  "scripts/release_quality_gate.py",
  "scripts/check_bundle_budget.mjs",
  "scripts/collect_release_evidence.py",
  "scripts/production_health_check.mjs",
  "scripts/collect_soc2_evidence.py",
  "scripts/agent_replay_nightly.py",
  "scripts/customer_acceptance_gate.py",
  "scripts/generate_customer_handoff.py",
  ".github/workflows/ci.yml",
  ".github/workflows/nightly-agent-quality.yml",
  "src/config/customerLaunchModules.ts",
  "src/components/product/LaunchChecklistPanel.tsx",
  "src/pages/CustomerSuccessPage.tsx",
  "src/pages/DeploymentReadinessPage.tsx",
  "src/pages/PermissionMatrixPage.tsx",
  "e2e/top10-critical-flows.spec.ts",
  "e2e/customer-business-acceptance.spec.ts",
  "nexus_backend/tests/k6/small_company.js",
  "nexus_backend/app/routers/enterprise_sso.py",
  "nexus_backend/app/routers/compliance.py",
  "nexus_backend/app/core/api_key_middleware.py",
  "nexus_backend/app/core/tool_rbac.py",
];
for (const file of requiredFiles) {
  addCheck(`file: ${file}`, existsSync(path.join(root, file)), "critical", "Required launch asset is missing");
}

const migrationDir = path.join(root, "supabase", "migrations");
const migrations = existsSync(migrationDir) ? readdirSync(migrationDir).filter((name) => name.endsWith(".sql")) : [];
addCheck("Supabase migrations present", migrations.length >= 1, "critical", "Run DB migrations before launch");

const launchMetadataPath = path.join(root, "src/config/customerLaunchModules.ts");
const launchMetadata = existsSync(launchMetadataPath) ? readFileSync(launchMetadataPath, "utf8") : "";
for (const module of customerLaunchEnabled) {
  addCheck(
    `launch metadata: ${module}`,
    launchMetadata.includes(`flag: "${module}"`) &&
      launchMetadata.includes("owner:") &&
      launchMetadata.includes("smokePath:"),
    "critical",
    `Add owner and smokePath for ${module} in src/config/customerLaunchModules.ts`,
  );
}

const top10Smoke = existsSync(path.join(root, "e2e/top10-critical-flows.spec.ts"))
  ? readFileSync(path.join(root, "e2e/top10-critical-flows.spec.ts"), "utf8")
  : "";
const goldenSmokePaths = ["/login", "/crm", "/approval", "/documents", "/knowledge", "/vmd", "/plugins", "/reports", "/finance", "/workflows"];
for (const routePath of goldenSmokePaths) {
  addCheck(
    `golden smoke route: ${routePath}`,
    top10Smoke.includes(routePath),
    "critical",
    `Top 10 E2E smoke test must cover ${routePath}`,
  );
}

const businessAcceptance = existsSync(path.join(root, "e2e/customer-business-acceptance.spec.ts"))
  ? readFileSync(path.join(root, "e2e/customer-business-acceptance.spec.ts"), "utf8")
  : "";
const businessFlows = [
  "CRM can create a customer",
  "approval can be submitted",
  "document upload appears",
  "project can be created",
  "HR employee and OA announcement",
  "AI chat sends a message",
  "employee role is blocked",
];
for (const flow of businessFlows) {
  addCheck(
    `business acceptance flow: ${flow}`,
    businessAcceptance.includes(flow),
    "critical",
    `Customer business acceptance E2E must cover: ${flow}`,
  );
}

const productReadinessFiles = {
  "first-week checklist": {
    file: "src/components/product/LaunchChecklistPanel.tsx",
    tokens: ["首周落地任务", "nexus:first-week-launch-checklist"],
  },
  "customer success dashboard": {
    file: "src/pages/CustomerSuccessPage.tsx",
    tokens: ["客户成功看板", "首周激活目标"],
  },
  "permission safety matrix": {
    file: "src/pages/PermissionMatrixPage.tsx",
    tokens: ["权限与 AI 安全矩阵", "Tool RBAC"],
  },
  "deployment product acceptance": {
    file: "src/pages/DeploymentReadinessPage.tsx",
    tokens: ["产品验收口径", "员工能从工作台完成客户、审批、文档和 AI 问答首周任务"],
  },
};

for (const [name, check] of Object.entries(productReadinessFiles)) {
  const fullPath = path.join(root, check.file);
  const body = existsSync(fullPath) ? readFileSync(fullPath, "utf8") : "";
  addCheck(
    `product readiness: ${name}`,
    check.tokens.every((token) => body.includes(token)),
    "critical",
    `${check.file} must include customer-facing readiness copy`,
  );
}

const criticalFailed = checks.filter((check) => !check.ok && check.severity === "critical");
const warnings = checks.filter((check) => !check.ok && check.severity === "warning");

console.log(`Production readiness check using ${envFile}`);
for (const check of checks) {
  const icon = check.ok ? "OK" : check.severity === "critical" ? "FAIL" : "WARN";
  console.log(`${icon.padEnd(4)} ${check.name}${check.ok ? "" : ` - ${check.hint}`}`);
}
console.log("");
console.log(`Summary: ${criticalFailed.length} critical failure(s), ${warnings.length} warning(s).`);

if (criticalFailed.length > 0) {
  process.exitCode = 1;
}
