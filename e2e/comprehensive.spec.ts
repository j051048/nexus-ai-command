import { test, expect } from "@playwright/test";
import { createClient } from "@supabase/supabase-js";
import * as fs from "fs";
import * as path from "path";

// Load service role key from backend .env (Node.js context only, not exposed to browser)
function loadEnvVar(key: string): string {
  try {
    const envPath = path.resolve(__dirname, "../nexus_backend/.env");
    const content = fs.readFileSync(envPath, "utf-8");
    const match = content.match(new RegExp(`^${key}=(.+)$`, "m"));
    return match ? match[1].trim() : "";
  } catch {
    return "";
  }
}

const SUPABASE_URL =
  process.env.SUPABASE_URL ||
  loadEnvVar("SUPABASE_URL") ||
  "https://hztpazmuejgbtixihcgj.supabase.co";
const SUPABASE_SERVICE_KEY =
  process.env.SUPABASE_SERVICE_KEY || loadEnvVar("SUPABASE_SERVICE_KEY");

test.describe("Comprehensive System Test", () => {
  const testEmail = `e2e_test_${Date.now()}@example.com`;
  const testName = "E2E Test User";
  const testPass = "Password123!";
  let adminClient: ReturnType<typeof createClient> | null = null;

  test.beforeAll(async () => {
    if (!SUPABASE_SERVICE_KEY) {
      console.warn(
        "SUPABASE_SERVICE_KEY not found — skipping admin user creation"
      );
      return;
    }

    // Use Supabase Admin API to create a pre-confirmed test user
    adminClient = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY, {
      auth: { autoRefreshToken: false, persistSession: false },
    });

    const { data, error } = await adminClient.auth.admin.createUser({
      email: testEmail,
      password: testPass,
      email_confirm: true, // Skip email confirmation
      user_metadata: { name: testName },
    });

    if (error) {
      console.error("Failed to create test user:", error.message);
    } else {
      console.log("Created pre-confirmed test user:", data.user?.id);
    }
  });

  test.afterAll(async () => {
    // Clean up test user
    if (!adminClient) return;

    try {
      const { data } = await adminClient.auth.admin.listUsers();
      const testUser = data?.users?.find((u) => u.email === testEmail);
      if (testUser) {
        await adminClient.auth.admin.deleteUser(testUser.id);
        console.log("Cleaned up test user:", testUser.id);
      }
    } catch (e) {
      console.warn("Failed to clean up test user:", e);
    }
  });

  test("User Login and Dashboard Navigation", async ({ page }) => {
    test.skip(
      !SUPABASE_SERVICE_KEY,
      "Requires SUPABASE_SERVICE_KEY for admin user creation"
    );

    console.log("Starting comprehensive test...");

    await page.goto("/login");
    console.log("Visited /login");

    // 1. Login with pre-confirmed test user
    console.log("Filling login form...");
    await page.locator("#login-email").fill(testEmail);
    await page.locator("#login-password").fill(testPass);
    await page.getByRole("button", { name: "登录", exact: true }).click();

    // 2. Expect success toast and redirect to dashboard
    console.log("Waiting for login success and redirect...");
    await expect(page.getByText("登录成功").first()).toBeVisible({
      timeout: 15000,
    });
    console.log("Login success toast visible.");

    await expect(page).toHaveURL(/.*\//, { timeout: 30000 });
    console.log("Login successful! Reached app.");

    // 3. Verify Dashboard Presence
    await expect(page.getByText("战绩中心").first()).toBeVisible({
      timeout: 10000,
    });

    // 4. Navigation Check
    console.log("Checking sidebar navigation...");
    await page.getByRole("link", { name: "投标作战" }).click();
    await expect(page).toHaveURL(/.*growth\/tenders/);

    console.log("Comprehensive test passed");
  });
});
