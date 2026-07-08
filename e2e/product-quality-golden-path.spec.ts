import { test, expect, type Page } from '@playwright/test';
import { createFakeJwt, fulfillJson, loginViaForm, setupBusinessMocks } from './fixtures/business-mocks';

async function setupProductQualityMocks(page: Page, role = 'boss') {
  await setupBusinessMocks(page);
  await page.addInitScript(() => window.localStorage.setItem('hasSeenTour', 'true'));

  await page.unroute('**/auth/v1/token*').catch(() => undefined);
  await page.unroute('**/auth/v1/user*').catch(() => undefined);

  await page.route('**/auth/v1/token*', async (route) => {
    await fulfillJson(route, {
      access_token: createFakeJwt(role),
      token_type: 'bearer',
      expires_in: 3600,
      refresh_token: 'fake-refresh',
      user: {
        id: 'test-user-id',
        email: `${role}@nexus-ai.com`,
        user_metadata: { role, name: `E2E ${role}` },
        app_metadata: { provider: 'email', role },
      },
    });
  });

  await page.route('**/auth/v1/user*', async (route) => {
    await fulfillJson(route, {
      id: 'test-user-id',
      email: `${role}@nexus-ai.com`,
      user_metadata: { role, name: `E2E ${role}` },
      app_metadata: { provider: 'email', role },
    });
  });

  await page.route(/.*profile.*/, async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        user: {
          id: 'test-user-id',
          user_id: 'test-user-id',
          email: `${role}@nexus-ai.com`,
          name: `E2E ${role}`,
          role,
          avatar_url: null,
          organization_id: 'org-123',
        },
      },
    });
  });

  await page.route('**/rest/v1/rpc/get_user_role*', async (route) => {
    await fulfillJson(route, role);
  });

  await page.route('**/api/feedback/experience', async (route) => {
    await fulfillJson(route, { success: true, data: { recorded: true } });
  });

  await page.route('**/api/crm/stats*', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: {
        stats: {
          total_customers: 1,
          new_this_month: 1,
          conversion_rate: 20,
          total_estimated_value: 580000,
          churned: 0,
        },
      },
    });
  });

  await page.route('**/api/crm/customers**', async (route) => {
    if (route.request().method() === 'OPTIONS') {
      await fulfillJson(route, {});
      return;
    }
    await fulfillJson(route, {
      success: true,
      data: [
        {
          id: 'cust-1',
          organization_id: 'org-123',
          name: '华东实验室',
          company: '华东实验室有限公司',
          industry: '医疗',
          stage: 'opportunity',
          source: 'referral',
          estimated_value: 580000,
          assigned_to: null,
          tags: [],
          metadata: {},
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
      total: 1,
    });
  });

  await page.route('**/api/contracts**', async (route) => {
    await fulfillJson(route, {
      success: true,
      data: [
        {
          id: 'contract-1',
          title: '华东实验室质谱采购合同',
          status: 'active',
          amount: 580000,
          customer_name: '华东实验室',
          end_date: new Date(Date.now() + 1000 * 60 * 60 * 24 * 45).toISOString(),
        },
      ],
    });
  });
}

async function expectHealthyPage(page: Page) {
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(300);
  const body = await page.textContent('body');
  expect(body).toBeTruthy();
  expect(body).not.toContain('Something went wrong');
  expect(body).not.toContain('Application error');
  expect(body).not.toContain('Unhandled');
}

test.describe('product quality golden paths', () => {
  test('core workspaces expose the unified AI insight layer', async ({ page }) => {
    await setupProductQualityMocks(page, 'boss');
    await loginViaForm(page, 'boss');

    for (const path of ['/dashboard', '/crm', '/approval', '/contracts']) {
      await page.goto(path);
      await expectHealthyPage(page);
      await expect(page.getByTestId('ai-insight-panel').first()).toBeVisible({ timeout: 15000 });
    }
  });

  test('command bar can launch executable business actions with page context', async ({ page }) => {
    await setupProductQualityMocks(page, 'boss');
    await loginViaForm(page, 'boss');

    await page.goto('/crm');
    await expectHealthyPage(page);
    await page.keyboard.press('Control+K');
    await expect(page.getByTestId('global-command-input')).toBeVisible({ timeout: 5000 });
    await page.getByTestId('global-command-input').fill('创建客户');
    await expect(page.getByText('创建客户').first()).toBeVisible({ timeout: 5000 });
  });

  test('employee entering boss-only workspace is guided back to dashboard', async ({ page }) => {
    await setupProductQualityMocks(page, 'employee');
    await loginViaForm(page, 'employee');

    await page.goto('/boss-dashboard');
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10000 });
    await expectHealthyPage(page);
  });
});
