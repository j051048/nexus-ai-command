import { test, expect } from "@playwright/test";

test.describe("Comprehensive System Test", () => {
  const testEmail = `test_${Math.floor(Math.random() * 100000)}@example.com`;
  const testName = "Test User";
  const testPass = "Password123!";

  test("User Registration with Auto-Login and Navigation", async ({ page }) => {
    console.log("Starting comprehensive test (Optimized Flow)...");

    await page.goto("/login");
    console.log("Visited /login");

    // 1. Switch to Registration
    console.log("Switching to registration tab...");
    await page.getByRole("tab", { name: /注册/ }).click();

    // 2. Fill Function using new Data Test IDs (Testability Check)
    console.log("Filling registration form using data-testids...");
    await page.getByTestId("register-name-input").fill(testName);
    await page.getByTestId("register-email-input").fill(testEmail);
    await page.getByTestId("register-password-input").fill(testPass);

    // 3. Submit
    console.log("Clicking register...");
    await page.getByTestId("register-submit-btn").click();

    // 4. Expect Success Toast AND Auto-Login Redirect
    console.log("Waiting for toast and auto-login redirect...");
    await expect(page.getByText("注册成功").first()).toBeVisible({
      timeout: 15000,
    });
    console.log("Registration success toast visible.");

    // The optimized flow should automatically redirect to dashboard
    await expect(page).toHaveURL(/.*\/dashboard/, { timeout: 30000 });
    console.log("Auto-login successful! Reached dashboard.");

    // 5. Verify Dashboard Presence
    await expect(page.getByText("战绩中心").first()).toBeVisible();

    // 6. Navigation Check (Optional, just to be sure layout is loaded)
    console.log("Checking sidebar navigation...");
    await page.getByRole("link", { name: "标书审阅" }).click();
    await expect(page).toHaveURL(/.*tender-analysis/);

    console.log("Comprehensive test passed");
  });
});
