import { expect, test, type Page } from '@playwright/test';
import { mockLoggedInState, setupBusinessMocks } from './fixtures/business-mocks';

const CORE_VISUAL_ROUTES = [
  { name: 'dashboard', path: '/dashboard' },
  { name: 'crm', path: '/crm' },
  { name: 'approval', path: '/approval' },
  { name: 'contracts', path: '/contracts' },
  { name: 'ai-operating-system', path: '/ai-operating-system' },
];

async function prepareVisualPage(page: Page) {
  await page.route('**/api/crm/stats**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          stats: {
            total_customers: 1,
            new_this_month: 1,
            conversion_rate: 28,
            total_estimated_value: 320000,
            churned: 0,
          },
        },
      }),
    });
  });
  await page.route('**/api/crm/customers?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: [
          {
            id: 'customer-1',
            name: '华东精密实验室',
            industry: '科学仪器',
            stage: 'proposal',
            status: 'active',
            estimated_value: 320000,
            created_at: '2026-07-01T08:00:00Z',
          },
        ],
        total: 1,
      }),
    });
  });
  await page.route('**/api/metrics/web-vitals**', async (route) => {
    await route.fulfill({ status: 204, body: '' });
  });
  await page.route('**/api/chat/history/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { messages: [] } }),
    });
  });
  await page.route('**/api/tools/metadata**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ tools: [], count: 0 }),
    });
  });
  await page.route('**/api/ai/saved-prompts**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [] }),
    });
  });
  await page.route('**/api/soul-document**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: null }),
    });
  });
  await page.route('**/api/notifications/unread-count**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: { unread_count: 0 } }),
    });
  });
  await page.route('**/api/notifications?**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data: [] }),
    });
  });
  await page.route('**/api/usage/quota-alert**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          alert_level: 'normal',
          daily_usage_ratio: 0,
          monthly_usage_ratio: 0,
        },
      }),
    });
  });
  await page.route('**/api/billing/subscription**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        data: {
          subscription: {
            org_id: 'test-org-id',
            plan: 'enterprise',
            status: 'active',
          },
        },
      }),
    });
  });
  await setupBusinessMocks(page);
  await page.addInitScript(() => {
    window.localStorage.setItem('hasSeenTour', 'true');
    window.localStorage.setItem('nexus_onboarding_completed', 'true');
    window.localStorage.setItem('nexus-sidebar-collapsed', 'false');
    window.localStorage.setItem(
      'nexus-theme-settings',
      JSON.stringify({ mode: 'light', preset: 'default-light' })
    );
  });
  await mockLoggedInState(page, 'boss');
}

test.describe('core page visual regression snapshots', () => {
  test.skip(
    process.env.RUN_VISUAL_REGRESSION !== '1',
    'Set RUN_VISUAL_REGRESSION=1 after approving/updating snapshots.'
  );

  for (const route of CORE_VISUAL_ROUTES) {
    test(`${route.name} stays visually stable`, async ({ page }) => {
      await prepareVisualPage(page);
      await page.goto(route.path);
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).not.toContainText('Application error');
      await expect(page.locator('body')).not.toContainText('Something went wrong');
      await expect(page).toHaveScreenshot(`${route.name}.png`, {
        fullPage: true,
        animations: 'disabled',
        maxDiffPixelRatio: 0.015,
      });
    });
  }

  test('login stays visually stable', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('hasSeenTour', 'true');
      window.localStorage.setItem('nexus_onboarding_completed', 'true');
      window.localStorage.setItem(
        'nexus-theme-settings',
        JSON.stringify({ mode: 'light', preset: 'default-light' })
      );
    });
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveScreenshot('login.png', {
      fullPage: true,
      animations: 'disabled',
      maxDiffPixelRatio: 0.015,
    });
  });

  test('mobile inbox stays visually stable', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await prepareVisualPage(page);
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveScreenshot('mobile-inbox.png', {
      fullPage: true,
      animations: 'disabled',
      maxDiffPixelRatio: 0.015,
    });
  });
});
