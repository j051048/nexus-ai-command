#!/usr/bin/env node
import { readFileSync, existsSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const args = process.argv.slice(2);

function argValue(name, fallback = "") {
  const index = args.indexOf(name);
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
}

function parseEnv(file) {
  const full = path.join(root, file);
  if (!existsSync(full)) return {};
  const out = {};
  for (const line of readFileSync(full, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const [key, ...rest] = trimmed.split("=");
    out[key.trim()] = rest.join("=").trim().replace(/^["']|["']$/g, "");
  }
  return out;
}

const envFile = argValue("--env", ".env.production");
const env = { ...parseEnv(envFile), ...process.env };
const baseUrl = argValue("--base-url", env.BACKEND_URL || env.VITE_API_BASE_URL || "");
const token = argValue("--token", env.HEALTH_CHECK_TOKEN || "");
const timeoutMs = Number(argValue("--timeout-ms", "8000"));

if (!baseUrl) {
  console.error("Missing --base-url, BACKEND_URL, or VITE_API_BASE_URL");
  process.exit(1);
}

const normalizedBase = baseUrl.replace(/\/+$/, "");
const checks = [
  { name: "live", path: "/health/live", critical: true },
  { name: "ready", path: "/health/ready", critical: true },
  { name: "basic", path: "/health", critical: true },
];

if (token) {
  checks.push({ name: "deep", path: "/health/deep", critical: false, token: true });
}

async function fetchWithTimeout(url, headers) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const started = Date.now();
    const response = await fetch(url, { headers, signal: controller.signal });
    const text = await response.text();
    return {
      ok: response.ok,
      status: response.status,
      latency_ms: Date.now() - started,
      body: text.slice(0, 500),
    };
  } finally {
    clearTimeout(timer);
  }
}

const results = [];
for (const check of checks) {
  const headers = {};
  if (check.token) headers.Authorization = `Bearer ${token}`;
  try {
    const result = await fetchWithTimeout(`${normalizedBase}${check.path}`, headers);
    results.push({ ...check, ...result });
  } catch (error) {
    results.push({
      ...check,
      ok: false,
      status: 0,
      latency_ms: timeoutMs,
      body: String(error?.message || error),
    });
  }
}

const failed = results.filter((item) => item.critical && !item.ok);
console.log(`Production health check: ${normalizedBase}`);
for (const item of results) {
  const status = item.ok ? "OK" : item.critical ? "FAIL" : "WARN";
  console.log(
    `${status.padEnd(5)} ${item.name.padEnd(6)} ${item.path} status=${item.status} latency=${item.latency_ms}ms`,
  );
  if (!item.ok && item.body) console.log(`      ${item.body}`);
}
console.log(`Summary: ${failed.length} critical failure(s), ${results.length - failed.length} checked.`);

if (failed.length > 0) process.exitCode = 1;
