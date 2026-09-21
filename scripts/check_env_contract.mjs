#!/usr/bin/env node
/**
 * Frontend environment contract guard.
 *
 * Every VITE_* variable the browser bundle reads must be documented in
 * .env.example, so a new configuration knob cannot reach production without an
 * operator-visible default and description.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SRC = path.join(ROOT, "src");
const SKIP_DIRS = new Set(["node_modules", "dist", "coverage"]);

function walk(dir) {
  const entries = [];
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    const stats = statSync(full);
    if (stats.isDirectory()) {
      if (!SKIP_DIRS.has(name)) entries.push(...walk(full));
      continue;
    }
    if (/\.(ts|tsx|js|jsx|mjs)$/.test(name) && !/\.(test|spec)\./.test(name)) {
      entries.push(full);
    }
  }
  return entries;
}

const referenced = new Set();
for (const file of walk(SRC)) {
  const content = readFileSync(file, "utf8");
  for (const match of content.matchAll(/import\.meta\.env\.(VITE_[A-Z0-9_]+)/g)) {
    referenced.add(match[1]);
  }
}

const documented = new Set();
const example = readFileSync(path.join(ROOT, ".env.example"), "utf8");
for (const line of example.split(/\r?\n/)) {
  const match = line.match(/^\s*(VITE_[A-Z0-9_]+)\s*=/);
  if (match) documented.add(match[1]);
}

const undocumented = [...referenced].filter((name) => !documented.has(name)).sort();
const stale = [...documented].filter((name) => !referenced.has(name)).sort();

if (undocumented.length > 0) {
  console.error("ENV_CONTRACT_GATE_FAIL");
  console.error(
    " - these VITE_* variables are read by the app but missing from .env.example:",
  );
  for (const name of undocumented) console.error(`   ${name}`);
  process.exit(1);
}

console.log(
  `ENV_CONTRACT_GATE_OK referenced=${referenced.size} documented=${documented.size}`,
);
if (stale.length > 0) {
  console.log(
    `ENV_CONTRACT_GATE_NOTE .env.example has unused entries (allowed): ${stale.join(", ")}`,
  );
}
