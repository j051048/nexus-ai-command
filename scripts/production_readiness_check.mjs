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
const firstLaunchEnabled = [
  "approval",
  "billing",
  "crm",
  "documents",
  "finance",
  "knowledge",
  "projects",
  "reports",
  "sales",
  "work_orders",
];
const firstLaunchDisabled = [
  "assets",
  "battlecards",
  "certificates",
  "custom_dashboard",
  "dev_tools",
  "form_designer",
  "hr",
  "import",
  "inventory",
  "oa",
  "plugins",
  "report_builder",
  "soul_document",
  "tender",
  "training",
  "vmd",
  "workflow_designer",
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
addCheck("OPENAI_API_KEY", hasRealValue("OPENAI_API_KEY"), "critical", "Configure a primary model provider key");
addCheck("AI_BASE_URL", hasRealValue("AI_BASE_URL"), "critical", "Configure an OpenAI-compatible base URL");
addCheck("LANGGRAPH_CHECKPOINTER=postgres", env.LANGGRAPH_CHECKPOINTER === "postgres", "critical", "Use durable Agent state");
addCheck("ENCRYPTION_KEY", hasRealValue("ENCRYPTION_KEY") && env.ENCRYPTION_KEY.length >= 32, "critical", "Use a 32+ character random key");
addCheck("HEALTH_CHECK_TOKEN", hasRealValue("HEALTH_CHECK_TOKEN") && env.HEALTH_CHECK_TOKEN.length >= 24, "critical", "Use a 24+ character random health token");
addCheck("VITE_API_BASE_URL", hasRealValue("VITE_API_BASE_URL"), "critical", "Frontend must point to backend API");
addCheck("VITE_SUPABASE_URL", hasRealValue("VITE_SUPABASE_URL"), "critical", "Frontend Supabase URL is required");
addCheck("VITE_SUPABASE_PUBLISHABLE_KEY", hasRealValue("VITE_SUPABASE_PUBLISHABLE_KEY"), "critical", "Frontend Supabase anon key is required");

addCheck("CORS_ORIGINS locked down", hasRealValue("CORS_ORIGINS") && !env.CORS_ORIGINS.includes("*"), "warning", "Use explicit app domains");
addCheck("AI fallback configured", hasAnyRealValue(["AI_FALLBACK_API_KEY", "AI_FALLBACK_BASE_URL"]), "warning", "Fallback provider improves resilience");
addCheck("Sentry configured", hasRealValue("SENTRY_DSN"), "warning", "Needed for production exception triage");
addCheck("Langfuse configured", env.LANGFUSE_ENABLED !== "true" || hasAnyRealValue(["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]), "warning", "If enabled, configure Langfuse keys");
addCheck("module flags configured", hasRealValue("VITE_ENABLED_MODULES") || hasRealValue("VITE_DISABLED_MODULES"), "warning", "Gate beta modules before first launch");
addCheck(
  "first launch enabled modules are scoped",
  containsAll(csvSet("VITE_ENABLED_MODULES"), firstLaunchEnabled),
  "critical",
  `VITE_ENABLED_MODULES should include only validated first-launch modules: ${firstLaunchEnabled.join(",")}`,
);
addCheck(
  "beta modules disabled",
  containsAll(csvSet("VITE_DISABLED_MODULES"), firstLaunchDisabled),
  "critical",
  `Disable beta modules before first launch: ${firstLaunchDisabled.join(",")}`,
);
addCheck("monthly cost cap <= 1500", Number(env.TOKEN_BUDGET_MAX_COST_PER_MONTH_PER_TENANT || 999999) <= 1500, "warning", "Keep first launch blast radius small");
addCheck("tenant LLM concurrency <= 5", Number(env.MAX_CONCURRENT_LLM_PER_TENANT || 999999) <= 5, "warning", "Avoid one tenant exhausting workers");

const requiredFiles = [
  "supabase/migrations/20260508_launch_readiness_feature_flags.sql",
  "docs/PRODUCTION_LAUNCH_CHECKLIST.md",
  "docs/RUNBOOK_SMALL_COMPANY.md",
  "scripts/backup_supabase.sh",
  "scripts/backup_supabase.ps1",
];
for (const file of requiredFiles) {
  addCheck(`file: ${file}`, existsSync(path.join(root, file)), "critical", "Required launch asset is missing");
}

const migrationDir = path.join(root, "supabase", "migrations");
const migrations = existsSync(migrationDir) ? readdirSync(migrationDir).filter((name) => name.endsWith(".sql")) : [];
addCheck("Supabase migrations present", migrations.length >= 1, "critical", "Run DB migrations before launch");

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
