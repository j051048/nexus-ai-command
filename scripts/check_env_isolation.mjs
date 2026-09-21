#!/usr/bin/env node
/**
 * Environment isolation and response-header guard.
 *
 * Why this exists: the production Vercel project rewrites /api/* to the
 * production backend. Any other environment (PR preview, staging) that omits
 * VITE_API_BASE_URL inherits that rewrite and silently talks to production
 * data. These invariants are cheap to check statically and expensive to debug
 * in production, so they are enforced in CI.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// Changing the production API host is a deliberate act: update this allowlist
// together with the deployment documentation.
const PRODUCTION_API_REWRITE_ALLOWLIST = ["https://aizhz.zeabur.app"];

const failures = [];

function read(relativePath) {
  return readFileSync(path.join(ROOT, relativePath), "utf8");
}

function checkVercelHeaders() {
  const vercel = JSON.parse(read("vercel.json"));
  const rules = Array.isArray(vercel.headers) ? vercel.headers : [];
  const catchAll = rules.find((rule) => rule.source === "/(.*)");
  if (!catchAll) {
    failures.push("vercel.json: missing catch-all header rule");
    return;
  }
  const keys = new Set((catchAll.headers || []).map((header) => header.key));
  if (!keys.has("Content-Security-Policy")) {
    failures.push(
      "vercel.json: catch-all route must send Content-Security-Policy (app pages were unprotected)",
    );
  }
  for (const required of [
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
  ]) {
    if (!keys.has(required)) {
      failures.push(`vercel.json: catch-all route is missing ${required}`);
    }
  }
}

function checkProductionRewrite() {
  const vercel = JSON.parse(read("vercel.json"));
  const rewrites = Array.isArray(vercel.rewrites) ? vercel.rewrites : [];
  for (const rewrite of rewrites) {
    const destination = String(rewrite.destination || "");
    if (!/^https?:\/\//.test(destination)) continue;
    const origin = new URL(destination).origin;
    if (!PRODUCTION_API_REWRITE_ALLOWLIST.includes(origin)) {
      failures.push(
        `vercel.json: ${rewrite.source} -> ${origin} is not in the production API allowlist`,
      );
    }
  }
}

function checkWorkflowBuildsIsolated(relativePath, label) {
  const content = read(relativePath);
  if (!content.includes("npm run build")) {
    failures.push(`${relativePath}: expected a frontend build step for ${label}`);
    return;
  }
  if (!content.includes("VITE_API_BASE_URL")) {
    failures.push(
      `${relativePath}: ${label} build must set VITE_API_BASE_URL, otherwise it inherits the production /api rewrite`,
    );
  }
}

function checkApiClientGuard() {
  const content = read("src/lib/apiConfig.ts");
  if (!content.includes("ISOLATED_ENVIRONMENTS")) {
    failures.push(
      "src/lib/apiConfig.ts: missing the preview/staging fail-fast guard for VITE_API_BASE_URL",
    );
  }
}

checkVercelHeaders();
checkProductionRewrite();
checkWorkflowBuildsIsolated(".github/workflows/preview.yml", "preview");
checkWorkflowBuildsIsolated(".github/workflows/ci.yml", "CI/staging");
checkApiClientGuard();

if (failures.length > 0) {
  console.error("ENV_ISOLATION_GATE_FAIL");
  for (const failure of failures) {
    console.error(` - ${failure}`);
  }
  process.exit(1);
}

console.log("ENV_ISOLATION_GATE_OK");
