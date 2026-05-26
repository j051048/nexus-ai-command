import { spawn } from "node:child_process";
import path from "node:path";

const root = process.cwd();
const viteBin = path.join(root, "node_modules", "vite", "bin", "vite.js");

const env = { ...process.env };
if (!env.NODE_OPTIONS?.includes("--max-old-space-size")) {
  env.NODE_OPTIONS = `${env.NODE_OPTIONS || ""} --max-old-space-size=${env.VITE_BUILD_MEMORY_MB || "4096"}`.trim();
}
if (!env.VITE_BUILD_PROFILE) {
  env.VITE_BUILD_PROFILE = "ci";
}

const args = process.argv.slice(2);
const child = spawn(process.execPath, [viteBin, "build", ...args], {
  cwd: root,
  env,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    console.error(`vite build terminated by ${signal}`);
    process.exit(1);
  }
  process.exit(code ?? 1);
});
