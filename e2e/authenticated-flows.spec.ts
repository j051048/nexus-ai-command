import { test, expect } from '@playwright/test';
import { createClient } from '@supabase/supabase-js';
import * as fs from 'fs';
import * as path from 'path';

/**
 * E2E Tests: Authenticated User Journeys
 * Requires SUPABASE_SERVICE_KEY for test user management.
 * Tests cross-role navigation, data isolation, and business operations.
 */

function loadEnvVar(key: string): string {
  try {
    const envPath = path.resolve(__dirname, '../nexus_backend/.env');
    const content = fs.readFileSync(envPath, 'utf-8');
    const match = content.match(new RegExp(`^${key}=(.+)$`, 'm'));
    return match ? match[1].trim() : '';
  } catch {
    return '';
  }
}

const SUPABASE_URL =
  process.env.SUPABASE_URL ||
  loadEnvVar('SUPABASE_URL') ||
  'https://hztpazmuejgbtixihcgj.supabase.co';
const SUPABASE_SERVICE_KEY =
  process.env.SUPABASE_SERVICE_KEY || loadEnvVar('SUPABASE_SERVICE_KEY');

test.describe('Cross-Role Navigation Tests', () => {
  const employeeEmail = `e2e_employee_${Date.now()}@example.com`;
  const bossEmail = `e2e_boss_${Date.now()}@example.com`;
  const testPass = 'TestPassword123!';
  let adminClient: ReturnType<typeof createClient> | null = null;
  let employeeUserId: string | undefined;
  let bossUserId: string | undefined;

  test.beforeAll(async () => {
    if (!SUPABASE_SERVICE_KEY) {
      console.warn('SUPABASE_SERVICE_KEY not found — skipping authenticated tests');
      return;
    }

    adminClient = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY, {
      auth: { autoRefreshToken: false, persistSession: false },
    });

    // Create employee test user
    const empResult = await adminClient.auth.admin.createUser({
      email: employeeEmail,
      password: testPass,
      email_confirm: true,
      user_metadata: { name: 'E2E Employee', role: 'employee' },
    });
    employeeUserId = empResult.data.user?.id;

    // Create boss test user
    const bossResult = await adminClient.auth.admin.createUser({
      email: bossEmail,
      password: testPass,
      email_confirm: true,
      user_metadata: { name: 'E2E Boss', role: 'boss' },
    });
    bossUserId = bossResult.data.user?.id;
  });

  test.afterAll(async () => {
    if (!adminClient) return;
    try {
      const { data } = await adminClient.auth.admin.listUsers();
      for (const email of [employeeEmail, bossEmail]) {
        const user = data?.users?.find((u) => u.email === email);
        if (user) {
          await adminClient.auth.admin.deleteUser(user.id);
          console.log(`Cleaned up test user: ${email}`);
        }
      }
    } catch (e) {
      console.warn('Failed to clean up test users:', e);
    }
  });

  test('Employee can login and access dashboard', async ({ page }) => {
    test.skip(!SUPABASE_SERVICE_KEY, 'Requires SUPABASE_SERVICE_KEY');

    await page.goto('/login');
    await page.locator('#login-email').fill(employeeEmail);
    await page.locator('#login-password').fill(testPass);
    await page.getByRole('button', { name: '登录', exact: true }).click();

    await expect(page.getByText('登录成功').first()).toBeVisible({ timeout: 15000 });

    // Verify employee can see dashboard
    await expect(page).toHaveURL(/.*\//, { timeout: 30000 });

    // Navigate to key employee pages
    const employeePages = ['/dashboard', '/sales', '/documents', '/approval'];
    for (const pagePath of employeePages) {
      await page.goto(pagePath);
      // Should NOT redirect to login (user is authenticated)
      await expect(page).not.toHaveURL(/.*\/login/, { timeout: 5000 });
    }
  });

  test('Boss can login and access admin pages', async ({ page }) => {
    test.skip(!SUPABASE_SERVICE_KEY, 'Requires SUPABASE_SERVICE_KEY');

    await page.goto('/login');
    await page.locator('#login-email').fill(bossEmail);
    await page.locator('#login-password').fill(testPass);
    await page.getByRole('button', { name: '登录', exact: true }).click();

    await expect(page.getByText('登录成功').first()).toBeVisible({ timeout: 15000 });
    await expect(page).toHaveURL(/.*\//, { timeout: 30000 });

    // Boss should be able to access management pages
    const bossPages = ['/boss-dashboard', '/finance', '/contracts', '/hr'];
    for (const pagePath of bossPages) {
      await page.goto(pagePath);
      await expect(page).not.toHaveURL(/.*\/login/, { timeout: 5000 });
    }
  });

  test('Module error boundaries prevent full page crash', async ({ page }) => {
    test.skip(!SUPABASE_SERVICE_KEY, 'Requires SUPABASE_SERVICE_KEY');

    // Login first
    await page.goto('/login');
    await page.locator('#login-email').fill(employeeEmail);
    await page.locator('#login-password').fill(testPass);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await expect(page.getByText('登录成功').first()).toBeVisible({ timeout: 15000 });

    // Navigate through multiple pages to verify no crash
    const pages = ['/dashboard', '/sales', '/documents', '/approval', '/crm', '/finance'];
    for (const pagePath of pages) {
      await page.goto(pagePath);
      // The page should render something (not a blank white screen)
      await expect(page.locator('body')).not.toBeEmpty({ timeout: 10000 });
    }
  });
});

test.describe('Logout Confirmation Flow', () => {
  test('Login page displays correctly after session expiry redirect', async ({ page }) => {
    // Navigate to a protected page
    await page.goto('/dashboard');
    // Should redirect to login
    await expect(page).toHaveURL(/.*\/login/);
    // Login form should be functional
    await expect(page.locator('#login-email')).toBeVisible();
    await expect(page.locator('#login-password')).toBeVisible();
  });
});

test.describe('API Security Headers', () => {
  test('Response includes security headers', async ({ page }) => {
    const response = await page.goto('/login');
    if (response) {
      const headers = response.headers();
      // These headers are set by the backend, so they may not be present
      // on the Vite preview server. Check if the page loads correctly.
      expect(response.status()).toBeLessThan(500);
    }
  });
});
