import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov", "json-summary"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/test/**",
        "src/**/*.d.ts",
        "src/**/*.test.{ts,tsx}",
        "src/**/*.spec.{ts,tsx}",
        "src/vite-env.d.ts",
      ],
      // Regression floor, not a quality target. These values sit slightly
      // below the real current baseline (2026-08: lines 13.1% / branches
      // 8.8% / functions 9.1% / statements 12.4%) to absorb CI environment
      // noise; the stricter trend gate in
      // scripts/check_frontend_coverage_trend.mjs is the real guard. Raising
      // thresholds is a deliberate, staged effort tracked in
      // docs/FRONTEND_TEST_COVERAGE.md.
      thresholds: {
        lines: 12.0,
        branches: 7.5,
        functions: 8.0,
        statements: 11.0,
      },
    },
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
