#!/usr/bin/env node
import { existsSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const root = process.cwd();
const distDir = path.join(root, "dist");
const assetDir = path.join(distDir, "assets");

const budgets = {
  maxJsChunkBytes: Number(process.env.BUNDLE_BUDGET_MAX_JS_CHUNK_BYTES || 550 * 1024),
  maxCssChunkBytes: Number(process.env.BUNDLE_BUDGET_MAX_CSS_CHUNK_BYTES || 220 * 1024),
  maxTotalJsBytes: Number(process.env.BUNDLE_BUDGET_MAX_TOTAL_JS_BYTES || 5.2 * 1024 * 1024),
  maxTotalAssetBytes: Number(process.env.BUNDLE_BUDGET_MAX_TOTAL_ASSET_BYTES || 6.5 * 1024 * 1024),
  maxJsChunkCount: Number(process.env.BUNDLE_BUDGET_MAX_JS_CHUNK_COUNT || 220),
};

function fail(message) {
  console.error(`FAIL ${message}`);
  process.exitCode = 1;
}

function ok(message) {
  console.log(`OK   ${message}`);
}

function formatBytes(bytes) {
  return `${(bytes / 1024).toFixed(1)} KiB`;
}

if (!existsSync(assetDir)) {
  fail("dist/assets is missing. Run npm run build first.");
  process.exit();
}

const indexPath = path.join(distDir, "index.html");
const indexMtimeMs = existsSync(indexPath) ? statSync(indexPath).mtimeMs : 0;
const currentBuildCutoffMs = indexMtimeMs > 0 ? indexMtimeMs - 2 * 60 * 1000 : 0;
const allFiles = readdirSync(assetDir).map((name) => {
  const fullPath = path.join(assetDir, name);
  const stat = statSync(fullPath);
  return {
    name,
    bytes: stat.size,
    ext: path.extname(name),
    mtimeMs: stat.mtimeMs,
  };
});
const files = allFiles.filter((file) => file.mtimeMs >= currentBuildCutoffMs);

const jsFiles = files.filter((file) => file.ext === ".js");
const cssFiles = files.filter((file) => file.ext === ".css");
const totalBytes = files.reduce((sum, file) => sum + file.bytes, 0);
const totalJsBytes = jsFiles.reduce((sum, file) => sum + file.bytes, 0);
const largestJs = [...jsFiles].sort((a, b) => b.bytes - a.bytes)[0];
const largestCss = [...cssFiles].sort((a, b) => b.bytes - a.bytes)[0];

console.log("Bundle budget check");
console.log(`Current build assets: ${files.length} of ${allFiles.length}`);
console.log(`Total assets: ${formatBytes(totalBytes)}`);
console.log(`Total JS: ${formatBytes(totalJsBytes)} across ${jsFiles.length} chunk(s)`);
console.log(`Largest JS: ${largestJs?.name || "none"} ${largestJs ? formatBytes(largestJs.bytes) : ""}`);
console.log(`Largest CSS: ${largestCss?.name || "none"} ${largestCss ? formatBytes(largestCss.bytes) : ""}`);

if (largestJs && largestJs.bytes > budgets.maxJsChunkBytes) {
  fail(`largest JS chunk ${largestJs.name} is ${formatBytes(largestJs.bytes)}, budget is ${formatBytes(budgets.maxJsChunkBytes)}`);
} else {
  ok(`largest JS chunk within ${formatBytes(budgets.maxJsChunkBytes)}`);
}

if (largestCss && largestCss.bytes > budgets.maxCssChunkBytes) {
  fail(`largest CSS chunk ${largestCss.name} is ${formatBytes(largestCss.bytes)}, budget is ${formatBytes(budgets.maxCssChunkBytes)}`);
} else {
  ok(`largest CSS chunk within ${formatBytes(budgets.maxCssChunkBytes)}`);
}

if (totalBytes > budgets.maxTotalAssetBytes) {
  fail(`total asset size is ${formatBytes(totalBytes)}, budget is ${formatBytes(budgets.maxTotalAssetBytes)}`);
} else {
  ok(`total asset size within ${formatBytes(budgets.maxTotalAssetBytes)}`);
}

if (totalJsBytes > budgets.maxTotalJsBytes) {
  fail(`total JS size is ${formatBytes(totalJsBytes)}, budget is ${formatBytes(budgets.maxTotalJsBytes)}`);
} else {
  ok(`total JS size within ${formatBytes(budgets.maxTotalJsBytes)}`);
}

if (jsFiles.length > budgets.maxJsChunkCount) {
  fail(`JS chunk count is ${jsFiles.length}, budget is ${budgets.maxJsChunkCount}`);
} else {
  ok(`JS chunk count within ${budgets.maxJsChunkCount}`);
}

const requiredDedicatedChunks = [
  "vendor-jspdf-",
  "vendor-html2canvas-",
  "vendor-motion-",
  "vendor-charts-",
  "vendor-flow-",
];

for (const prefix of requiredDedicatedChunks) {
  const found = jsFiles.some((file) => file.name.startsWith(prefix));
  if (found) {
    ok(`dedicated chunk present: ${prefix}`);
  } else {
    fail(`dedicated chunk missing: ${prefix}`);
  }
}
