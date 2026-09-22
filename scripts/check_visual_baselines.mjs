#!/usr/bin/env node
/**
 * Guard the visual regression baselines.
 *
 * Playwright resolves snapshots per platform (`*-chromium-linux.png` on CI,
 * `*-chromium-win32.png` on a developer workstation), so a baseline committed
 * for one platform is invisible to the other. On 2026-09-21 the nightly job
 * went red for exactly this reason: only Windows baselines were committed, and
 * Playwright's `--update-snapshots=missing` mode always fails the run by design
 * (see playwright/lib/matchers/toMatchSnapshot.js handleMissing), so the
 * generator path could never be green either.
 *
 * This checker derives the expected names from the spec and fails when a
 * platform baseline is missing or orphaned, which turns "the nightly is red
 * again" into a PR-time signal with an explicit fix command.
 */
import fs from "node:fs";
import path from "node:path";

const SPEC = path.join("e2e", "visual-regression.spec.ts");
const SNAPSHOT_DIR = path.join("e2e", "visual-regression.spec.ts-snapshots");
const PROJECT = "chromium";
// CI renders on Linux; the Windows baseline keeps the local developer loop
// honest. Both are committed so neither platform silently loses coverage.
const PLATFORMS = ["linux", "win32"];

function readSpec() {
  if (!fs.existsSync(SPEC)) {
    throw new Error(`${SPEC} is missing; the visual regression suite was removed`);
  }
  return fs.readFileSync(SPEC, "utf8");
}

function expectedSnapshotNames(source) {
  const names = new Set();
  // Routes rendered through `toHaveScreenshot(`${route.name}.png`)`.
  for (const match of source.matchAll(/\{\s*name:\s*'([^']+)'\s*,\s*path:/g)) {
    names.add(match[1]);
  }
  // Literal names such as `toHaveScreenshot('login.png')`.
  for (const match of source.matchAll(/toHaveScreenshot\(\s*'([^']+)\.png'/g)) {
    names.add(match[1]);
  }
  return [...names].sort();
}

function baselineFiles() {
  if (!fs.existsSync(SNAPSHOT_DIR)) return [];
  return fs.readdirSync(SNAPSHOT_DIR).filter((name) => name.endsWith(".png"));
}

function expectedFiles(names) {
  return names.flatMap((name) =>
    PLATFORMS.map((platform) => `${name}-${PROJECT}-${platform}.png`)
  ).sort();
}

function main() {
  const source = readSpec();
  const names = expectedSnapshotNames(source);
  if (names.length === 0) {
    console.log("VISUAL_BASELINE_GATE_FAIL");
    console.log(` - no snapshot names found in ${SPEC}`);
    return 1;
  }

  const expected = expectedFiles(names);
  const present = baselineFiles();
  const presentSet = new Set(present);
  const missing = expected.filter((name) => !presentSet.has(name));
  const orphans = present.filter((name) => !expected.includes(name));

  if (missing.length || orphans.length) {
    console.log("VISUAL_BASELINE_GATE_FAIL");
    for (const name of missing) {
      console.log(` - missing baseline: ${name}`);
    }
    for (const name of orphans) {
      console.log(` - orphan baseline (no matching test): ${name}`);
    }
    if (missing.some((name) => name.includes("-linux"))) {
      console.log(
        "   fix: dispatch the Nightly Agent Quality workflow with update_visual_baselines=true, " +
          "review the uploaded PNGs and commit them"
      );
    }
    if (missing.some((name) => name.includes("-win32"))) {
      console.log(
        "   fix: RUN_VISUAL_REGRESSION=1 npx playwright test e2e/visual-regression.spec.ts " +
          "--project=chromium --update-snapshots=all (on Windows), review and commit"
      );
    }
    return 1;
  }

  console.log(
    `VISUAL_BASELINE_GATE_OK snapshots=${expected.length} tests=${names.length} ` +
      `platforms=${PLATFORMS.join(",")}`
  );
  return 0;
}

process.exit(main());
