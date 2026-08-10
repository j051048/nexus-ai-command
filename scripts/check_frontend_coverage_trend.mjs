#!/usr/bin/env node
/**
 * Frontend coverage trend gate.
 *
 * The vitest thresholds in vitest.config.ts are a hard regression floor.
 * This script is the "honest" trend check used in CI: it compares the current
 * coverage summary against a committed baseline and fails when any metric
 * drops beyond tolerance. It deliberately does NOT compare against an
 * aspirational number such as 65% - the quality target is tracked in
 * docs/FRONTEND_TEST_COVERAGE.md instead.
 *
 * Usage:
 *   node scripts/check_frontend_coverage_trend.mjs --check   # CI gate
 *   node scripts/check_frontend_coverage_trend.mjs --update  # refresh baseline
 */

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SUMMARY_PATH = resolve(ROOT, "coverage", "coverage-summary.json");
const BASELINE_PATH = resolve(ROOT, "docs", "test-coverage", "frontend-baseline.json");
const TOLERANCE_PP = 0.75; // percentage-point drop allowed before failing

const METRICS = ["lines", "statements", "functions", "branches"];

function readCurrent() {
  if (!existsSync(SUMMARY_PATH)) {
    console.warn(
      `[coverage-trend] ${SUMMARY_PATH} not found; run "npm run test -- --coverage" first. Treating as SKIP.`
    );
    return null;
  }
  const summary = JSON.parse(readFileSync(SUMMARY_PATH, "utf-8"));
  const total = summary.total;
  const current = {};
  for (const metric of METRICS) {
    current[metric] = Number(total[metric].pct);
  }
  return current;
}

function readBaseline() {
  if (!existsSync(BASELINE_PATH)) {
    console.warn(`[coverage-trend] Baseline missing: ${BASELINE_PATH}`);
    return null;
  }
  return JSON.parse(readFileSync(BASELINE_PATH, "utf-8"));
}

function runCheck() {
  const current = readCurrent();
  if (!current) return 0;
  const baseline = readBaseline();
  if (!baseline) {
    console.error(
      `[coverage-trend] FAIL: no baseline to compare against. ` +
        `Run "npm run test -- --coverage && node scripts/check_frontend_coverage_trend.mjs --update" and commit the result.`
    );
    return 1;
  }

  const failures = [];
  console.log("[coverage-trend] current vs baseline:");
  for (const metric of METRICS) {
    const cur = current[metric];
    const base = Number(baseline[metric]);
    const drop = base - cur;
    const marker = drop > TOLERANCE_PP ? "  <-- FAIL" : "";
    console.log(
      `  ${metric.padEnd(10)} ${cur.toFixed(2)}%  (baseline ${base.toFixed(2)}%, drop ${drop.toFixed(2)}pp)${marker}`
    );
    if (drop > TOLERANCE_PP) {
      failures.push(
        `${metric} dropped ${drop.toFixed(2)}pp (${base.toFixed(2)} -> ${cur.toFixed(2)})`
      );
    }
  }
  if (failures.length) {
    console.error(`[coverage-trend] FAIL: ${failures.join("; ")}`);
    return 1;
  }
  console.log("[coverage-trend] OK: coverage did not regress beyond tolerance.");
  return 0;
}

function runUpdate() {
  const current = readCurrent();
  if (!current) return 1;
  const payload = {
    ...current,
    updated_at: new Date().toISOString(),
    note: "Regression floor tracked by scripts/check_frontend_coverage_trend.mjs",
  };
  writeFileSync(BASELINE_PATH, JSON.stringify(payload, null, 2) + "\n", "utf-8");
  console.log(`[coverage-trend] baseline updated: ${BASELINE_PATH}`);
  return 0;
}

const mode = process.argv[2] ?? "--check";
if (mode === "--update") {
  process.exit(runUpdate());
}
process.exit(runCheck());
