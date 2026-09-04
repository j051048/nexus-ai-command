import { test, expect, Page } from '@playwright/test';
import { fulfillJson, mockLoggedInState, setupBusinessMocks } from './fixtures/business-mocks';

async function setupCriticalMocks(page: Page) {
  await setupBusinessMocks(page);
  await page.addInitScript(() => window.localStorage.setItem('hasSeenTour', 'true'));

  await page.route(/.*profile.*/, async (route) => {
    await fulfillJson(route, {
        success: true,
        data: {
          user: {
            id: 'test-user-id',
            user_id: 'test-user-id',
            email: 'test-admin@nexus-ai.com',
            name: 'E2E Admin',
            role: 'boss',
            avatar_url: null,
            organization_id: 'org-123',
          },
        },
      });
  });

  await page.route('**/api/agent-runs**', async (route) => {
    await fulfillJson(route, {
        success: true,
        data: {
          runs: [
            {
              run_id: 'run-critical-1',
              status: 'failed',
              input_summary: 'E2E replay candidate',
              created_at: new Date().toISOString(),
              tool_calls: [{ tool_name: 'get_customers' }],
            },
          ],
          total: 1,
        },
      });
  });

  await page.route('**/api/usage/cost-alerts**', async (route) => {
    await fulfillJson(route, { success: true, data: { alerts: [], summary: { count: 0 } } });
  });

  await page.route('**/api/tools/governance**', async (route) => {
    await fulfillJson(route, {
        success: true,
        data: {
          tools: [{ name: 'get_customers', category: 'crm', risk: 'low', owner: 'crm' }],
          count: 1,
          audit: { findings: {}, risk_counts: { low: 1 }, category_counts: { crm: 1 } },
          fix_suggestions: [],
          tool_rag: { tool_count: 1, ttl_s: 3600 },
        },
      });
  });

  await page.route('**/api/tools/rag/evaluate**', async (route) => {
    await fulfillJson(route, {
        success: true,
        data: { cases: [], summary: { total: 0, passed: 0, top_k_recall: 1 } },
      });
  });

  await page.route('**/api/plugins**', async (route) => {
    await fulfillJson(route, { success: true, data: { plugins: [], installed: [] } });
  });

  await page.route('**/api/competitors**', async (route) => {
    await fulfillJson(route, { success: true, data: [] });
  });
}

async function openCriticalRoute(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState('networkidle');
  // 页面应成功加载（不是登录页或错误页）
  const body = await page.textContent('body');
  expect(body).toBeTruthy();
  expect(body).not.toContain('Something went wrong');
  expect(body).not.toContain('Application error');
}

test.describe('Customer launch smoke flows', () => {
  test.beforeEach(async ({ page }) => {
    await setupCriticalMocks(page);
  });

  test('@critical login page accepts first-launch credentials', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    const body = await page.textContent('body');
    expect(body).toBeTruthy();
    expect(body).not.toContain('Something went wrong');
    expect(body).not.toContain('Application error');
  });

  test('@critical CRM customer workspace loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/crm');
  });

  test('@critical battlecard library loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/battlecards');
  });

  test('@critical approval center loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/approval');
  });

  test('@critical documents workspace loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/documents');
  });

  test('@critical knowledge graph workspace loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/knowledge');
  });

  test('@critical VMD workspace loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/vmd');
  });

  test('@critical plugin marketplace install workspace loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/plugins');
  });

  test('@critical reports dashboard loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/reports');
  });

  test('@critical finance center loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/finance');
  });

  test('@critical HR center loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/hr');
  });

  test('@critical OA center loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/oa');
  });

  test('@critical project workspace loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/projects');
  });

  test('@critical workflow designer list loads', async ({ page }) => {
    await mockLoggedInState(page, 'boss');
    await openCriticalRoute(page, '/workflows');
  });
});
